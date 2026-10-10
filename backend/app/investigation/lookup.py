"""Search fallbacks for the official-site check. Plain code; search only points, pages decide.

1. discover_domain: when the model's proposed domain can't be established, search
   for the company's website and run the same identity checks on what comes back.
   A domain found this way still has to pass every check; the message itself is
   never a source of the domain, so a scammer can't vouch for their own site.
2. find_listing: when the careers pages don't show the role, search the official
   site for it, then read the page (in a browser if it needs JavaScript). Only a
   page that really shows the role counts; a search snippet alone never does.
See spec.md > Components > Backend > app/investigation/lookup.py.
"""

import re
from urllib.parse import urlsplit

from pydantic import BaseModel

from app.evidence.channels import JOB_PLATFORMS
from app.investigation.observe import inspectable
from app.investigation.plan import ATS_HOSTS, HOSTING_PLATFORMS, DomainCheck, _company_tokens, _same_site, check_domain, clean_domain, registrable
from app.web.scraper import FetchBudgetExceeded, FetchResult, Scraper
from app.web.search import Search, SearchBudgetExceeded

# Sites that write about companies rather than being them.
NOT_A_COMPANY_SITE = (
    *JOB_PLATFORMS, *HOSTING_PLATFORMS, "facebook.com", "instagram.com", "twitter.com", "x.com", "youtube.com",
    "wikipedia.org", "ambitionbox.com", "crunchbase.com", "zaubacorp.com", "tofler.in", "justdial.com",
    "quora.com", "reddit.com", "medium.com", "bloomberg.com", "zoominfo.com", "economictimes.indiatimes.com",
)
GENERIC_ROLE_WORDS = {
    "intern", "interns", "internship", "internships", "trainee", "job", "jobs", "opening", "openings", "vacancy",
    "fresher", "freshers", "remote", "wfh", "part", "time", "full", "work", "from", "home", "the", "a", "an",
    "of", "for", "and", "in", "at", "program", "programme", "role", "position",
}
MAX_DOMAIN_CANDIDATES = 2
MAX_LISTING_PAGES = 2


class ListingFinding(BaseModel):
    verified: bool
    url: str
    excerpt: str | None = None
    observation: str


def _acronym(company: str) -> str:
    return "".join(w[0] for w in re.findall(r"[a-z0-9]+", company.lower()) if len(w) > 2)


def _names_company(host: str, company: str) -> bool:
    label = registrable(host).split(".")[0]
    tokens = [t for t in _company_tokens(company) if len(t) >= 3]
    acronym = _acronym(company)
    return any(t in label for t in tokens) or (len(acronym) >= 2 and label == acronym)


def domain_candidates(answer, company: str, tried: str | None) -> list[str]:
    """Websites from the results that are plausibly the company's own, best first."""
    urls = ([answer.website] if answer.website else []) + [r.url for r in answer.results]
    seen = {registrable(tried)} if tried else set()
    out: list[str] = []
    for url in urls:
        host = clean_domain(url)
        if not host or any(host == d or host.endswith(f".{d}") for d in NOT_A_COMPANY_SITE):
            continue
        base = registrable(host)
        if base in seen or not _names_company(host, company):
            continue
        seen.add(base)
        out.append(host)
    return out[:MAX_DOMAIN_CANDIDATES]


def discover_domain(company: str, tried: str | None, scraper: Scraper, search: Search) -> DomainCheck | None:
    """An established official domain found through search, or None."""
    try:
        answer = search.search(f"{company} official website")
    except SearchBudgetExceeded:
        return None
    if answer is None:
        return None
    for host in domain_candidates(answer, company, tried):
        try:
            check = check_domain(host, company, scraper)
        except FetchBudgetExceeded:
            return None
        if check.established:
            return check
    return None


def role_words(role: str) -> list[str]:
    words = [w for w in re.findall(r"[a-z0-9]+", role.lower()) if w not in GENERIC_ROLE_WORDS]
    return words


def role_in(role: str, text: str) -> str | None:
    """The line where every significant word of the role appears (and "intern" too, for internships)."""
    words = role_words(role)
    if not words:
        return None
    wants_intern = bool(re.search(r"\bintern", role, re.I))
    for line in text.splitlines():
        low = line.casefold()
        if all(re.search(rf"\b{re.escape(w)}\b", low) for w in words) and (not wants_intern or "intern" in low):
            return line.strip()[:200]
    return None


def _read(url: str, scraper: Scraper) -> FetchResult | None:
    try:
        page = scraper.fetch(url)
        if not inspectable(page) and scraper.can_render:
            page = scraper.fetch_rendered(page.url if page.ok else url)
        return page
    except FetchBudgetExceeded:
        return None


def find_listing(role: str, domain: str, scraper: Scraper, search: Search) -> ListingFinding | None:
    """The role on a page of the official site, found through search and confirmed by reading the page."""
    if not role_words(role):
        return None
    try:
        answer = search.search(f"site:{registrable(domain)} {role}")
    except SearchBudgetExceeded:
        return None
    if answer is None:
        return None
    hits = [
        r for r in answer.results
        if (_same_site(r.url, domain) or any((urlsplit(r.url).hostname or "").endswith(a) for a in ATS_HOSTS))
        and role_in(role, f"{r.title}\n{r.snippet}")
    ]
    seen_only: str | None = None
    for hit in hits[:MAX_LISTING_PAGES]:
        page = _read(hit.url, scraper)
        if page is None:
            break
        passage = role_in(role, page.text) if page.ok else None
        if passage:
            return ListingFinding(
                verified=True,
                url=page.url,
                excerpt=passage,
                observation="Found through a web search of the official site, then confirmed by reading the page.",
            )
        seen_only = seen_only or hit.url
    if seen_only:
        return ListingFinding(
            verified=False,
            url=seen_only,
            observation=(
                "A web search shows this role on the official site, but the page itself did not confirm it, "
                "so it does not count as verification."
            ),
        )
    return None
