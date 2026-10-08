"""Slice 5: a link to a job posting is fetched and investigated like pasted text."""

import pytest
from fastapi.testclient import TestClient

from app.input import InputUnreadable
from app.input.link import read_link
from app.investigation.extract import Extraction, ExtractedClaim, ExtractedStage
from app.investigation.pipeline import run_from_link
from app.main import app
from app.web.scraper import Scraper, is_public_url
from tests.helpers import ScriptedClient, saved_scraper

POSTING = "https://quickjobs.example/jobs/123"
LINKEDIN = "https://www.linkedin.com/jobs/view/123"


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1/", "http://localhost:8000/", "http://10.0.0.5/", "http://169.254.169.254/latest/meta-data"],
)
def test_private_addresses_are_refused_before_any_request(url):
    calls = []
    scraper = Scraper(get=lambda u: calls.append(u), guard=is_public_url)
    with pytest.raises(InputUnreadable):
        read_link(url, scraper)
    assert calls == []


def test_non_http_links_are_refused():
    with pytest.raises(InputUnreadable, match="http"):
        read_link("file:///etc/passwd", saved_scraper({}))


def test_login_wall_gives_the_paste_instead_message():
    with pytest.raises(InputUnreadable, match="Paste the text instead"):
        read_link(LINKEDIN, saved_scraper({LINKEDIN: "linkedin_login.html"}))


def test_unreachable_link_gives_the_paste_instead_message():
    with pytest.raises(InputUnreadable, match="Paste the text instead"):
        read_link(POSTING, saved_scraper({POSTING: 403}))


def test_posting_page_text_is_read():
    page = read_link(POSTING, saved_scraper({POSTING: "posting_board.html"}))
    assert "Registration fee for the training is ₹1,999" in page.text
    assert page.url == POSTING


def _extraction() -> Extraction:
    return Extraction(
        company="Nexora Technologies",
        role="Business Analyst Internship",
        claims=[
            ExtractedClaim(kind="company", value="Nexora Technologies", excerpt="HR team at Nexora Technologies"),
            ExtractedClaim(kind="fee", value="₹1,999", excerpt="Registration fee for the training is ₹1,999"),
        ],
        funnel_stages=[
            ExtractedStage(stage="private_to_group", excerpt="Please join our WhatsApp group for the next round."),
            ExtractedStage(stage="group_orientation", excerpt="group orientation call for all shortlisted candidates"),
            ExtractedStage(stage="payment_request", excerpt="Registration fee for the training is ₹1,999"),
        ],
    )


def test_linked_posting_produces_the_same_stages_as_its_text():
    scraper = saved_scraper({POSTING: "posting_board.html"})
    result = run_from_link(POSTING, ScriptedClient(_extraction()), scraper)
    assert [s.stage for s in result.funnel.stages] == ["private_to_group", "group_orientation", "payment_request"]
    assert result.decision == "STOP"
    assert result.source.source_type == "linked_page"
    fee = next(r for r in result.evidence if r.claim_id == "payment")
    assert fee.source_type == "linked_page"
    assert fee.source_url == POSTING
    assert fee.reliability == "user-provided"  # a linked page is never official by itself
    assert scraper.fetches == 1  # the link counts against the same fetch budget


def test_api_requires_exactly_one_input():
    client = TestClient(app)
    assert client.post("/api/investigations", json={}).status_code == 422
    assert client.post("/api/investigations", json={"text": "a", "url": POSTING}).status_code == 422


def test_api_turns_a_private_link_into_a_plain_422():
    response = TestClient(app).post("/api/investigations", json={"url": "http://127.0.0.1:8000/"})
    assert response.status_code == 422
    assert "private or internal" in response.json()["detail"]
