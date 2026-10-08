"""Slice 8: the self-challenge runs every time, checks only official links, and revises the decision only through new evidence."""

from pathlib import Path

from app.investigation.challenge import ChallengePlan, Hypothesis, NO_FEE_POLICY
from app.investigation.extract import Extraction, ExtractedClaim, ExtractedStage
from app.investigation.observe import Observation, Observations
from app.investigation.pipeline import run_investigation
from app.investigation.plan import PlanProposal
from app.llm.llm_client import LLMClient, ModelCallError
from tests.helpers import ScriptedClient, saved_scraper

FEE_TEXT = (Path(__file__).parent / "fixtures" / "fee_conversation.txt").read_text(encoding="utf-8")
HOME = "https://nexora.example/"
CAREERS = "https://nexora.example/careers"
INTERNSHIPS = "https://nexora.example/careers/internships"
PROCESS = "https://nexora.example/careers/hiring-process"
NEXORA = PlanProposal(official_domain="nexora.example", questions=[])
ROUTES = {
    HOME: "nexora_home.html",
    CAREERS: "nexora_careers_linking_internships.html",
    INTERNSHIPS: "nexora_internships.html",
    PROCESS: "nexora_hiring_process.html",
}


def _extraction(with_fee: bool) -> Extraction:
    claims = [
        ExtractedClaim(kind="company", value="Nexora Technologies", excerpt="Nexora Technologies"),
        ExtractedClaim(kind="role", value="Business Analyst Internship", excerpt="Business Analyst Internship"),
    ]
    if with_fee:
        claims.append(ExtractedClaim(kind="fee", value="₹1,999", excerpt="Registration fee for the training is ₹1,999"))
    return Extraction(
        company="Nexora Technologies",
        role="Business Analyst Internship",
        claims=claims,
        funnel_stages=[ExtractedStage(stage="opportunity", excerpt="shortlisted for our Business Analyst Internship")],
    )


def _links_offered(client_user: str) -> list[str]:
    return [line.split(":")[0] for line in client_user.splitlines() if line.startswith("L")]


def _plan(*hypotheses: Hypothesis) -> ChallengePlan:
    return ChallengePlan(hypotheses=list(hypotheses))


INTERNSHIP_PAGE = Hypothesis(
    question="Is the internship listed on an internships page?",
    kind="alternate_official_source",
    link_ids=["L1"],  # filled per test from the offered list
    alternate_titles=[],
)


def _run(extraction, plan, routes=ROUTES, observations=None, max_fetches=8):
    client = ScriptedClient(extraction, NEXORA, Observations(observations=observations or []), plan)
    scraper = saved_scraper(routes, max_fetches=max_fetches)
    return run_investigation(FEE_TEXT, client, scraper), client, scraper


def _link_id(url: str) -> str:
    """The challenge offers same-site links not yet read, in page order; find the ID for a URL."""
    from app.investigation.pipeline import challenge_links
    from tests.helpers import fetched

    pages = [fetched(HOME, "nexora_home.html"), fetched(CAREERS, "nexora_careers_linking_internships.html")]
    links = challenge_links(pages, "nexora.example")
    return f"L{[l.url for l in links].index(url) + 1}"


def test_challenge_finds_the_role_and_changes_verify_first_to_proceed():
    hypothesis = INTERNSHIP_PAGE.model_copy(update={"link_ids": [_link_id(INTERNSHIPS)]})
    result, client, scraper = _run(_extraction(with_fee=False), _plan(hypothesis))
    assert result.challenge.first_decision == "VERIFY FIRST"
    assert result.decision == "PROCEED"
    assert result.challenge.changed
    assert result.challenge.note == "Assessment changed after contradictory evidence was found."
    found = [r for r in result.evidence if r.observation.startswith("Self-challenge")]
    assert found and found[0].status == "verified" and found[0].source_url == INTERNSHIPS
    assert "Business Analyst Internship" in found[0].excerpt
    assert client.calls == 4
    assert scraper.fetches <= 8


def test_challenge_that_finds_nothing_leaves_the_decision_and_says_so():
    hypothesis = INTERNSHIP_PAGE.model_copy(update={"link_ids": [_link_id(PROCESS)]})
    result, _, _ = _run(_extraction(with_fee=False), _plan(hypothesis))
    assert result.decision == "VERIFY FIRST"
    assert not result.challenge.changed
    assert result.challenge.note == "No credible contradictory evidence found."
    assert result.challenge.hypotheses[0].checked_urls == [PROCESS]


def test_official_no_fee_statement_found_in_challenge_turns_verify_first_into_stop():
    role_listed = Observation(page_id="P2", topic="role", finding="matches", quote="Data Engineer (2+ years, Pune)", explanation="")
    hypothesis = Hypothesis(question="Does the company charge fees?", kind="contradicting_evidence", link_ids=[_link_id(PROCESS)], alternate_titles=[])
    result, _, _ = _run(_extraction(with_fee=True), _plan(hypothesis), observations=[role_listed])
    assert result.challenge.first_decision == "VERIFY FIRST"  # verified role, but a fee is requested
    assert result.decision == "STOP"
    assert result.challenge.changed
    policy = next(r for r in result.evidence if r.claim_id == "recruitment_policy")
    assert policy.status == "contradiction"
    assert "never charges candidates" in policy.excerpt


def test_invented_link_ids_are_ignored():
    hypothesis = INTERNSHIP_PAGE.model_copy(update={"link_ids": ["L99"]})
    result, _, scraper = _run(_extraction(with_fee=False), _plan(hypothesis))
    assert "not an official link" in result.challenge.hypotheses[0].finding
    assert result.decision == "VERIFY FIRST"


def test_low_risk_first_assessment_gets_a_lighter_challenge():
    role_listed = Observation(page_id="P2", topic="role", finding="matches", quote="Data Engineer (2+ years, Pune)", explanation="")
    many = [INTERNSHIP_PAGE.model_copy(update={"link_ids": [_link_id(INTERNSHIPS), _link_id(PROCESS)]}) for _ in range(3)]
    result, _, scraper = _run(_extraction(with_fee=False), _plan(*many), observations=[role_listed])
    assert result.challenge.first_decision == "PROCEED"
    assert len(result.challenge.hypotheses) == 1
    assert len(result.challenge.hypotheses[0].checked_urls) == 1


def test_challenge_runs_even_without_official_links():
    result, client, _ = _run(_extraction(with_fee=True), _plan(INTERNSHIP_PAGE), routes={})
    assert client.calls == 3  # extract, domain proposal, self-challenge (site unreachable, nothing to observe)
    assert result.challenge.note == "No credible contradictory evidence found."
    assert "not an official link" in result.challenge.hypotheses[0].finding


def test_top_evidence_only_cites_existing_records():
    hypothesis = INTERNSHIP_PAGE.model_copy(update={"link_ids": [_link_id(INTERNSHIPS)]})
    result, _, _ = _run(_extraction(with_fee=False), _plan(hypothesis))
    ids = {r.id for r in result.evidence}
    assert set(result.top_evidence) <= ids
    assert len(ids) == len(result.evidence)  # record ids are unique


def test_challenge_failure_keeps_the_first_decision_and_says_so():
    class FailsOnChallenge(ScriptedClient):
        def structured(self, system, user, output_format, max_tokens=8000):
            if output_format is ChallengePlan:
                self.calls += 1
                raise ModelCallError("The free model's request limit was reached. Try again later.")
            return super().structured(system, user, output_format, max_tokens)

    client = FailsOnChallenge(_extraction(with_fee=True), NEXORA, Observations(observations=[]))
    result = run_investigation(FEE_TEXT, client, saved_scraper(ROUTES))
    assert result.decision == "STOP"
    assert result.challenge.note.startswith("The self-challenge could not run")


def test_no_fee_policy_pattern():
    assert NO_FEE_POLICY.search("Nexora Technologies never charges candidates any fee for applications")
    assert NO_FEE_POLICY.search("We do not ask for money or any deposit at any stage")
    assert not NO_FEE_POLICY.search("Registration fee for the training is ₹1,999")
