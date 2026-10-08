"""Status and decision rules, one test per rule (spec.md > Derived implementation decisions)."""

from pathlib import Path

from app.evidence.ledger import Ledger
from app.evidence.status import OfficialCheck, decide, opportunity_status, top_evidence
from app.investigation.extract import Extraction, ExtractedClaim, ExtractedStage
from app.investigation.pipeline import run_investigation
from tests.helpers import ScriptedClient, saved_scraper

FEE_TEXT = (Path(__file__).parent / "fixtures" / "fee_conversation.txt").read_text(encoding="utf-8")


# Opportunity status


def test_no_official_domain_is_unknown():
    assert opportunity_status(OfficialCheck()) == "unknown"


def test_domain_but_page_not_inspected_is_unknown_not_unverified():
    assert opportunity_status(OfficialCheck(domain_established=True)) == "unknown"


def test_inspected_page_without_the_claim_is_unverified():
    check = OfficialCheck(domain_established=True, relevant_page_inspected=True)
    assert opportunity_status(check) == "unverified"


def test_official_page_confirming_the_claim_is_verified():
    check = OfficialCheck(domain_established=True, relevant_page_inspected=True, supports_claim=True)
    assert opportunity_status(check) == "verified"


def test_official_page_conflicting_with_the_claim_is_a_contradiction():
    check = OfficialCheck(domain_established=True, relevant_page_inspected=True, contradicts_claim=True)
    assert opportunity_status(check) == "contradiction"


def test_contradiction_outranks_support():
    check = OfficialCheck(domain_established=True, supports_claim=True, contradicts_claim=True)
    assert opportunity_status(check) == "contradiction"


# Decisions


def test_payment_and_unverified_opportunity_is_stop():
    result = decide(payment_requested=True, opportunity="unverified")
    assert (result.decision, result.severity) == ("STOP", "Critical concern")


def test_payment_and_unknown_opportunity_is_stop():
    assert decide(payment_requested=True, opportunity="unknown").decision == "STOP"


def test_direct_contradiction_on_payment_or_identity_is_stop_even_if_verified():
    result = decide(False, "verified", direct_contradiction_on_payment_or_identity=True)
    assert result.decision == "STOP"


def test_no_payment_and_unknown_is_verify_first():
    result = decide(payment_requested=False, opportunity="unknown")
    assert (result.decision, result.severity) == ("VERIFY FIRST", "Significant uncertainty")


def test_no_payment_and_unverified_is_verify_first():
    assert decide(payment_requested=False, opportunity="unverified").decision == "VERIFY FIRST"


def test_verified_with_no_payment_is_proceed():
    result = decide(payment_requested=False, opportunity="verified")
    assert (result.decision, result.severity) == ("PROCEED", "Low concern")


def test_verified_but_payment_requested_is_not_proceed():
    assert decide(payment_requested=True, opportunity="verified").decision == "VERIFY FIRST"


# Top evidence


def test_stop_puts_the_payment_fact_and_opportunity_first():
    ledger = Ledger()
    ledger.add(claim_id="company", claim="Company: X", source_type="pasted_text", reliability="user-provided", observation="", status="fact")
    ledger.add(claim_id="payment", claim="Fee", source_type="pasted_text", reliability="user-provided", observation="", status="fact")
    ledger.add(claim_id="opportunity", claim="Role at X", source_type="none", reliability="unknown", observation="", status="unknown")
    top = top_evidence(ledger.records, "STOP")
    assert [r.claim_id for r in top] == ["payment", "opportunity", "company"]


# Pipeline, with the model stubbed


def _extraction(with_fee: bool) -> Extraction:
    claims = [
        ExtractedClaim(kind="company", value="Nexora Technologies", excerpt="Nexora Technologies"),
        ExtractedClaim(kind="role", value="Business Analyst Internship", excerpt="Business Analyst Internship"),
    ]
    stages = [ExtractedStage(stage="opportunity", excerpt="shortlisted for our Business Analyst Internship")]
    if with_fee:
        claims.append(ExtractedClaim(kind="fee", value="₹1,999", excerpt="Registration fee for the training is ₹1,999"))
        stages.append(ExtractedStage(stage="payment_request", excerpt="Registration fee for the training is ₹1,999"))
    return Extraction(company="Nexora Technologies", role="Business Analyst Internship", claims=claims, funnel_stages=stages)


def _run(extraction: Extraction):
    return run_investigation(FEE_TEXT, ScriptedClient(extraction), saved_scraper({}))


def test_fee_message_is_stop_with_the_fee_as_top_evidence():
    result = _run(_extraction(with_fee=True))
    assert result.decision == "STOP"
    assert result.severity == "Critical concern"
    top = [next(r for r in result.evidence if r.id == i) for i in result.top_evidence]
    assert top[0].claim_id == "payment"
    assert top[0].status == "fact"
    assert top[0].reliability == "user-provided"
    assert top[1].claim_id == "opportunity"
    assert top[1].status == "unknown"


def test_no_fee_message_is_verify_first():
    result = _run(_extraction(with_fee=False))
    assert result.decision == "VERIFY FIRST"
    assert result.severity == "Significant uncertainty"


def test_payment_stage_without_fee_claim_still_counts_as_payment():
    extraction = _extraction(with_fee=False)
    extraction.funnel_stages.append(
        ExtractedStage(stage="payment_request", excerpt="Registration fee for the training is ₹1,999")
    )
    result = _run(extraction)
    assert result.decision == "STOP"
