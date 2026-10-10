"""Call 2 and the official-domain check.

The model only proposes a domain. Code decides whether it is established, from
several first-party identity signals on the fetched site; a company-name match
alone never establishes it. Then code discovers careers or jobs pages.
See spec.md > Components > Backend > app/investigation/plan.py.
"""

import re
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel

from app.investigation.extract import CheckedExtraction
from app.llm.llm_client import LLMClient
from app.web.scraper import FetchBudgetExceeded, FetchResult, Scraper

PROMPT = (Path(__file__).parent.parent / "prompts" / "plan.md").read_text(encoding="utf-8")

# Hosts where anyone can publish a page; they never count as a company's own domain.
HOSTING_PLATFORMS = (
    "wixsite.com", "blogspot.com", "wordpress.com", "github.io", "sites.google.com",
    "forms.gle", "docs.google.com", "linktr.ee", "carrd.co", "weebly.com",
    "notion.site", "vercel.app", "netlify.app", "web.app", "firebaseapp.com",
)
LOOKALIKE_WORDS = re.compile(r"(career|careers|jobs|job|hiring|recruit|recruitment|hr|intern|internship|offer|apply)")
CAREER_WORDS = re.compile(r"career|\bjobs?\b|join[- ]?us|work[- ]with[- ]us|hiring", re.I)
# Weaker hints, used only when no link matches CAREER_WORDS.
CAREER_FALLBACK_WORDS = re.compile(r"internship|graduates|early[- ]careers|opportunit", re.I)
ABOUT_WORDS = re.compile(r"about|contact|company|who[- ]we[- ]are|investor|press|newsroom", re.I)
ATS_HOSTS = (
    "greenhouse.io", "lever.co", "myworkdayjobs.com", "smartrecruiters.com",
    "ashbyhq.com", "workable.com", "icims.com", "successfactors.com", "taleo.net",
)
SECOND_LEVEL = ("co", "com", "org", "net", "ac", "gov", "edu")


class PlanProposal(BaseModel):
    official_domain: str | None
    questions: list[str]


class DomainSignal(BaseModel):
    name: str
    passed: bool
    detail: str


class DomainCheck(BaseModel):
    domain: str | None
    established: bool
    signals: list[DomainSignal]
    homepage: FetchResult | None = None
    probed_careers: list[FetchResult] = []  # careers pages found at a usual address, already fetched
    reason: str


def propose(extraction: CheckedExtraction, client: LLMClient) -> PlanProposal:
    claims = "\n".join(f"- {c.kind}: {c.value}" for c in extraction.claims)
    user = (
        f"<claimed_company>{extraction.company}</claimed_company>\n"
        f"<claimed_role>{extraction.role or 'not stated'}</claimed_role>\n"
        f"<other_claims>\n{claims}\n</other_claims>"
    )
    proposal = client.structured(system=PROMPT, user=user, output_format=PlanProposal)
    proposal.official_domain = clean_domain(proposal.official_domain)
    return proposal


def clean_domain(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().lower()
    host = urlsplit(value if "//" in value else f"//{value}").hostname or ""
    host = host.removeprefix("www.")
    return host if "." in host else None


def registrable(host: str) -> str:
    """Crude registrable domain: example.com, example.co.in."""
    labels = host.lower().removeprefix("www.").split(".")
    if len(labels) >= 3 and labels[-2] in SECOND_LEVEL and len(labels[-1]) == 2:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _same_site(url: str, domain: str) -> bool:
    host = urlsplit(url).hostname or ""
    return registrable(host) == registrable(domain)


def _company_tokens(company: str) -> list[str]:
    stop = {"pvt", "ltd", "limited", "inc", "llc", "the", "and", "of", "private", "technologies", "technology", "solutions", "services", "group", "india", "global"}
    # Department words that come with a recruiter's signature ("Amazon HR"), not part of the company's name.
    stop |= {"hr", "team", "careers", "career", "recruitment", "recruiting", "talent", "acquisition", "hiring", "department"}
    words = [w for w in re.findall(r"[a-z0-9]+", company.lower()) if w not in stop and len(w) > 1]
    if words:
        return words
    # Acronyms like "TCS" from "Tata Consultancy Services"
    return [w for w in re.findall(r"[a-z0-9]+", company.lower()) if len(w) > 1]


def check_domain(domain: str | None, company: str, scraper: Scraper) -> DomainCheck:
    if not domain:
        return DomainCheck(domain=None, established=False, signals=[], reason="No official domain could be proposed for this company.")

    base = registrable(domain)
    host_label = base.split(".")[0]
    lookalike = (
        any(domain.endswith(p) for p in HOSTING_PLATFORMS)
        or ("-" in host_label and bool(LOOKALIKE_WORDS.search(host_label)))
    )
    if lookalike:
        signal = DomainSignal(name="Not a look-alike or hosting domain", passed=False, detail=f"{domain} looks like a hosting or recruitment look-alike domain.")
        return DomainCheck(domain=domain, established=False, signals=[signal], reason="The proposed domain looks like a look-alike, not a company's own site.")

    homepage = scraper.fetch(f"https://{domain}/")
    signals = [DomainSignal(name="Not a look-alike or hosting domain", passed=True, detail=f"{domain} is not a hosting platform or recruitment look-alike.")]
    if not homepage.ok:
        signals.append(DomainSignal(name="Homepage reachable", passed=False, detail=homepage.failure or "Not reachable."))
        return DomainCheck(domain=domain, established=False, signals=signals, homepage=homepage, reason="The official site could not be reached.")
    signals.append(DomainSignal(name="Homepage reachable", passed=True, detail=f"{homepage.url} returned HTTP {homepage.status}."))

    tokens = _company_tokens(company)
    title = (homepage.title or "").lower()
    body = homepage.text.lower()
    acronym = "".join(w[0] for w in re.findall(r"[a-z0-9]+", company.lower()) if len(w) > 2)
    identity = (
        all(t in title or t in body for t in tokens)
        and (any(t in title for t in tokens) or sum(body.count(t) for t in tokens) >= 2 or (len(acronym) >= 2 and acronym in host_label))
    )
    signals.append(DomainSignal(name="Company identity on the site", passed=identity, detail=f"Looked for {', '.join(tokens) or company} in the title and page text."))

    links = homepage.links
    same_site = [l for l in links if _same_site(l.url, domain)]
    share = len(same_site) / len(links) if links else 0.0
    signals.append(DomainSignal(name="Links stay on the same site", passed=share >= 0.5, detail=f"{len(same_site)} of {len(links)} links stay on {base}."))

    careers = career_links(homepage, domain)
    probed = [] if careers else probe_careers(domain, scraper)
    found = careers[0] if careers else (probed[0].url if probed else None)
    signals.append(DomainSignal(name="Careers or jobs section", passed=bool(found), detail=found or "No careers or jobs page found on the site."))

    about = any(ABOUT_WORDS.search(f"{l.text} {l.url}") for l in same_site)
    signals.append(DomainSignal(name="About or contact information", passed=about, detail="Found an about or contact link." if about else "No about or contact link found."))

    supporting = sum(s.passed for s in signals[3:])
    established = identity and supporting >= 2
    reason = (
        "Several first-party identity signals agree."
        if established
        else "Not enough first-party identity signals agree, so the official site is not established."
    )
    return DomainCheck(domain=domain, established=established, signals=signals, homepage=homepage, probed_careers=probed, reason=reason)


def probe_careers(domain: str, scraper: Scraper) -> list[FetchResult]:
    """Big companies often keep jobs off the homepage (careers.google.com). Try the usual addresses."""
    base = registrable(domain)
    for url in (f"https://careers.{base}/", f"https://{domain}/careers"):
        try:
            page = scraper.fetch(url)
        except FetchBudgetExceeded:
            return []
        if page.ok and _same_site(page.url, domain) and CAREER_WORDS.search(page.url):
            return [page]
    return []


def normalize_url(url: str) -> str:
    """Drop default ports, fragments, trailing slashes and .html, so the same page is fetched once."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.port and parts.port not in (80, 443):
        host = f"{host}:{parts.port}"
    path = parts.path.rstrip("/").removesuffix(".html").removesuffix(".htm")
    query = f"?{parts.query}" if parts.query else ""
    return f"{parts.scheme}://{host}{path}{query}"


def career_links(homepage: FetchResult, domain: str, limit: int = 2) -> list[str]:
    """Careers or jobs links on the official homepage: same site or a known jobs platform."""

    def candidates(pattern: re.Pattern) -> list[str]:
        found: list[str] = []
        seen: set[str] = set()
        for link in homepage.links:
            host = urlsplit(link.url).hostname or ""
            on_site = _same_site(link.url, domain)
            on_ats = any(host.endswith(a) for a in ATS_HOSTS)
            key = normalize_url(link.url)
            if (on_site or on_ats) and pattern.search(f"{link.text} {link.url}") and key not in seen:
                seen.add(key)
                found.append(link.url)
            if len(found) >= limit:
                break
        return found

    return candidates(CAREER_WORDS) or candidates(CAREER_FALLBACK_WORDS)
