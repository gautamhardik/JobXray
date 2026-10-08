"""HTTP routes for JobXray.

POST starts an investigation and returns its id; GET returns the step list and,
when finished, the result. See spec.md > Components > Backend > app/main.py.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from app.config import FRONTEND_ORIGINS, MAX_INPUT_CHARS
from app.input import InputUnreadable
from app.investigation.pipeline import InvestigationResult, run_from_image, run_from_link, run_investigation
from app.investigation.progress import Progress
from app.jobs import InvestigationStatus, Jobs
from app.llm.llm_client import ModelBudgetExceeded, ModelCallError
from app.samples import load_example
from app.web.scraper import FetchBudgetExceeded

app = FastAPI(title="JobXray")
jobs = Jobs()

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class InvestigationRequest(BaseModel):
    """Exactly one of: pasted text, a link to a job posting, or a screenshot (data URL)."""

    text: str | None = Field(default=None, max_length=MAX_INPUT_CHARS)
    url: str | None = Field(default=None, max_length=2_000)
    image: str | None = Field(default=None, max_length=6_000_000)

    @model_validator(mode="after")
    def exactly_one_input(self) -> "InvestigationRequest":
        given = [v for v in (self.text, self.url, self.image) if v is not None and v.strip()]
        if len(given) != 1:
            raise ValueError("Paste the recruiter or job messages, a link to the job posting, or a screenshot before investigating.")
        return self


class Started(BaseModel):
    id: str


def explain(error: Exception) -> str:
    """Plain message for any failure. Unknown errors never leak internals."""
    if isinstance(error, (InputUnreadable, ModelCallError)):
        return str(error)
    if isinstance(error, (ModelBudgetExceeded, FetchBudgetExceeded)):
        return "The investigation reached its safety limit before it finished. Try again with a shorter input."
    return "Analysis could not finish. Try again or view the example."


@app.post("/api/investigations", response_model=Started, status_code=202)
def start_investigation(request: InvestigationRequest) -> Started:
    if request.image:
        progress = Progress("image")
        job_id = jobs.start(progress, lambda p: run_from_image(request.image or "", progress=p), explain)
    elif request.url:
        progress = Progress("url")
        job_id = jobs.start(progress, lambda p: run_from_link(request.url or "", progress=p), explain)
    else:
        progress = Progress("text")
        job_id = jobs.start(progress, lambda p: run_investigation(request.text or "", progress=p), explain)
    return Started(id=job_id)


@app.get("/api/investigations/{investigation_id}", response_model=InvestigationStatus)
def get_investigation(investigation_id: str) -> InvestigationStatus:
    status = jobs.get(investigation_id)
    if status is None:
        raise HTTPException(status_code=404, detail="This investigation was interrupted. Start again.")
    return status


@app.get("/api/example", response_model=InvestigationResult)
def get_example() -> InvestigationResult:
    """The saved example investigation. Works without the model or the web; always labelled Cached."""
    example = load_example()
    if example is None:
        raise HTTPException(status_code=404, detail="The example investigation has not been saved yet.")
    return example
