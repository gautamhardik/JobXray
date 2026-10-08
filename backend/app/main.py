"""HTTP routes for JobXray.

See spec.md > Components > Backend > app/main.py.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from app.config import FRONTEND_ORIGINS, MAX_INPUT_CHARS
from app.input import InputUnreadable
from app.investigation.pipeline import InvestigationResult, run_from_link, run_investigation
from app.llm.llm_client import ModelBudgetExceeded, ModelCallError
from app.web.scraper import FetchBudgetExceeded

app = FastAPI(title="JobXray")

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class InvestigationRequest(BaseModel):
    """Exactly one of: pasted text, or a link to a job posting."""

    text: str | None = Field(default=None, max_length=MAX_INPUT_CHARS)
    url: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def exactly_one_input(self) -> "InvestigationRequest":
        given = [v for v in (self.text, self.url) if v is not None and v.strip()]
        if len(given) != 1:
            raise ValueError("Paste the recruiter or job messages, or a link to the job posting, before investigating.")
        return self


@app.post("/api/investigations", response_model=InvestigationResult)
def start_investigation(request: InvestigationRequest) -> InvestigationResult:
    try:
        if request.url:
            return run_from_link(request.url)
        return run_investigation(request.text or "")
    except InputUnreadable as error:
        raise HTTPException(status_code=422, detail=str(error))
    except (ModelCallError, ModelBudgetExceeded, FetchBudgetExceeded) as error:
        raise HTTPException(status_code=502, detail=str(error))
