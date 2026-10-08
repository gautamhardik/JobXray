"""Slice 7: the step list moves pending -> active -> done in order, and polling sees it."""

import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.investigation.extract import Extraction, ExtractedClaim, ExtractedStage
from app.investigation.pipeline import run_investigation
from app.investigation.progress import Progress
from app.main import app, explain, jobs
from tests.helpers import ScriptedClient, saved_scraper

FEE_TEXT = (Path(__file__).parent / "fixtures" / "fee_conversation.txt").read_text(encoding="utf-8")


def _extraction() -> Extraction:
    return Extraction(
        company="Nexora Technologies",
        role="Business Analyst Internship",
        claims=[ExtractedClaim(kind="company", value="Nexora Technologies", excerpt="Nexora Technologies")],
        funnel_stages=[ExtractedStage(stage="opportunity", excerpt="shortlisted for our Business Analyst Internship")],
    )


def test_steps_finish_in_order_with_notes():
    progress = Progress("text")
    run_investigation(FEE_TEXT, ScriptedClient(_extraction()), saved_scraper({}), progress=progress)
    steps = {s.key: s for s in progress.snapshot()}
    assert [s.key for s in progress.snapshot()] == ["read", "extract", "funnel", "domain", "official_pages", "challenge", "decide"]
    assert steps["read"].state == "done"
    assert steps["extract"].state == "done"
    assert steps["funnel"].note == "1 of 6 stages"
    assert steps["domain"].state == "skipped"  # no domain proposed by the scripted model
    assert steps["decide"].state == "done"
    assert "VERIFY FIRST" in steps["decide"].note


def test_polling_sees_active_then_done():
    def slow(progress):
        progress.start("extract")
        time.sleep(0.3)
        return run_investigation(FEE_TEXT, ScriptedClient(_extraction()), saved_scraper({}), progress=progress)

    job_id = jobs.start(Progress("text"), slow, explain)
    time.sleep(0.1)
    midway = jobs.get(job_id)
    assert midway.status == "running"
    assert midway.result is None
    assert next(s for s in midway.steps if s.key == "extract").state == "active"

    deadline = time.time() + 5
    while jobs.get(job_id).status == "running" and time.time() < deadline:
        time.sleep(0.05)
    final = jobs.get(job_id)
    assert final.status == "done"
    assert final.result is not None
    assert all(s.state in ("done", "skipped") for s in final.steps)


def test_unknown_id_is_404_with_plain_message():
    response = TestClient(app).get("/api/investigations/doesnotexist")
    assert response.status_code == 404
    assert response.json()["detail"] == "This investigation was interrupted. Start again."


def test_unexpected_errors_never_leak_internals():
    assert explain(KeyError("secret internals")) == "Analysis could not finish. Try again or view the example."
