"""The only place that calls the model (OpenRouter).

Counts model calls against the per-investigation budget, asks for JSON that
matches a Pydantic schema, validates the reply, and turns failures into plain
messages. See spec.md > Components > Backend > app/llm/llm_client.py.
"""

import copy
import re
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import MAX_MODEL_CALLS, OPENROUTER_API_KEY, OPENROUTER_MODEL, VISION_MODEL

T = TypeVar("T", bound=BaseModel)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT_SECONDS = 90.0
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


class ModelBudgetExceeded(Exception):
    """Raised instead of making a call that would exceed MAX_MODEL_CALLS."""


class ModelCallError(Exception):
    """A model call failed. The message is safe to show to the person."""


class LLMClient:
    """One instance per investigation, so the call counter is per investigation."""

    def __init__(self, max_calls: int = MAX_MODEL_CALLS, http: httpx.Client | None = None):
        self.max_calls = max_calls
        self.calls = 0
        self._http = http

    def structured(self, system: str, user: str, output_format: type[T], max_tokens: int = 8000) -> T:
        """A reply that must match output_format's schema (calls 1-4)."""
        payload = self._post({
            "model": OPENROUTER_MODEL,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": output_format.__name__,
                    "strict": True,
                    "schema": strict_schema(output_format),
                },
            },
        })
        return parse_reply(payload, output_format)

    def read_image(self, system: str, instruction: str, image_data_url: str | list[str], max_tokens: int = 8000) -> str:
        """A plain-text reply about one or more images, from the vision model (screenshot transcription)."""
        urls = [image_data_url] if isinstance(image_data_url, str) else image_data_url
        payload = self._post({
            "model": VISION_MODEL,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instruction},
                        *({"type": "image_url", "image_url": {"url": url}} for url in urls),
                    ],
                },
            ],
        })
        return parse_text_reply(payload)

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        if self.calls >= self.max_calls:
            raise ModelBudgetExceeded(f"Model-call budget of {self.max_calls} reached.")
        if not OPENROUTER_API_KEY or not body.get("model"):
            raise ModelCallError("JobXray is not configured: set OPENROUTER_API_KEY and the model names.")
        self.calls += 1

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "X-Title": "JobXray",
        }
        try:
            response = self._client().post(OPENROUTER_URL, json=body, headers=headers)
        except httpx.TimeoutException:
            raise ModelCallError("The model took too long to answer. Try again.")
        except httpx.HTTPError:
            raise ModelCallError("JobXray could not reach OpenRouter. Check the internet connection.")

        if response.status_code == 401:
            raise ModelCallError("JobXray could not sign in to OpenRouter. Check the API key.")
        if response.status_code == 402:
            raise ModelCallError("The OpenRouter account has no credit available for this request.")
        if response.status_code == 429:
            raise ModelCallError("The free model's request limit was reached. Try again later.")
        if response.status_code >= 400:
            raise ModelCallError(f"OpenRouter returned an error ({response.status_code}). Try again.")
        return response.json()

    def _client(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(timeout=TIMEOUT_SECONDS)
        return self._http


def parse_text_reply(payload: dict[str, Any]) -> str:
    if payload.get("error"):
        raise ModelCallError("OpenRouter reported an error for this request. Try again.")
    try:
        choice = payload["choices"][0]
        content = choice["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        raise ModelCallError("The model returned an empty answer. Try again.")
    if choice.get("finish_reason") == "length":
        raise ModelCallError("The answer was cut off before it finished. Try a smaller screenshot.")
    return content.strip()


def parse_reply(payload: dict[str, Any], output_format: type[T]) -> T:
    """Validate the model's JSON against the schema. Anything else is an error, never a guess."""
    if payload.get("error"):
        raise ModelCallError("OpenRouter reported an error for this request. Try again.")
    try:
        choice = payload["choices"][0]
        content = choice["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        raise ModelCallError("The model returned an empty answer. Try again.")
    if choice.get("finish_reason") == "length":
        raise ModelCallError("The analysis was cut off before it finished. Try a shorter paste.")
    try:
        return output_format.model_validate_json(_FENCE.sub("", content.strip()))
    except ValidationError:
        raise ModelCallError("The model's answer did not match the expected format. Try again.")


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic's JSON schema with every object closed and every property required (strict mode)."""
    schema = copy.deepcopy(model.model_json_schema())

    def close(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
            node.pop("title", None)
            for value in node.values():
                close(value)
        elif isinstance(node, list):
            for item in node:
                close(item)

    close(schema)
    return schema
