"""Call 3: report what fetched official pages say about the claims.

Observations must quote the page; quotes not found in the fetched text are
dropped. Code, not the model, turns observations into statuses.
See spec.md > Components > Backend > app/investigation/observe.py.
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.evidence.quotes import quote_in_text
from app.investigation.extract import CheckedExtraction
from app.llm.llm_client import LLMClient
from app.web.scraper import FetchResult

PROMPT = (Path(__file__).parent.parent / "prompts" / "observe.md").read_text(encoding="utf-8")

# A page with less readable text than this was probably rendered by JavaScript
# and could not actually be inspected.
MIN_INSPECTABLE_CHARS = 300
PAGE_CHARS_FOR_MODEL = 12_000

Topic = Literal["role", "stipend", "recruitment_policy"]
Finding = Literal["matches", "conflicts", "not_mentioned"]


class Observation(BaseModel):
    page_id: str
    topic: Topic
    finding: Finding
    quote: str
    explanation: str


class Observations(BaseModel):
    observations: list[Observation]


class CheckedObservations(BaseModel):
    observations: list[Observation]
    dropped_quotes: int


def inspectable(page: FetchResult) -> bool:
    return page.ok and len(page.text) >= MIN_INSPECTABLE_CHARS


def observe(extraction: CheckedExtraction, pages: list[FetchResult], client: LLMClient) -> CheckedObservations:
    """Pages are numbered P1, P2, ... in the order given."""
    claims = "\n".join(f"- {c.kind}: {c.value}" for c in extraction.claims)
    blocks = "\n\n".join(
        f'<page id="P{i}" url="{p.url}">\n{p.text[:PAGE_CHARS_FOR_MODEL]}\n</page>'
        for i, p in enumerate(pages, start=1)
    )
    user = (
        f"<claims>\nCompany: {extraction.company}\nRole: {extraction.role or 'not stated'}\n{claims}\n</claims>\n\n"
        f"<pages>\n{blocks}\n</pages>"
    )
    raw = client.structured(system=PROMPT, user=user, output_format=Observations)
    return check_observation_quotes(raw, pages)


def check_observation_quotes(raw: Observations, pages: list[FetchResult]) -> CheckedObservations:
    by_id = {f"P{i}": p for i, p in enumerate(pages, start=1)}
    kept: list[Observation] = []
    dropped = 0
    for obs in raw.observations:
        page = by_id.get(obs.page_id)
        if page is None:
            dropped += 1
            continue
        if obs.finding == "not_mentioned" and not obs.quote.strip():
            kept.append(obs)  # absence needs no quote, but only counts for inspected pages
        elif quote_in_text(obs.quote, page.text):
            kept.append(obs)
        else:
            dropped += 1
    return CheckedObservations(observations=kept, dropped_quotes=dropped)
