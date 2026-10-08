"""Status and decision rules. Plain Python, no model.

The same evidence always produces the same status and decision.
See spec.md > Decisions and Open Issues > Derived implementation decisions.
"""

from typing import Literal

from pydantic import BaseModel

from app.evidence.ledger import EvidenceRecord, Status

Decision = Literal["STOP", "VERIFY FIRST", "PROCEED"]

SEVERITY: dict[str, str] = {
    "STOP": "Critical concern",
    "VERIFY FIRST": "Significant uncertainty",
    "PROCEED": "Low concern",
}

NEXT_STEP: dict[str, str] = {
    "STOP": (
        "Do not pay or share documents. Verify the opportunity directly through the "
        "company's official careers page or recruitment contact, found by you, not from the message."
    ),
    "VERIFY FIRST": (
        "Don't pay or share sensitive information yet. Confirm the opportunity through "
        "the company's official website before you continue."
    ),
    "PROCEED": "The opportunity matches the company's official listing. Apply through that official channel.",
}


class OfficialCheck(BaseModel):
    """What the official-source check found. Empty until slice 4 runs it."""

    domain_established: bool = False
    relevant_page_inspected: bool = False
    supports_claim: bool = False
    contradicts_claim: bool = False


def opportunity_status(check: OfficialCheck) -> Status:
    """Status of the claim "this opportunity is offered by this company".

    Unverified only when the relevant official page was actually inspected.
    Anything that could not be established or reached is Unknown, never fake.
    """
    if not check.domain_established:
        return "unknown"
    if check.contradicts_claim:
        return "contradiction"
    if check.supports_claim:
        return "verified"
    if check.relevant_page_inspected:
        return "unverified"
    return "unknown"


class DecisionResult(BaseModel):
    decision: Decision
    severity: str
    next_step: str
    rule: str


def decide(
    payment_requested: bool,
    opportunity: Status,
    direct_contradiction_on_payment_or_identity: bool = False,
) -> DecisionResult:
    """Turn evidence statuses into Proceed, Verify First, or Stop."""
    if direct_contradiction_on_payment_or_identity:
        decision, rule = "STOP", "An official source directly contradicts a payment or identity claim."
    elif payment_requested and opportunity != "verified":
        decision, rule = "STOP", "A payment is requested and the opportunity is not verified by an official source."
    elif opportunity == "verified" and not payment_requested:
        decision, rule = "PROCEED", "An official source confirms the opportunity, with no payment request."
    else:
        decision, rule = "VERIFY FIRST", "The opportunity could not be confirmed by an official source."
    return DecisionResult(decision=decision, severity=SEVERITY[decision], next_step=NEXT_STEP[decision], rule=rule)


def _weight(record: EvidenceRecord) -> int:
    if record.status == "contradiction":
        return 0
    if record.claim_id == "payment":
        return 1
    if record.claim_id == "opportunity":
        return 2
    if record.status in ("unverified", "unknown"):
        return 3
    if record.status == "verified":
        return 4
    return 5  # other facts from the pasted text


def top_evidence(records: list[EvidenceRecord], decision: Decision, limit: int = 3) -> list[EvidenceRecord]:
    """The 2-3 records that most directly drove the decision."""
    if decision == "PROCEED":
        ranked = sorted(records, key=lambda r: (r.status != "verified", int(r.id[1:])))
    else:
        ranked = sorted(records, key=lambda r: (_weight(r), int(r.id[1:])))
    return ranked[:limit]
