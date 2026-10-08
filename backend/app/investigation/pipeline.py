"""The investigation sequence.

Slice 3: extraction (call 1) feeds the evidence ledger, and the decision comes
from the rules in app/evidence/status.py, not from the model.
See spec.md > Components > Backend > app/investigation/pipeline.py.
"""

from pydantic import BaseModel

from app.evidence.ledger import EvidenceRecord, Ledger
from app.evidence.status import OfficialCheck, decide, opportunity_status, top_evidence
from app.investigation.extract import FUNNEL_ORDER, STAGE_LABELS, CheckedExtraction, extract
from app.llm.llm_client import LLMClient

CLAIM_LABELS = {
    "company": "Company",
    "role": "Role",
    "stipend": "Stipend or pay",
    "fee": "Payment requested",
    "application_link": "Application link",
    "other": "Claim",
}


class FunnelStage(BaseModel):
    stage: str
    label: str
    excerpt: str


class Funnel(BaseModel):
    detected: int
    total: int
    stages: list[FunnelStage]


class InvestigationResult(BaseModel):
    decision: str
    severity: str
    next_step: str
    rule: str
    summary: str
    company: str | None
    role: str | None
    funnel: Funnel
    evidence: list[EvidenceRecord]
    top_evidence: list[str]
    dropped_quotes: int
    model_calls: int


def run_investigation(text: str, client: LLMClient | None = None) -> InvestigationResult:
    client = client or LLMClient()
    extraction = extract(text, client)

    ledger = Ledger()
    payment_requested = record_pasted_facts(ledger, extraction)

    check = OfficialCheck()  # slice 4 fills this from the company's official site
    status = opportunity_status(check)
    ledger.add(
        claim_id="opportunity",
        claim=opportunity_claim(extraction),
        source_type="none",
        reliability="unknown",
        observation=(
            "The company's official website has not been checked."
            if extraction.company
            else "No company is named, so no official source can be checked."
        ),
        status=status,
    )

    result = decide(payment_requested=payment_requested, opportunity=status)
    top = top_evidence(ledger.records, result.decision)

    stages = [
        FunnelStage(stage=s.stage, label=STAGE_LABELS[s.stage], excerpt=s.excerpt)
        for s in extraction.funnel_stages
    ]
    funnel = Funnel(detected=len(stages), total=len(FUNNEL_ORDER), stages=stages)

    return InvestigationResult(
        decision=result.decision,
        severity=result.severity,
        next_step=result.next_step,
        rule=result.rule,
        summary=f"{result.rule} {funnel.detected} of {funnel.total} recruitment-funnel stages detected.",
        company=extraction.company,
        role=extraction.role,
        funnel=funnel,
        evidence=ledger.records,
        top_evidence=[r.id for r in top],
        dropped_quotes=extraction.dropped_quotes,
        model_calls=client.calls,
    )


def record_pasted_facts(ledger: Ledger, extraction: CheckedExtraction) -> bool:
    """Every surviving claim becomes a Fact from the pasted text. Returns whether a payment is requested."""
    payment_requested = False
    other_count = 0
    for claim in extraction.claims:
        if claim.kind == "fee":
            claim_id = "payment"
            payment_requested = True
        elif claim.kind == "other":
            other_count += 1
            claim_id = f"other-{other_count}"
        else:
            claim_id = claim.kind
        ledger.add(
            claim_id=claim_id,
            claim=f"{CLAIM_LABELS[claim.kind]}: {claim.value}",
            source_type="pasted_text",
            excerpt=claim.excerpt,
            reliability="user-provided",
            observation="Stated in the text you provided.",
            status="fact",
        )

    # A payment-request stage with no fee claim still counts as a payment Fact.
    if not payment_requested:
        stage = next((s for s in extraction.funnel_stages if s.stage == "payment_request"), None)
        if stage:
            payment_requested = True
            ledger.add(
                claim_id="payment",
                claim="Payment requested",
                source_type="pasted_text",
                excerpt=stage.excerpt,
                reliability="user-provided",
                observation="Stated in the text you provided.",
                status="fact",
            )
    return payment_requested


def opportunity_claim(extraction: CheckedExtraction) -> str:
    role = extraction.role or "This opportunity"
    company = extraction.company or "the named company"
    return f"{role} is offered by {company}"
