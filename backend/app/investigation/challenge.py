"""Call 4: challenge the first assessment, then check the targeted pages with fixed rules.

The model writes counter-hypotheses and picks pages, but only from links found
on the official site. Code fetches them and decides what they show: whether the
claimed role (or an alternate title) appears, and whether the company states it
never charges candidates. A changed decision only ever comes from a new
Verified or Contradiction record. See spec.md > Components > Backend > challenge.py.
"""

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.evidence.ledger import EvidenceRecord
from app.evidence.quotes import _normalize
from app.llm.llm_client import LLMClient
from app.web.scraper import FetchBudgetExceeded, FetchResult, PageLink, Scraper

PROMPT = (Path(__file__).parent.parent / "prompts" / "challenge.md").read_text(encoding="utf-8")

Kind = Literal[
    "alternate_official_source",
    "alternate_title",
    "authorized_intermediary",
    "innocent_explanation",
    "contradicting_evidence",
]

NO_FEE_POLICY = re.compile(
    r"(never|do not|don't|does not|doesn't|will not|won't|not)\s+(charge|ask|request|collect)\w*\b[^.]{0,80}\b(fee|fees|money|payment|deposit)"
    r"|\b(no|zero)\s+(registration\s+|application\s+|recruitment\s+)?(fee|fees|charges?)\b[^.]{0,60}\b(candidate|applicant|recruit|hiring|interview|job)",
    re.I,
)
STOP_WORDS = {"the", "a", "an", "of", "for", "and", "in", "at", "our", "program", "programme", "role", "position"}


class Hypothesis(BaseModel):
    question: str
    kind: Kind
    link_ids: list[str]
    alternate_titles: list[str]


class ChallengePlan(BaseModel):
    hypotheses: list[Hypothesis]


class CheckedHypothesis(BaseModel):
    question: str
    kind: Kind
    checked_urls: list[str]
    finding: str


class ChallengeOutcome(BaseModel):
    hypotheses: list[CheckedHypothesis]
    new_records: list[EvidenceRecord] = []
    role_found: bool = False
    fee_policy_found: bool = False


def limits(first_decision: str) -> tuple[int, int]:
    """Proportional challenge: (max hypotheses, max pages). Lighter when the first look is low risk."""
    return (1, 1) if first_decision == "PROCEED" else (3, 3)


def plan_challenge(
    first_decision: str,
    first_rule: str,
    evidence: list[EvidenceRecord],
    links: list[PageLink],
    client: LLMClient,
) -> ChallengePlan:
    max_hypotheses, max_pages = limits(first_decision)
    lines = "\n".join(f"- [{r.status}] {r.claim}: {r.observation}" for r in evidence)
    link_list = "\n".join(f"L{i}: {l.text or '(no text)'} — {l.url}" for i, l in enumerate(links, start=1)) or "(no official links available)"
    user = (
        f"<first_assessment>{first_decision}: {first_rule}</first_assessment>\n"
        f"<evidence>\n{lines}\n</evidence>\n"
        f"<official_links>\n{link_list}\n</official_links>\n"
        f"Write at most {max_hypotheses} hypotheses and choose at most {max_pages} links in total."
    )
    return client.structured(system=PROMPT, user=user, output_format=ChallengePlan)


def _title_in(title: str, text: str) -> str | None:
    """The passage where the title appears, or None. Every significant word must appear in that passage."""
    norm_title = _normalize(title)
    norm_text = _normalize(text)
    if not norm_title:
        return None
    index = norm_text.find(norm_title)
    if index >= 0:
        return text_window(text, title)
    words = [w for w in re.findall(r"[a-z0-9]+", norm_title) if w not in STOP_WORDS]
    for line in text.splitlines():
        low = line.casefold()
        if words and all(re.search(rf"\b{re.escape(w)}\b", low) for w in words):
            return line.strip()[:200]
    return None


def text_window(text: str, needle: str) -> str:
    for line in text.splitlines():
        if _normalize(needle) in _normalize(line):
            return line.strip()[:200]
    return needle


def run_challenge(
    plan: ChallengePlan,
    first_decision: str,
    links: list[PageLink],
    role: str | None,
    payment_requested: bool,
    scraper: Scraper,
    next_id: int,
) -> ChallengeOutcome:
    max_hypotheses, max_pages = limits(first_decision)
    by_id = {f"L{i}": l for i, l in enumerate(links, start=1)}
    fetched: dict[str, FetchResult] = {}
    outcome = ChallengeOutcome(hypotheses=[])

    def record(**fields) -> None:
        nonlocal next_id
        outcome.new_records.append(EvidenceRecord(id=f"E{next_id}", **fields))
        next_id += 1

    for hypothesis in plan.hypotheses[:max_hypotheses]:
        checked: list[str] = []
        findings: list[str] = []
        for link_id in hypothesis.link_ids:
            link = by_id.get(link_id)
            if link is None:
                findings.append(f"{link_id} is not an official link, so it was ignored.")
                continue
            if link.url not in fetched:
                if len(fetched) >= max_pages:
                    break
                try:
                    fetched[link.url] = scraper.fetch(link.url)
                except FetchBudgetExceeded:
                    findings.append("The page-fetch budget ran out.")
                    break
            page = fetched[link.url]
            checked.append(page.url)
            if not page.ok:
                findings.append(f"{page.url} could not be read.")
                continue

            for title in [t for t in [role, *hypothesis.alternate_titles] if t]:
                passage = _title_in(title, page.text)
                if passage and not outcome.role_found:
                    outcome.role_found = True
                    findings.append(f"Found “{title}” on {page.url}.")
                    record(
                        claim_id="opportunity",
                        claim=f"{role or 'This opportunity'} is listed on the official site",
                        source_type="official_page",
                        source_url=page.url,
                        excerpt=passage,
                        reliability="official",
                        observation=f"Self-challenge: the official page lists “{title}”.",
                        supports_or_contradicts="supports",
                        status="verified",
                    )
                    break

            policy = NO_FEE_POLICY.search(page.text)
            if policy and payment_requested and not outcome.fee_policy_found:
                outcome.fee_policy_found = True
                passage = text_window(page.text, policy.group(0))
                findings.append(f"{page.url} says the company does not charge candidates.")
                record(
                    claim_id="recruitment_policy",
                    claim="How the company recruits and whether it charges candidates",
                    source_type="official_page",
                    source_url=page.url,
                    excerpt=passage,
                    reliability="official",
                    observation="Self-challenge: the official site says it does not charge candidates, which contradicts the payment request.",
                    supports_or_contradicts="contradicts",
                    status="contradiction",
                )

        if not findings:
            findings.append("Nothing on the checked pages changes the assessment." if checked else "No official page was available to check this.")
        outcome.hypotheses.append(
            CheckedHypothesis(question=hypothesis.question, kind=hypothesis.kind, checked_urls=checked, finding=" ".join(findings))
        )
    return outcome
