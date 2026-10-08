"""Run one real investigation and save it as the cached example.

Usage (from backend/): python -m scripts.save_example tests/fixtures/realworld/india_internship_upi.txt
Uses real model calls and real fetches. Every record is saved as cached.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

from app.investigation.pipeline import run_investigation
from app.samples import CASE_FILE


def main(path: str) -> None:
    text = Path(path).read_text(encoding="utf-8")
    result = run_investigation(text)
    result.cached_at = datetime.now(timezone.utc)
    for record in result.evidence:
        record.live_or_cached = "cached"
    CASE_FILE.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(f"Saved {CASE_FILE}: {result.decision} · {result.severity}, {len(result.evidence)} records, "
          f"{result.model_calls} model calls, {result.fetches} fetches")


if __name__ == "__main__":
    main(sys.argv[1])
