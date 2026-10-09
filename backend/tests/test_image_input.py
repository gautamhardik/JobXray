"""Slice 6: a screenshot is transcribed, shown, and investigated with a 5-call budget."""

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import MAX_IMAGE_BYTES
from app.input import InputUnreadable
from app.input.image import validate_image
from app.investigation.extract import Extraction, ExtractedClaim, ExtractedStage
from app.investigation.pipeline import run_from_image, run_investigation
from app.llm.llm_client import LLMClient
from app.main import app, jobs
from tests.helpers import ScriptedClient, saved_scraper

FEE_TEXT = (Path(__file__).parent / "fixtures" / "fee_conversation.txt").read_text(encoding="utf-8")
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def data_url(raw: bytes = PNG, kind: str = "png") -> str:
    return f"data:image/{kind};base64,{base64.b64encode(raw).decode()}"


def _extraction() -> Extraction:
    return Extraction(
        company="Nexora Technologies",
        role="Business Analyst Internship",
        claims=[ExtractedClaim(kind="fee", value="₹1,999", excerpt="Registration fee for the training is ₹1,999")],
        funnel_stages=[ExtractedStage(stage="payment_request", excerpt="Registration fee for the training is ₹1,999")],
    )


def test_valid_png_passes_validation():
    validate_image(data_url())


@pytest.mark.parametrize(
    "value, message",
    [
        ("data:text/plain;base64,aGVsbG8=", "PNG, JPEG, or WebP"),
        ("not a data url", "PNG, JPEG, or WebP"),
        (data_url(b"GIF89a" + b"\x00" * 10), "not a valid image"),
        (data_url(PNG + b"\x00" * MAX_IMAGE_BYTES), "larger than 4 MB"),
    ],
    ids=["not-an-image-type", "not-a-data-url", "gif-bytes-labelled-png", "over-4mb"],
)
def test_bad_or_oversized_images_are_refused_before_any_model_call(value, message):
    client = ScriptedClient(_extraction(), transcription=FEE_TEXT)
    with pytest.raises(InputUnreadable, match=message):
        run_from_image(value, client, saved_scraper({}))
    assert client.calls == 0


def test_screenshot_is_transcribed_and_investigated():
    client = ScriptedClient(_extraction(), transcription=FEE_TEXT, max_calls=5)
    result = run_from_image(data_url(), client, saved_scraper({}))
    assert result.source.source_type == "screenshot"
    assert result.source.transcription == FEE_TEXT
    assert result.decision == "STOP"
    fee = next(r for r in result.evidence if r.claim_id == "payment")
    assert fee.source_type == "screenshot"
    assert client.calls == 3  # transcription, extraction, self-challenge (no company quote, so no domain proposal)


def test_excerpts_are_checked_against_the_transcription():
    client = ScriptedClient(_extraction(), transcription="Hello, a different message with no fee.", max_calls=5)
    result = run_from_image(data_url(), client, saved_scraper({}))
    assert result.funnel.detected == 0
    assert result.dropped_quotes == 2
    assert result.decision == "VERIFY FIRST"


def test_empty_transcription_is_a_plain_error():
    client = ScriptedClient(_extraction(), transcription="NO_TEXT", max_calls=5)
    with pytest.raises(InputUnreadable, match="couldn't read any text"):
        run_from_image(data_url(), client, saved_scraper({}))


def test_image_budget_is_five_and_text_budget_is_four(monkeypatch):
    seen = {}
    real_run = run_investigation

    def spy(text, client=None, scraper=None, origin=None, progress=None):
        seen["max_calls"] = client.max_calls
        raise InputUnreadable("stop here")

    monkeypatch.setattr("app.investigation.pipeline.run_investigation", spy)
    monkeypatch.setattr("app.investigation.pipeline.transcribe", lambda url, client: "text")
    with pytest.raises(InputUnreadable):
        run_from_image(data_url())
    assert seen["max_calls"] == 5
    assert LLMClient().max_calls == 4
    assert real_run is not spy


def test_api_accepts_exactly_one_of_text_url_image():
    client = TestClient(app)
    response = client.post("/api/investigations", json={"url": "https://example.org/job", "image": data_url()})
    assert response.status_code == 422
    jobs.run_inline = True
    try:
        started = client.post("/api/investigations", json={"image": "data:text/plain;base64,aGVsbG8="})
        status = client.get(f"/api/investigations/{started.json()['id']}").json()
    finally:
        jobs.run_inline = False
    assert status["status"] == "failed"
    assert "PNG, JPEG, or WebP" in status["error"]


class _RecordingClient(ScriptedClient):
    def read_image(self, system, instruction, image_data_url, max_tokens=4000):
        self.sent = image_data_url
        self.instruction = instruction
        return super().read_image(system, instruction, image_data_url, max_tokens)


def test_several_screenshots_are_read_together_in_one_call():
    client = _RecordingClient(_extraction(), transcription=FEE_TEXT, max_calls=5)
    shots = [data_url(), data_url(PNG + b"\x01"), data_url(PNG + b"\x02")]
    result = run_from_image(shots, client, saved_scraper({}))
    assert client.sent == shots
    assert "3 screenshots, in order" in client.instruction
    assert result.decision == "STOP"
    assert client.calls <= 5


def test_more_than_three_screenshots_are_refused():
    with pytest.raises(InputUnreadable, match="at most 3"):
        run_from_image([data_url()] * 4, ScriptedClient(_extraction(), max_calls=5), saved_scraper({}))
    response = TestClient(app).post("/api/investigations", json={"images": [data_url()] * 4})
    assert response.status_code == 422


def test_one_bad_screenshot_among_several_is_named_before_any_call():
    client = ScriptedClient(_extraction(), transcription=FEE_TEXT, max_calls=5)
    with pytest.raises(InputUnreadable, match="not a valid image"):
        run_from_image([data_url(), data_url(b"GIF89a" + b"\x00" * 10)], client, saved_scraper({}))
    assert client.calls == 0
