"""The evidence record: one claim, one source, one observation, one status.

Every conclusion JobXray shows is built from these records.
See spec.md > Components > Backend > app/evidence/ledger.py.
"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["fact", "verified", "unverified", "unknown", "contradiction"]
Reliability = Literal["official", "first-party", "user-provided", "third-party", "unknown"]
SourceType = Literal["pasted_text", "linked_page", "screenshot", "official_page", "none"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceRecord(BaseModel):
    id: str
    claim_id: str
    claim: str
    source_type: SourceType
    source_url: str | None = None
    excerpt: str | None = None
    reliability: Reliability
    observation: str
    supports_or_contradicts: Literal["supports", "contradicts", "neither"] = "neither"
    status: Status
    live_or_cached: Literal["live", "cached"] = "live"
    checked_at: datetime = Field(default_factory=_now)


class Ledger:
    """The evidence list for one investigation, with stable record ids."""

    def __init__(self) -> None:
        self.records: list[EvidenceRecord] = []

    def add(self, **fields) -> EvidenceRecord:
        record = EvidenceRecord(id=f"E{len(self.records) + 1}", **fields)
        self.records.append(record)
        return record

    def get(self, record_id: str) -> EvidenceRecord | None:
        return next((r for r in self.records if r.id == record_id), None)
