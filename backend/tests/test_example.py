"""Slice 9: the cached example loads without the model or web, and is always labelled cached."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import samples
from app.investigation.extract import Extraction, ExtractedClaim, ExtractedStage
from app.investigation.pipeline import run_investigation
from app.main import app, explain
from app.llm.llm_client import ModelCallError
from tests.helpers import ScriptedClient, saved_scraper


def _live_result():
    extraction = Extraction(
        company="Nexora Technologies",
        role="Business Analyst Internship",
        claims=[ExtractedClaim(kind="fee", value="₹1,999", excerpt="fee ₹1,999")],
        funnel_stages=[ExtractedStage(stage="payment_request", excerpt="fee ₹1,999")],
    )
    return run_investigation("A registration fee ₹1,999 is due.", ScriptedClient(extraction), saved_scraper({}))


@pytest.fixture
def case_file(tmp_path, monkeypatch):
    path = tmp_path / "cached_case.json"
    monkeypatch.setattr(samples, "CASE_FILE", path)
    return path


def test_missing_example_is_a_plain_404(case_file):
    response = TestClient(app).get("/api/example")
    assert response.status_code == 404
    assert "not been saved yet" in response.json()["detail"]


def test_example_is_always_labelled_cached_even_if_saved_as_live(case_file):
    result = _live_result()
    result.cached_at = datetime(2026, 10, 10, tzinfo=timezone.utc)
    assert any(r.live_or_cached == "live" for r in result.evidence)
    case_file.write_text(result.model_dump_json(), encoding="utf-8")

    response = TestClient(app).get("/api/example")
    assert response.status_code == 200
    body = response.json()
    assert body["cached_at"].startswith("2026-10-10")
    assert {r["live_or_cached"] for r in body["evidence"]} == {"cached"}


def test_example_without_a_save_date_is_refused(case_file):
    case_file.write_text(_live_result().model_dump_json(), encoding="utf-8")
    with pytest.raises(ValueError, match="cached_at"):
        samples.load_example()


def test_live_runs_never_carry_a_cached_date():
    assert _live_result().cached_at is None


def test_model_failures_become_plain_messages():
    assert explain(ModelCallError("JobXray could not sign in to OpenRouter. Check the API key.")) == (
        "JobXray could not sign in to OpenRouter. Check the API key."
    )
