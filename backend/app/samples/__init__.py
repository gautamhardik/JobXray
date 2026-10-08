"""The saved example investigation: a real run, always labelled Cached.

See spec.md > Components > Backend > app/samples/cached_case.json.
"""

from pathlib import Path

from app.investigation.pipeline import InvestigationResult

CASE_FILE = Path(__file__).parent / "cached_case.json"


def load_example() -> InvestigationResult | None:
    """The saved example, with every record marked cached. None if no example has been saved yet."""
    if not CASE_FILE.exists():
        return None
    result = InvestigationResult.model_validate_json(CASE_FILE.read_text(encoding="utf-8"))
    for record in result.evidence:
        record.live_or_cached = "cached"
    if result.cached_at is None:
        raise ValueError("cached_case.json is missing cached_at; re-save it with scripts/save_example.py")
    return result
