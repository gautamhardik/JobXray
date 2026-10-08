"""HTTP routes for JobXray.

See spec.md > Components > Backend > app/main.py.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from app.config import FRONTEND_ORIGINS, MAX_INPUT_CHARS

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


class InvestigationResult(BaseModel):
    decision: str
    severity: str
    summary: str


@app.post("/api/investigations", response_model=InvestigationResult)
def start_investigation(request: InvestigationRequest) -> InvestigationResult:
    # Placeholder result: slice 1 proves the round trip only.
    return InvestigationResult(
        decision="VERIFY FIRST",
        severity="Placeholder",
        summary=f"Received {len(request.text)} characters. Analysis is not built yet.",
    )
