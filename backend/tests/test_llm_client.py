"""OpenRouter client: budget, reply validation, and error mapping, with HTTP mocked."""

import json

import httpx
import pytest

from app.investigation.extract import Extraction
from app.llm import llm_client
from app.llm.llm_client import LLMClient, ModelBudgetExceeded, ModelCallError, parse_reply, strict_schema

VALID = {"company": "Nexora", "role": None, "claims": [], "funnel_stages": []}


def _reply(content: str, finish_reason: str = "stop") -> dict:
    return {"choices": [{"message": {"content": content}, "finish_reason": finish_reason}]}


def _client(status: int, payload: dict | None = None) -> LLMClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload or {})

    return LLMClient(http=httpx.Client(transport=httpx.MockTransport(handler)))


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(llm_client, "OPENROUTER_MODEL", "test/model:free")


def test_valid_json_is_parsed():
    assert parse_reply(_reply(json.dumps(VALID)), Extraction).company == "Nexora"


def test_code_fenced_json_is_parsed():
    assert parse_reply(_reply(f"```json\n{json.dumps(VALID)}\n```"), Extraction).company == "Nexora"


def test_wrong_shape_is_an_error_not_a_guess():
    with pytest.raises(ModelCallError):
        parse_reply(_reply('{"company": "Nexora"}'), Extraction)


def test_cut_off_answer_is_an_error():
    with pytest.raises(ModelCallError, match="cut off"):
        parse_reply(_reply(json.dumps(VALID), finish_reason="length"), Extraction)


def test_strict_schema_closes_every_object():
    schema = strict_schema(Extraction)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"company", "role", "claims", "funnel_stages", "several_opportunities"}
    for definition in schema["$defs"].values():
        assert definition["additionalProperties"] is False


def test_successful_call_counts_one_call():
    client = _client(200, _reply(json.dumps(VALID)))
    client.structured("system", "user", Extraction)
    assert client.calls == 1


def test_budget_is_enforced_before_calling():
    client = _client(200, _reply(json.dumps(VALID)))
    client.calls = client.max_calls
    with pytest.raises(ModelBudgetExceeded):
        client.structured("system", "user", Extraction)


@pytest.mark.parametrize(
    "status, message",
    [(401, "API key"), (402, "credit"), (429, "busy"), (503, "error \\(503\\)")],
)
def test_http_errors_become_plain_messages(status, message):
    with pytest.raises(ModelCallError, match=message):
        _client(status).structured("system", "user", Extraction)


def test_missing_key_is_a_configuration_error(monkeypatch):
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "")
    with pytest.raises(ModelCallError, match="not configured"):
        _client(200).structured("system", "user", Extraction)


def _sequence(*responses) -> tuple[LLMClient, list]:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        status, body = responses[min(len(seen), len(responses) - 1)]
        seen.append(status)
        return httpx.Response(status, json=body) if isinstance(body, dict) else httpx.Response(status, text=body)

    return LLMClient(http=httpx.Client(transport=httpx.MockTransport(handler))), seen


def test_a_passing_failure_is_retried_once_without_eating_a_later_steps_call():
    client, seen = _sequence((503, {}), (200, _reply(json.dumps(VALID))))
    assert client.structured("system", "user", Extraction).company == VALID["company"]
    assert seen == [503, 200]
    assert client.max_calls - client.calls == 4 - 1  # the retry brought its own call


def test_only_one_retry_per_investigation():
    client, seen = _sequence((503, {}))
    with pytest.raises(ModelCallError):
        client.structured("system", "user", Extraction)
    with pytest.raises(ModelCallError):
        client.structured("system", "user", Extraction)
    assert seen == [503, 503, 503]


def test_the_daily_cap_is_named_and_never_retried():
    client, seen = _sequence((429, '{"error":{"message":"Rate limit exceeded: free-models-per-day"}}'))
    with pytest.raises(ModelCallError, match="daily model limit"):
        client.structured("system", "user", Extraction)
    assert seen == [429]
