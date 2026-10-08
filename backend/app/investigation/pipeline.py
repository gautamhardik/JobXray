"""The investigation sequence. Slice 2: extraction and funnel recognition.

The decision is still a placeholder; slice 3 replaces it with the evidence rules.
See spec.md > Components > Backend > app/investigation/pipeline.py.
"""

from pydantic import BaseModel

from app.investigation.extract import FUNNEL_ORDER, STAGE_LABELS, extract
from app.llm.llm_client import LLMClient


class FunnelStage(BaseModel):
    stage: str
    label: str
    excerpt: str


class Funnel(BaseModel):
    detected: int
    total: int
    stages: list[FunnelStage]


class Claim(BaseModel):
    kind: str
    value: str
    excerpt: str


class InvestigationResult(BaseModel):
    decision: str
    severity: str
    summary: str
    company: str | None
    role: str | None
    funnel: Funnel
    claims: list[Claim]
    dropped_quotes: int
    model_calls: int


def run_investigation(text: str, client: LLMClient | None = None) -> InvestigationResult:
    client = client or LLMClient()
    extraction = extract(text, client)

    stages = [
        FunnelStage(stage=s.stage, label=STAGE_LABELS[s.stage], excerpt=s.excerpt)
        for s in extraction.funnel_stages
    ]
    funnel = Funnel(detected=len(stages), total=len(FUNNEL_ORDER), stages=stages)

    return InvestigationResult(
        decision="VERIFY FIRST",
        severity="Placeholder",
        summary=(
            f"{funnel.detected} of {funnel.total} recruitment-funnel stages detected. "
            "The decision is not built yet."
        ),
        company=extraction.company,
        role=extraction.role,
        funnel=funnel,
        claims=[Claim(**c.model_dump()) for c in extraction.claims],
        dropped_quotes=extraction.dropped_quotes,
        model_calls=client.calls,
    )
