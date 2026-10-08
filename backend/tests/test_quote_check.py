"""Quote check and extraction filtering, with the model call stubbed out."""

from pathlib import Path

from app.evidence.quotes import quote_in_text
from app.investigation.extract import Extraction, ExtractedClaim, ExtractedStage, check_quotes
from app.investigation.pipeline import run_investigation
from app.llm.llm_client import LLMClient

FEE_TEXT = (Path(__file__).parent / "fixtures" / "fee_conversation.txt").read_text(encoding="utf-8")


def test_present_excerpt_is_kept():
    assert quote_in_text("Registration fee for the training is ₹1,999", FEE_TEXT)


def test_whitespace_and_case_are_normalized():
    assert quote_in_text("please   JOIN our whatsapp group", FEE_TEXT)


def test_altered_excerpt_is_dropped():
    assert not quote_in_text("Registration fee for the training is ₹999", FEE_TEXT)


def test_empty_excerpt_is_dropped():
    assert not quote_in_text("   ", FEE_TEXT)


def _raw_extraction() -> Extraction:
    return Extraction(
        company="Nexora Technologies",
        role="Business Analyst Internship",
        claims=[
            ExtractedClaim(kind="company", value="Nexora Technologies", excerpt="HR team at Nexora Technologies"),
            ExtractedClaim(kind="role", value="Business Analyst Internship", excerpt="our Business Analyst Internship"),
            ExtractedClaim(kind="fee", value="₹1,999", excerpt="Registration fee for the training is ₹1,999"),
            ExtractedClaim(kind="stipend", value="₹50,000", excerpt="stipend ₹50,000/month"),  # invented
        ],
        funnel_stages=[
            ExtractedStage(stage="payment_request", excerpt="Registration fee for the training is ₹1,999"),
            ExtractedStage(stage="private_to_group", excerpt="Please join our WhatsApp group for the next round"),
            ExtractedStage(stage="opportunity", excerpt="You have been shortlisted for our Business Analyst Internship"),
            ExtractedStage(stage="group_orientation", excerpt="a private one-on-one interview"),  # invented
            ExtractedStage(stage="private_to_group", excerpt="join our WhatsApp group"),  # duplicate
        ],
    )


def test_check_quotes_drops_invented_excerpts_and_orders_stages():
    checked = check_quotes(_raw_extraction(), FEE_TEXT)
    assert [c.kind for c in checked.claims] == ["company", "role", "fee"]
    assert [s.stage for s in checked.funnel_stages] == ["opportunity", "private_to_group", "payment_request"]
    assert checked.dropped_quotes == 2
    assert checked.company == "Nexora Technologies"


def test_company_without_a_real_quote_becomes_unknown():
    raw = _raw_extraction()
    raw.claims[0].excerpt = "Nexora Technologies Pvt Ltd official"  # not in the text
    assert check_quotes(raw, FEE_TEXT).company is None


class _StubClient(LLMClient):
    def structured(self, system, user, output_format, max_tokens=16000):
        self.calls += 1
        return _raw_extraction()


def test_pipeline_uses_one_model_call_and_reports_the_funnel():
    client = _StubClient()
    result = run_investigation(FEE_TEXT, client)
    assert client.calls == 1
    assert result.model_calls == 1
    assert result.funnel.detected == 3
    assert result.funnel.total == 6
    assert result.funnel.stages[0].label == "Opportunity offered"
