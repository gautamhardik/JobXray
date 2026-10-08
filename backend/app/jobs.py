"""In-memory investigations: started by POST, polled by GET, lost on restart.

See spec.md > Data Model (Investigation) and spec.md > Components > Backend > app/main.py.
"""

import threading
import uuid
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pydantic import BaseModel

from app.investigation.pipeline import InvestigationResult
from app.investigation.progress import Progress, Step

MAX_KEPT = 200


class InvestigationStatus(BaseModel):
    id: str
    status: Literal["running", "done", "failed"]
    steps: list[Step]
    result: InvestigationResult | None = None
    error: str | None = None


class _Job:
    def __init__(self, progress: Progress):
        self.progress = progress
        self.status: Literal["running", "done", "failed"] = "running"
        self.result: InvestigationResult | None = None
        self.error: str | None = None


class Jobs:
    def __init__(self, workers: int = 4, run_inline: bool = False):
        self._jobs: OrderedDict[str, _Job] = OrderedDict()
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=workers)
        self.run_inline = run_inline  # tests run investigations synchronously

    def start(
        self,
        progress: Progress,
        work: Callable[[Progress], InvestigationResult],
        explain: Callable[[Exception], str],
    ) -> str:
        job_id = uuid.uuid4().hex[:12]
        job = _Job(progress)
        with self._lock:
            self._jobs[job_id] = job
            while len(self._jobs) > MAX_KEPT:
                self._jobs.popitem(last=False)

        def run() -> None:
            try:
                job.result = work(progress)
                job.status = "done"
            except Exception as error:  # every failure becomes a plain message, never a partial result
                job.error = explain(error)
                job.status = "failed"

        if self.run_inline:
            run()
        else:
            self._executor.submit(run)
        return job_id

    def get(self, job_id: str) -> InvestigationStatus | None:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            return None
        return InvestigationStatus(
            id=job_id,
            status=job.status,
            steps=job.progress.snapshot(),
            result=job.result if job.status == "done" else None,
            error=job.error,
        )
