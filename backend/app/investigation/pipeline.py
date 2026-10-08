"""The investigation sequence.

Extraction (call 1) feeds the evidence ledger; the official-site check (call 2,
the domain check, careers fetches, call 3) adds official evidence; the decision
comes from the rules in app/evidence/status.py, not from the model.
See spec.md > Components > Backend > app/investigation/pipeline.py.
"""

from pydantic import BaseModel

from app.evidence.ledger import EvidenceRecord, Ledger, Reliability, SourceType, Status
from app.evidence.status import OfficialCheck, decide, opportunity_status, top_evidence
from app.investigation.extract import FUNNEL_ORDER, STAGE_LABELS, CheckedExtraction, extract
from app.investigation.observe import inspectable, observe
from app.config import MAX_MODEL_CALLS_IMAGE
from app.input.image import transcribe
from app.input.link import read_link
from app.investigation.challenge import CheckedHypothesis, plan_challenge, run_challenge
from app.investigation.plan import ATS_HOSTS, _same_site, career_links, check_domain, normalize_url, propose
from app.investigation.progress import NoProgress, Progress
from app.llm.llm_client import LLMClient, ModelBudgetExceeded, ModelCallError
from app.web.scraper import FetchBudgetExceeded, FetchResult, PageLink, Scraper

CLAIM_LABELS = {
    "company": "Company",
    "role": "Role",
    "stipend": "Stipend or pay",
    "fee": "Payment requested",
    "application_link": "Application link",
    "other": "Claim",
}


class Origin(BaseModel):
    """Where the investigated text came from."""

    source_type: SourceType = "pasted_text"
    source_url: str | None = None
    reliability: Reliability = "user-provided"
    transcription: str | None = None


ORIGIN_OBSERVATION = {
    "pasted_text": "Stated in the text you provided.",
    "linked_page": "Stated on the page you linked.",
    "screenshot": "Stated in your screenshot (as transcribed).",
}


class FunnelStage(BaseModel):
    stage: str
    label: str
    excerpt: str


class Funnel(BaseModel):
    detected: int
    total: int
    stages: list[FunnelStage]


class Challenge(BaseModel):
    hypotheses: list[CheckedHypothesis]
    changed: bool
    first_decision: str
    note: str


class InvestigationResult(BaseModel):
    decision: str
    severity: str
    next_step: str
    rule: str
    summary: str
    company: str | None
    role: str | None
    funnel: Funnel
    evidence: list[EvidenceRecord]
    top_evidence: list[str]
    dropped_quotes: int
    model_calls: int
    fetches: int
    source: Origin
    challenge: Challenge


def run_from_link(
    url: str,
    client: LLMClient | None = None,
    scraper: Scraper | None = None,
    progress: Progress | None = None,
) -> InvestigationResult:
    """Link input: read the linked page (one fetch from the same budget), then investigate its text."""
    scraper = scraper or Scraper()
    progress = progress or NoProgress("url")
    progress.start("read")
    page = read_link(url, scraper)
    progress.done("read", page.title)
    origin = Origin(source_type="linked_page", source_url=page.url)
    return run_investigation(page.text, client, scraper, origin, progress)


def run_from_image(
    data_url: str,
    client: LLMClient | None = None,
    scraper: Scraper | None = None,
    progress: Progress | None = None,
) -> InvestigationResult:
    """Screenshot input: one transcription call (budget 5 instead of 4), then investigate the transcription."""
    client = client or LLMClient(max_calls=MAX_MODEL_CALLS_IMAGE)
    progress = progress or NoProgress("image")
    progress.start("read")
    text = transcribe(data_url, client)
    progress.done("read")
    origin = Origin(source_type="screenshot", transcription=text)
    return run_investigation(text, client, scraper, origin, progress)


def run_investigation(
    text: str,
    client: LLMClient | None = None,
    scraper: Scraper | None = None,
    origin: Origin | None = None,
    progress: Progress | None = None,
) -> InvestigationResult:
    client = client or LLMClient()
    scraper = scraper or Scraper()
    origin = origin or Origin()
    progress = progress or NoProgress()
    if origin.source_type == "pasted_text":
        progress.done("read")

    progress.start("extract")
    extraction = extract(text, client)
    progress.done("extract", f"{extraction.company or 'No company named'} · {extraction.role or 'no role named'}")
    stages = [
        FunnelStage(stage=s.stage, label=STAGE_LABELS[s.stage], excerpt=s.excerpt)
        for s in extraction.funnel_stages
    ]
    funnel = Funnel(detected=len(stages), total=len(FUNNEL_ORDER), stages=stages)
    progress.done("funnel", f"{funnel.detected} of {funnel.total} stages")

    ledger = Ledger()
    payment_requested = record_pasted_facts(ledger, extraction, origin)

    official = check_official_sources(extraction, client, scraper, ledger, progress)
    first = decide(
        payment_requested=payment_requested,
        opportunity=official.status,
        direct_contradiction_on_payment_or_identity=official.policy_contradiction,
    )

    progress.start("challenge")
    challenge = challenge_first_assessment(first, extraction, official, payment_requested, client, scraper, ledger)
    progress.done("challenge", challenge.note)

    progress.start("decide")
    opportunity = official.status
    if challenge_found_role(ledger) and official.domain_established and opportunity != "contradiction":
        opportunity = opportunity_status(OfficialCheck(domain_established=True, relevant_page_inspected=True, supports_claim=True))
    result = decide(
        payment_requested=payment_requested,
        opportunity=opportunity,
        direct_contradiction_on_payment_or_identity=official.policy_contradiction or any(
            r.claim_id == "recruitment_policy" and r.status == "contradiction" for r in ledger.records
        ),
    )
    challenge.changed = result.decision != first.decision
    challenge.note = (
        "Assessment changed after contradictory evidence was found."
        if challenge.changed
        else challenge.note
    )
    top = top_evidence(ledger.records, result.decision)
    progress.done("decide", f"{result.decision} · {result.severity}")

    return InvestigationResult(
        decision=result.decision,
        severity=result.severity,
        next_step=result.next_step,
        rule=result.rule,
        summary=f"{result.rule} {funnel.detected} of {funnel.total} recruitment-funnel stages detected.",
        company=extraction.company,
        role=extraction.role,
        funnel=funnel,
        evidence=ledger.records,
        top_evidence=[r.id for r in top],
        dropped_quotes=extraction.dropped_quotes + official.dropped_quotes,
        model_calls=client.calls,
        fetches=scraper.fetches,
        source=origin,
        challenge=challenge,
    )


def challenge_first_assessment(first, extraction, official, payment_requested, client, scraper, ledger) -> Challenge:
    """Call 4 plus the targeted fetches. A failure here keeps the first decision and says so."""
    try:
        plan = plan_challenge(first.decision, first.rule, ledger.records, official.links, client)
    except (ModelCallError, ModelBudgetExceeded) as error:
        return Challenge(hypotheses=[], changed=False, first_decision=first.decision, note=f"The self-challenge could not run: {error}")
    outcome = run_challenge(
        plan, first.decision, official.links, extraction.role, payment_requested, scraper, next_id=len(ledger.records) + 1
    )
    ledger.records.extend(outcome.new_records)
    return Challenge(
        hypotheses=outcome.hypotheses,
        changed=False,
        first_decision=first.decision,
        note="No credible contradictory evidence found.",
    )


def challenge_found_role(ledger: Ledger) -> bool:
    return any(r.claim_id == "opportunity" and r.status == "verified" and r.observation.startswith("Self-challenge") for r in ledger.records)


class OfficialOutcome(BaseModel):
    status: Status
    policy_contradiction: bool = False
    dropped_quotes: int = 0
    domain_established: bool = False
    links: list[PageLink] = []  # official links not yet read, offered to the self-challenge


def challenge_links(pages: list[FetchResult], domain: str, limit: int = 25) -> list[PageLink]:
    """Same-site or jobs-platform links from the official pages that were not already fetched."""
    read = {normalize_url(p.url) for p in pages} | {normalize_url(p.requested_url) for p in pages}
    links: list[PageLink] = []
    seen: set[str] = set(read)
    for page in pages:
        for link in page.links:
            key = normalize_url(link.url)
            host = link.url.split("/")[2] if "//" in link.url else ""
            if key in seen or not (_same_site(link.url, domain) or any(host.endswith(a) for a in ATS_HOSTS)):
                continue
            seen.add(key)
            links.append(link)
            if len(links) >= limit:
                return links
    return links


def check_official_sources(
    extraction: CheckedExtraction,
    client: LLMClient,
    scraper: Scraper,
    ledger: Ledger,
    progress: Progress | None = None,
) -> OfficialOutcome:
    """Calls 2 and 3 plus the fetches between them. Every outcome lands in the ledger."""
    progress = progress or NoProgress()
    claim = opportunity_claim(extraction)

    def opportunity(status: Status, observation: str, **source) -> OfficialOutcome:
        ledger.add(claim_id="opportunity", claim=claim, observation=observation, status=status, **source)
        for key in ("domain", "official_pages"):
            if not any(s.key == key and s.state in ("done", "skipped") for s in progress.snapshot()):
                progress.skip(key, observation)
        return OfficialOutcome(status=status)

    progress.start("domain")
    if not extraction.company:
        return opportunity(
            "unknown",
            "No company is named, so no official source can be checked.",
            source_type="none",
            reliability="unknown",
        )

    try:
        proposal = propose(extraction, client)  # call 2
        domain = check_domain(proposal.official_domain, extraction.company, scraper)
    except FetchBudgetExceeded:
        return opportunity("unknown", "The page-fetch budget ran out before the official site was checked.", source_type="none", reliability="unknown")

    ledger.add(
        claim_id="official_domain",
        claim=f"Official website of {extraction.company}" + (f": {domain.domain}" if domain.domain else ""),
        source_type="official_page" if domain.homepage else "none",
        source_url=domain.homepage.url if domain.homepage else None,
        reliability="official" if domain.established else "unknown",
        observation=domain.reason + " " + "; ".join(f"{'✓' if s.passed else '✗'} {s.name}" for s in domain.signals),
        status="verified" if domain.established else "unknown",
    )
    if domain.established:
        progress.done("domain", domain.domain)
    if not domain.established or domain.homepage is None:
        return opportunity(
            "unknown",
            "The company's official website could not be established, so the opportunity could not be checked against it.",
            source_type="none",
            reliability="unknown",
        )

    progress.start("official_pages")
    careers: list[FetchResult] = []
    for url in career_links(domain.homepage, domain.domain or ""):
        try:
            careers.append(scraper.fetch(url))
        except FetchBudgetExceeded:
            break
    readable: list[FetchResult] = []
    for page in careers:
        if inspectable(page) and all(page.text != r.text for r in readable):
            readable.append(page)  # the same page under two addresses is read once
    if not readable:
        detail = (
            "No careers or jobs page was found on the official site."
            if not careers
            else "The official careers pages could not be read (they may need JavaScript or blocked the request)."
        )
        outcome = opportunity("unknown", detail, source_type="official_page", source_url=domain.homepage.url, reliability="official")
        outcome.domain_established = True
        outcome.links = challenge_links([domain.homepage, *careers], domain.domain or "")
        return outcome

    pages = [domain.homepage, *readable]
    checked = observe(extraction, pages, client)  # call 3
    by_id = {f"P{i}": p for i, p in enumerate(pages, start=1)}
    careers_ids = {f"P{i}" for i in range(2, len(pages) + 1)}

    role_match = next((o for o in checked.observations if o.topic == "role" and o.finding == "matches" and o.page_id in careers_ids), None)
    role_conflict = next((o for o in checked.observations if o.topic == "role" and o.finding == "conflicts"), None)
    check = OfficialCheck(
        domain_established=True,
        relevant_page_inspected=True,
        supports_claim=role_match is not None,
        contradicts_claim=role_conflict is not None,
    )
    status = opportunity_status(check)
    progress.done("official_pages", f"{len(readable)} page{'s' if len(readable) != 1 else ''} read · {status}")
    evidence = role_conflict or role_match
    page = by_id[evidence.page_id] if evidence else readable[0]
    observation = {
        "verified": "The company's official careers pages list this opportunity.",
        "contradiction": "The company's official pages directly contradict this opportunity.",
        "unverified": "The official careers pages that were read do not list this opportunity.",
    }[status]
    ledger.add(
        claim_id="opportunity",
        claim=claim,
        source_type="official_page",
        source_url=page.url,
        excerpt=evidence.quote if evidence and evidence.quote else None,
        reliability="official",
        observation=observation + (f" {evidence.explanation}" if evidence else ""),
        supports_or_contradicts="supports" if status == "verified" else ("contradicts" if status == "contradiction" else "neither"),
        status=status,
    )

    policy_contradiction = False
    for obs in checked.observations:
        if obs.finding == "not_mentioned" or obs.topic == "role":
            continue
        page = by_id[obs.page_id]
        conflicts = obs.finding == "conflicts"
        if obs.topic == "recruitment_policy" and conflicts:
            policy_contradiction = True
        ledger.add(
            claim_id="recruitment_policy" if obs.topic == "recruitment_policy" else "stipend",
            claim="How the company recruits and whether it charges candidates" if obs.topic == "recruitment_policy" else "Stipend or pay for the role",
            source_type="official_page",
            source_url=page.url,
            excerpt=obs.quote,
            reliability="official",
            observation=obs.explanation,
            supports_or_contradicts="contradicts" if conflicts else "supports",
            status="contradiction" if conflicts else "verified",
        )

    return OfficialOutcome(
        status=status,
        policy_contradiction=policy_contradiction,
        dropped_quotes=checked.dropped_quotes,
        domain_established=True,
        links=challenge_links(pages, domain.domain or ""),
    )


def record_pasted_facts(ledger: Ledger, extraction: CheckedExtraction, origin: Origin) -> bool:
    """Every surviving claim becomes a Fact from the pasted text. Returns whether a payment is requested."""
    payment_requested = False
    other_count = 0
    for claim in extraction.claims:
        if claim.kind == "fee":
            claim_id = "payment"
            payment_requested = True
        elif claim.kind == "other":
            other_count += 1
            claim_id = f"other-{other_count}"
        else:
            claim_id = claim.kind
        ledger.add(
            claim_id=claim_id,
            claim=f"{CLAIM_LABELS[claim.kind]}: {claim.value}",
            source_type=origin.source_type,
            source_url=origin.source_url,
            excerpt=claim.excerpt,
            reliability=origin.reliability,
            observation=ORIGIN_OBSERVATION[origin.source_type],
            status="fact",
        )

    # A payment-request stage with no fee claim still counts as a payment Fact.
    if not payment_requested:
        stage = next((s for s in extraction.funnel_stages if s.stage == "payment_request"), None)
        if stage:
            payment_requested = True
            ledger.add(
                claim_id="payment",
                claim="Payment requested",
                source_type=origin.source_type,
                source_url=origin.source_url,
                excerpt=stage.excerpt,
                reliability=origin.reliability,
                observation=ORIGIN_OBSERVATION[origin.source_type],
                status="fact",
            )
    return payment_requested


def opportunity_claim(extraction: CheckedExtraction) -> str:
    role = extraction.role or "This opportunity"
    company = extraction.company or "the named company"
    return f"{role} is offered by {company}"
