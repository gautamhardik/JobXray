"""Slice 4: official domain check, careers pages, observations, and the resulting statuses.

Pages are saved fixtures; the model is scripted. Expected statuses follow
spec.md > Decisions and Open Issues > Derived implementation decisions.
"""

from pathlib import Path

from app.investigation.extract import Extraction, ExtractedClaim, ExtractedStage
from app.investigation.observe import Observation, Observations, check_observation_quotes
from app.investigation.pipeline import run_investigation
from app.investigation.plan import PlanProposal, check_domain
from tests.helpers import ScriptedClient, fetched, saved_scraper

FEE_TEXT = (Path(__file__).parent / "fixtures" / "fee_conversation.txt").read_text(encoding="utf-8")

HOME = "https://nexora.example/"
CAREERS = "https://nexora.example/careers"
NEXORA = PlanProposal(official_domain="nexora.example", questions=[])


def _extraction(with_fee: bool = True) -> Extraction:
    claims = [
        ExtractedClaim(kind="company", value="Nexora Technologies", excerpt="Nexora Technologies"),
        ExtractedClaim(kind="role", value="Business Analyst Internship", excerpt="Business Analyst Internship"),
    ]
    stages = [ExtractedStage(stage="opportunity", excerpt="shortlisted for our Business Analyst Internship")]
    if with_fee:
        claims.append(ExtractedClaim(kind="fee", value="₹1,999", excerpt="Registration fee for the training is ₹1,999"))
    return Extraction(company="Nexora Technologies", role="Business Analyst Internship", claims=claims, funnel_stages=stages)


ROLE_LISTED = Observation(
    page_id="P2", topic="role", finding="matches",
    quote="Business Analyst Internship (6 months, Bengaluru)",
    explanation="The role is in the current openings.",
)
FEE_POLICY = Observation(
    page_id="P2", topic="recruitment_policy", finding="conflicts",
    quote="Nexora Technologies never charges candidates any fee at any stage of recruitment",
    explanation="The company says it never charges candidates.",
)


def _record(result, claim_id):
    return next(r for r in result.evidence if r.claim_id == claim_id)


# Domain check


def test_real_homepage_with_several_signals_is_established():
    check = check_domain("nexora.example", "Nexora Technologies", saved_scraper({HOME: "nexora_home.html"}))
    assert check.established
    assert all(s.passed for s in check.signals)


def test_lookalike_domain_is_refused_without_fetching():
    scraper = saved_scraper({})
    check = check_domain("nexora-careers.in", "Nexora Technologies", scraper)
    assert not check.established
    assert scraper.fetches == 0


def test_name_only_page_is_not_established():
    check = check_domain("nexorainfo.example", "Nexora Technologies", saved_scraper({"https://nexorainfo.example/": "name_only.html"}))
    assert not check.established
    assert next(s for s in check.signals if s.name == "Company identity on the site").passed


def test_unreachable_homepage_is_not_established():
    check = check_domain("nexora.example", "Nexora Technologies", saved_scraper({}))
    assert not check.established


# Statuses from the official pages


def test_role_listed_on_official_careers_page_is_verified_and_proceed_without_fee():
    client = ScriptedClient(_extraction(with_fee=False), NEXORA, Observations(observations=[ROLE_LISTED]))
    result = run_investigation(FEE_TEXT, client, saved_scraper({HOME: "nexora_home.html", CAREERS: "nexora_careers_with_role.html"}))
    record = _record(result, "opportunity")
    assert record.status == "verified"
    assert record.source_url == CAREERS
    assert record.reliability == "official"
    assert result.decision == "PROCEED"
    assert client.calls == 4  # extract, domain, observe, self-challenge


def test_inspected_careers_page_without_the_role_is_unverified_and_fee_means_stop():
    client = ScriptedClient(_extraction(), NEXORA, Observations(observations=[]))
    result = run_investigation(FEE_TEXT, client, saved_scraper({HOME: "nexora_home.html", CAREERS: "nexora_careers_without_role.html"}))
    assert _record(result, "opportunity").status == "unverified"
    assert result.decision == "STOP"


def test_blocked_careers_page_is_unknown_not_unverified():
    client = ScriptedClient(_extraction(with_fee=False), NEXORA, Observations(observations=[]))
    result = run_investigation(FEE_TEXT, client, saved_scraper({HOME: "nexora_home.html", CAREERS: 403}))
    assert _record(result, "opportunity").status == "unknown"
    assert result.decision == "VERIFY FIRST"
    assert client.calls == 3  # extract, domain, self-challenge: no page to observe, so no observe call


def test_javascript_only_careers_page_is_unknown():
    client = ScriptedClient(_extraction(with_fee=False), NEXORA, Observations(observations=[]))
    result = run_investigation(FEE_TEXT, client, saved_scraper({HOME: "nexora_home.html", CAREERS: "js_careers.html"}))
    assert _record(result, "opportunity").status == "unknown"


def test_lookalike_proposal_makes_the_official_check_unknown():
    client = ScriptedClient(_extraction(), PlanProposal(official_domain="nexora-careers.in", questions=[]))
    scraper = saved_scraper({})
    result = run_investigation(FEE_TEXT, client, scraper)
    assert _record(result, "official_domain").status == "unknown"
    assert _record(result, "opportunity").status == "unknown"
    assert scraper.fetches == 0
    assert result.decision == "STOP"  # the fee is still a Fact and nothing is verified


def test_official_no_fee_policy_contradicts_the_fee_and_means_stop():
    client = ScriptedClient(_extraction(), NEXORA, Observations(observations=[ROLE_LISTED, FEE_POLICY]))
    result = run_investigation(FEE_TEXT, client, saved_scraper({HOME: "nexora_home.html", CAREERS: "nexora_careers_with_role.html"}))
    policy = _record(result, "recruitment_policy")
    assert policy.status == "contradiction"
    assert result.decision == "STOP"
    assert result.top_evidence[0] == policy.id


def test_fetches_stay_within_budget():
    client = ScriptedClient(_extraction(), NEXORA, Observations(observations=[]))
    scraper = saved_scraper({HOME: "nexora_home.html", CAREERS: "nexora_careers_without_role.html"}, max_fetches=1)
    result = run_investigation(FEE_TEXT, client, scraper)
    assert scraper.fetches == 1
    assert _record(result, "opportunity").status == "unknown"


# Quote check on page observations


def test_observation_quote_not_on_the_page_is_dropped():
    pages = [fetched(HOME, "nexora_home.html"), fetched(CAREERS, "nexora_careers_without_role.html")]
    invented = Observation(page_id="P2", topic="role", finding="matches", quote="Business Analyst Internship (6 months, Bengaluru)", explanation="")
    checked = check_observation_quotes(Observations(observations=[invented]), pages)
    assert checked.observations == []
    assert checked.dropped_quotes == 1


def test_careers_kept_off_the_homepage_are_found_at_the_usual_address():
    scraper = saved_scraper({
        HOME: "nexora_home_no_careers_link.html",
        "https://careers.nexora.example/": "nexora_careers_with_role.html",
    })
    check = check_domain("nexora.example", "Nexora Technologies", scraper)
    assert check.established
    assert [p.url for p in check.probed_careers] == ["https://careers.nexora.example/"]


def test_probed_careers_page_is_read_without_fetching_it_again():
    client = ScriptedClient(_extraction(with_fee=False), NEXORA, Observations(observations=[ROLE_LISTED]))
    scraper = saved_scraper({
        HOME: "nexora_home_no_careers_link.html",
        "https://careers.nexora.example/": "nexora_careers_with_role.html",
    })
    result = run_investigation(FEE_TEXT, client, scraper)
    assert _record(result, "opportunity").status == "verified"
    assert result.decision == "PROCEED"


def test_department_words_in_the_company_name_are_not_required_on_the_site():
    from app.investigation.plan import _company_tokens

    assert _company_tokens("Amazon HR") == ["amazon"]
    assert _company_tokens("Infosys Talent Acquisition Team") == ["infosys"]
    check = check_domain("nexora.example", "Nexora HR Team", saved_scraper({HOME: "nexora_home.html"}))
    assert check.established
