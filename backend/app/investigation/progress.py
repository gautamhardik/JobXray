"""The step list the progress checklist polls.

The pipeline marks each step active, done, or skipped as it runs.
See spec.md > Components > Backend > app/investigation/pipeline.py (step-status list).
"""

import threading
from typing import Literal

from pydantic import BaseModel

StepState = Literal["pending", "active", "done", "skipped"]

STEP_LABELS: dict[str, str] = {
    "read": "Reading what you provided",
    "extract": "Identifying the company, role, and claims",
    "funnel": "Checking the recruitment sequence",
    "domain": "Establishing the company's official website",
    "official_pages": "Checking the official careers pages",
    "challenge": "Challenging the first assessment",
    "decide": "Deciding from the evidence",
}
READ_LABELS = {
    "text": "Reading what you provided",
    "url": "Reading the page you linked",
    "image": "Transcribing your screenshot",
}


class Step(BaseModel):
    key: str
    label: str
    state: StepState = "pending"
    note: str | None = None


class Progress:
    """Thread-safe step list for one investigation."""

    def __init__(self, input_kind: str = "text"):
        self._lock = threading.Lock()
        self._steps = [Step(key=k, label=v) for k, v in STEP_LABELS.items()]
        self._find("read").label = READ_LABELS.get(input_kind, STEP_LABELS["read"])

    def _find(self, key: str) -> Step:
        return next(s for s in self._steps if s.key == key)

    def start(self, key: str) -> None:
        with self._lock:
            self._find(key).state = "active"

    def done(self, key: str, note: str | None = None) -> None:
        with self._lock:
            step = self._find(key)
            step.state, step.note = "done", note

    def skip(self, key: str, note: str) -> None:
        with self._lock:
            step = self._find(key)
            step.state, step.note = "skipped", note

    def snapshot(self) -> list[Step]:
        with self._lock:
            return [s.model_copy() for s in self._steps]


class NoProgress(Progress):
    """Used when nobody is watching (tests, scripts)."""
