"""Inputs the first build did not handle: sensitive requests, outdated posts, recruiter
emails and links, posts with several offers, non-offers, too-short pastes, and file links.

Pages are saved fixtures; the model is scripted.
"""

from datetime import date
from types import SimpleNamespace

import pytest

from app.evidence.channels import check_channels
from app.evidence.freshness import check_freshness
from app.evidence.sensitive import asks_for_credentials
from app.evidence.status import OUTDATED_NEXT_STEP, decide
from app.input import InputUnreadable
from app.investigation.extract import Extraction, ExtractedClaim, ExtractedStage
from app.investigation.observe import Observation, Observations
from app.investigation.pipeline import run_investigation
from app.investigation.plan import PlanProposal
from app.web.scraper import Scraper
from tests.helpers import ScriptedClient, _SavedResponse, saved_scraper

HOME = "https://nexora.example/"
CAREERS = "https://nexora.example/careers"
NEXORA = PlanProposal(official_domain="nexora.example", questions=[])
OFFICIAL = {HOME: "nexora_home.html", CAREERS: "nexora_careers_with_role.html"}
ROLE_LISTED = Observations(observations=[Observation(
    page_id="P2", topic="role", finding="matches",
    quote="Business Analyst Internship (6 months, Bengaluru)",
    explanation="The role is in the current openings.",
)])
TODAY = date(2026, 10, 9)

BASE = (
    "Hi, this is Rahul from the HR team at Nexora Technologies.\n"
    "You have been shortlisted for our Business Analyst Internship.\n"
)


def _claim(kind, value, excerpt=None):
    return ExtractedClaim(kind=kind, value=value, excerpt=excerpt or value)


def _extraction(*extra: ExtractedClaim, several: bool = False) -> Extraction:
    return Extraction(
        company="Nexora Technologies",
        role="Business Analyst Internship",
        claims=[
            _claim("company", "Nexora Technologies"),
            _claim("role", "Business Analyst Internship"),
            *extra,
        ],
        funnel_stages=[ExtractedStage(stage="opportunity", excerpt="You have been shortlisted for our Business Analyst Internship.")],
        several_opportunities=several,
    )


def _run(text: str, extraction: Extraction, routes=OFFICIAL):
    client = ScriptedClient(extraction, NEXORA, ROLE_LISTED)
    return run_investigation(text, client, saved_scraper(routes))


def test_verified_role_with_nothing_else_still_proceeds():
    assert _run(BASE, _extraction()).decision == "PROCEED"


# Sensitive information


def test_otp_request_is_stop_even_when_the_role_is_verified():
    text = BASE + "To confirm your seat, share the OTP you receive on your phone.\n"
    result = _run(text, _extraction(_claim("sensitive_request", "OTP", "share the OTP you receive on your phone")))
    assert result.decision == "STOP"
    assert "one-time password" in result.rule
    assert any(r.claim_id == "credentials" for r in result.evidence)


def test_document_request_holds_back_proceed():
    text = BASE + "Send your Aadhaar and PAN card copies today.\n"
    result = _run(text, _extraction(_claim("sensitive_request", "Aadhaar and PAN", "Send your Aadhaar and PAN card copies today.")))
    assert result.decision == "VERIFY FIRST"
    assert "Sensitive documents are requested." in result.rule


def test_a_warning_not_to_share_an_otp_is_not_a_request():
    text = BASE + "Nexora will never ask you to share an OTP or your bank password.\n"
    result = _run(text, _extraction(_claim("sensitive_request", "OTP", "Nexora will never ask you to share an OTP or your bank password.")))
    assert result.decision == "PROCEED"
    assert not asks_for_credentials("We never ask for your OTP.")
    assert not asks_for_credentials("Please share your address and PIN code.")


# Outdated posts


def _c(kind, value, excerpt=None):
    return SimpleNamespace(kind=kind, value=value, excerpt=excerpt or value)


@pytest.mark.parametrize(
    ("claims", "text", "expected"),
    [
        ([], "Google\nRole: SDE Intern\n3y\nEdited", "about 3 years old"),
        ([], "Vidyalai\n2 months ago\nOver 200 applicants", "about 2 months old"),
        ([], "Software Intern\nNo longer accepting applications", "no longer accepting applications"),
        ([_c("deadline", "2023-10-08", "Apply by Oct 08, 2023")], "", "deadline (08 Oct 2023) passed"),
        ([_c("deadline", "15 Aug 2026", "Last date: 15 Aug 2026")], "", "deadline (15 Aug 2026) passed"),
        ([_c("posted_date", "2026-06-01", "Posted on 1 June 2026")], "", "months old"),
        ([_c("eligible_batch", "2023, 2024", "Batch: 2023, 2024")], "", "2023, 2024 batch"),
    ],
    ids=["linkedin-post-age", "linkedin-job-age", "closed", "deadline-iso", "deadline-written", "posted-date", "old-batch"],
)
def test_outdated_posts_are_recognised(claims, text, expected):
    finding = check_freshness(claims, text, TODAY)
    assert finding is not None and expected in finding.observation


@pytest.mark.parametrize(
    ("claims", "text"),
    [
        ([], "Vidyalai\n3 weeks ago\nOver 200 applicants"),
        ([], "I applied 2 months ago and heard nothing back."),
        ([_c("deadline", "12th Jan", "deadline 12th Jan")], ""),
        ([_c("deadline", "2026-11-30", "Apply by 30 Nov 2026")], ""),
        ([_c("eligible_batch", "2025, 2026", "2025 and 2026 grads")], ""),
        ([_c("posted_date", "3y", "3y"), _c("posted_date", "2 days ago", "Reposted 2 days ago")], ""),
    ],
    ids=["recent", "chat-sentence", "no-year", "future-deadline", "current-batch", "most-recent-wins"],
)
def test_current_posts_are_not_called_outdated(claims, text):
    assert check_freshness(claims, text, TODAY) is None


def test_outdated_verified_post_is_verify_first_with_its_own_advice():
    text = BASE + "Posted on 12 Jan 2024\n"
    result = _run(text, _extraction(_claim("posted_date", "2024-01-12", "Posted on 12 Jan 2024")))
    assert result.decision == "VERIFY FIRST"
    assert result.next_step == OUTDATED_NEXT_STEP
    assert any(r.claim_id == "freshness" for r in result.evidence)
    assert "freshness" in [r.claim_id for r in result.evidence if r.id in result.top_evidence]


def test_outdated_alone_is_never_stop():
    assert decide(False, "unknown", cautions=["The post is about 3 years old."], outdated=True).decision == "VERIFY FIRST"


# Recruiter emails and links


def test_personal_email_holds_back_proceed():
    text = BASE + "Reply to rahul.nexora.hr@gmail.com with your resume.\n"
    result = _run(text, _extraction())
    assert result.decision == "VERIFY FIRST"
    channel = next(r for r in result.evidence if r.claim_id == "channel")
    assert "personal email" in channel.observation


def test_lookalike_link_is_impersonation_and_stop():
    text = BASE + "Complete your registration at https://nexora-careers.in/register today.\n"
    result = _run(text, _extraction(_claim("application_link", "https://nexora-careers.in/register")))
    assert result.decision == "STOP"
    identity = next(r for r in result.evidence if r.claim_id == "identity")
    assert identity.status == "contradiction"


def test_form_link_holds_back_proceed():
    text = BASE + "Fill this form to continue: https://forms.gle/AbCdEf123\n"
    result = _run(text, _extraction(_claim("application_link", "https://forms.gle/AbCdEf123")))
    assert result.decision == "VERIFY FIRST"


@pytest.mark.parametrize(
    "text",
    [
        "Apply here: https://www.linkedin.com/jobs/view/123456789",
        "Apply on https://nexora.example/careers/ba-intern",
        "Mail careers@nexora.example for details.",
        "Join https://chat.whatsapp.com/abc for updates.",
        "Apply at https://boards.greenhouse.io/nexora/jobs/1",
    ],
    ids=["job-board", "official-site", "official-email", "chat-group", "ats"],
)
def test_ordinary_channels_raise_nothing(text):
    assert check_channels(text, "Nexora Technologies", "nexora.example", []) == []


# Inputs that are not an offer at all


def test_too_short_paste_is_refused_before_any_model_call():
    client = ScriptedClient(_extraction())
    with pytest.raises(InputUnreadable, match="too short"):
        run_investigation("hello there", client, saved_scraper({}))
    assert client.calls == 0


def test_text_with_no_offer_in_it_says_so():
    nothing = Extraction(company=None, role=None, claims=[], funnel_stages=[])
    client = ScriptedClient(nothing)
    with pytest.raises(InputUnreadable, match="didn't find a job or internship offer"):
        run_investigation("What is the weather like in Pune this week?", client, saved_scraper({}))
    assert client.calls == 1


def test_post_with_several_offers_says_which_one_was_checked():
    result = _run(BASE, _extraction(several=True))
    assert result.notes and "Business Analyst Internship at Nexora Technologies" in result.notes[0]


# Links to files


class _FileResponse(_SavedResponse):
    def __init__(self, url, content_type):
        super().__init__(url, "<html></html>")
        self.headers = {"content-type": content_type}


@pytest.mark.parametrize(("content_type", "word"), [("application/pdf", "PDF"), ("image/png", "image"), ("application/zip", "file")])
def test_file_links_are_named_not_crashed_on(content_type, word):
    scraper = Scraper(get=lambda url: _FileResponse(url, content_type), guard=lambda url: (True, ""))
    page = scraper.fetch("https://example.org/offer-letter")
    assert not page.ok
    assert word in page.failure


class _MissesOnce(ScriptedClient):
    """Answers the first extraction with nothing, like a free model that misses."""

    def structured(self, system, user, output_format, max_tokens=8000):
        answer = super().structured(system, user, output_format, max_tokens)
        if output_format is Extraction and self.calls == 1:
            return Extraction(company=None, role=None, claims=[], funnel_stages=[])
        return answer


def test_an_empty_answer_on_a_job_post_is_retried_not_called_a_non_offer():
    client = _MissesOnce(_extraction(), NEXORA, ROLE_LISTED)
    result = run_investigation(BASE, client, saved_scraper(OFFICIAL))
    assert result.company == "Nexora Technologies"
    assert result.decision == "PROCEED"
    assert client.max_calls == 5  # the retry does not eat the self-challenge's call
