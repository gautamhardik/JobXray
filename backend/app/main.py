"""HTTP routes for JobXray.

See spec.md > Components > Backend > app/main.py.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from app.config import FRONTEND_ORIGINS, MAX_INPUT_CHARS
from app.investigation.pipeline import InvestigationResult, run_investigation
from app.llm.llm_client import ModelBudgetExceeded, ModelCallError

app = FastAPI(title="JobXray")

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class InvestigationRequest(BaseModel):
    text: str = Field(max_length=MAX_INPUT_CHARS)

    @field_validator("text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Paste the recruiter or job messages before investigating.")
        return value


@app.post("/api/investigations", response_model=InvestigationResult)
def start_investigation(request: InvestigationRequest) -> InvestigationResult:
    try:
        return run_investigation(request.text)
    except (ModelCallError, ModelBudgetExceeded) as error:
        raise HTTPException(status_code=502, detail=str(error))
