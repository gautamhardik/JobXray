"""Slice 5: a link to a job posting is fetched and investigated like pasted text."""

import pytest
from fastapi.testclient import TestClient

from app.input import InputUnreadable
from app.input.link import public_view, read_link
from app.investigation.extract import Extraction, ExtractedClaim, ExtractedStage
from app.investigation.pipeline import run_from_link
from app.main import app, jobs
from app.web.scraper import Scraper, is_public_url
from tests.helpers import ScriptedClient, saved_scraper

POSTING = "https://quickjobs.example/jobs/123"
LINKEDIN = "https://www.linkedin.com/jobs/view/business-analyst-internship-at-nexora-4123456789"
GUEST_JOB = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4123456789"
SHORT = "https://lnkd.in/dAbC123"


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


def test_login_wall_asks_for_a_screenshot_after_trying_the_guest_view():
    scraper = saved_scraper({GUEST_JOB: 404, LINKEDIN: "linkedin_login.html"})
    with pytest.raises(InputUnreadable, match="Upload a screenshot"):
        read_link(LINKEDIN, scraper)
    assert scraper.fetches == 2  # the public guest view first, then the link as given


def test_unreachable_link_asks_for_a_screenshot():
    with pytest.raises(InputUnreadable, match="Upload a screenshot"):
        read_link(POSTING, saved_scraper({POSTING: 403}))


@pytest.mark.parametrize(
    ("url", "view"),
    [
        ("https://in.linkedin.com/jobs/view/business-analyst-internship-at-nexora-4467410588", "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4467410588"),
        ("https://www.linkedin.com/jobs/view/4467410588/?trk=public", "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4467410588"),
        ("https://www.linkedin.com/jobs/search?keywords=intern&currentJobId=4444262929", "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4444262929"),
        ("https://www.linkedin.com/posts/someone_hiring-activity-7085453312795287553-Grgm", "https://www.linkedin.com/embed/feed/update/urn:li:activity:7085453312795287553"),
        ("https://www.linkedin.com/feed/update/urn:li:activity:7000685626786254849/", "https://www.linkedin.com/embed/feed/update/urn:li:activity:7000685626786254849"),
        ("https://www.linkedin.com/feed/update/urn%3Ali%3AugcPost%3A7000685626786254849", "https://www.linkedin.com/embed/feed/update/urn:li:ugcPost:7000685626786254849"),
        ("https://www.linkedin.com/in/someone", None),
        (POSTING, None),
    ],
    ids=["job-slug", "job-id", "job-search", "post", "feed-update", "encoded-urn", "profile", "other-site"],
)
def test_linkedin_links_map_to_their_public_view(url, view):
    assert public_view(url) == view


def test_linkedin_job_is_read_through_the_guest_view_without_sign_in_boxes():
    scraper = saved_scraper({GUEST_JOB: "linkedin_guest_job.html"})
    page = read_link(LINKEDIN, scraper)
    assert "gather requirements from stakeholders" in page.text
    assert "Email or phone" not in page.text and "Sign in" not in page.text
    assert page.url == LINKEDIN  # the evidence keeps the link the person gave
    assert scraper.fetches == 1


def test_short_link_is_followed_to_its_target():
    scraper = saved_scraper({SHORT: "lnkd_interstitial.html", POSTING: "posting_board.html"})
    page = read_link(SHORT, scraper)
    assert "Registration fee for the training is ₹1,999" in page.text
    assert page.url == POSTING


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


def test_api_reports_a_private_link_as_a_plain_failure(monkeypatch):
    monkeypatch.setattr(jobs, "run_inline", True)
    client = TestClient(app)
    started = client.post("/api/investigations", json={"url": "http://127.0.0.1:8000/"})
    assert started.status_code == 202
    status = client.get(f"/api/investigations/{started.json()['id']}").json()
    assert status["status"] == "failed"
    assert "private or internal" in status["error"]
    assert status["result"] is None
