"""Call 1: pull claims and recruitment-funnel stages out of the pasted text.

Every excerpt the model returns is checked against the pasted text; excerpts that
are not really there are dropped and counted.
See spec.md > Components > Backend > app/investigation/extract.py.
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.evidence.quotes import quote_in_text
from app.llm.llm_client import LLMClient

PROMPT = (Path(__file__).parent.parent / "prompts" / "extract.md").read_text(encoding="utf-8")

ClaimKind = Literal["company", "role", "stipend", "fee", "application_link", "other"]
StageName = Literal[
    "opportunity",
    "recruiter_contact",
    "private_to_group",
    "group_orientation",
    "training_pitch",
    "payment_request",
]

# Funnel order: the sequence is the investigative signal (scope.md > The Unique Kernel).
FUNNEL_ORDER: list[str] = [
    "opportunity",
    "recruiter_contact",
    "private_to_group",
    "group_orientation",
    "training_pitch",
    "payment_request",
]

STAGE_LABELS = {
    "opportunity": "Opportunity offered",
    "recruiter_contact": "Recruiter contact",
    "private_to_group": "Moved from private chat to a group",
    "group_orientation": "Group orientation or call",
    "training_pitch": "Training or program pitch",
    "payment_request": "Payment request",
}


class ExtractedClaim(BaseModel):
    kind: ClaimKind
    value: str
    excerpt: str


class ExtractedStage(BaseModel):
    stage: StageName
    excerpt: str


class Extraction(BaseModel):
    company: str | None
    role: str | None
    claims: list[ExtractedClaim]
    funnel_stages: list[ExtractedStage]


class CheckedExtraction(BaseModel):
    company: str | None
    role: str | None
    claims: list[ExtractedClaim]
    funnel_stages: list[ExtractedStage]
    dropped_quotes: int


def extract(text: str, client: LLMClient) -> CheckedExtraction:
    raw = client.structured(
        system=PROMPT,
        user=f"<pasted_messages>\n{text}\n</pasted_messages>",
        output_format=Extraction,
    )
    return check_quotes(raw, text)


def check_quotes(raw: Extraction, text: str) -> CheckedExtraction:
    """Keep only claims and stages whose excerpt really appears in the pasted text."""
    claims = [c for c in raw.claims if quote_in_text(c.excerpt, text)]

    stages: list[ExtractedStage] = []
    seen: set[str] = set()
    for stage in raw.funnel_stages:
        if stage.stage not in seen and quote_in_text(stage.excerpt, text):
            stages.append(stage)
            seen.add(stage.stage)
    stages.sort(key=lambda s: FUNNEL_ORDER.index(s.stage))

    dropped = (len(raw.claims) - len(claims)) + sum(
        1 for s in raw.funnel_stages if not quote_in_text(s.excerpt, text)
    )

    # A company or role counts only if a surviving claim backs it with a real quote.
    company = raw.company if any(c.kind == "company" for c in claims) else None
    role = raw.role if any(c.kind == "role" for c in claims) else None

    return CheckedExtraction(
        company=company,
        role=role,
        claims=claims,
        funnel_stages=stages,
        dropped_quotes=dropped,
    )
