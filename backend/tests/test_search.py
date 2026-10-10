"""Search and browser fallbacks: SerpAPI finds pages, Scrapling's browser reads JavaScript pages,
and only a page that really shows the role verifies it. No real browser or search runs here."""

from pathlib import Path

import httpx
import pytest

from app.investigation.extract import Extraction, ExtractedClaim, ExtractedStage
from app.investigation.lookup import domain_candidates, role_in
from app.investigation.observe import Observation, Observations
from app.investigation.pipeline import run_investigation
from app.investigation.plan import PlanProposal
from app.web import search as search_module
from app.web.scraper import Scraper, _public_requests_only
from app.web.search import Search, SearchAnswer, SearchBudgetExceeded, SearchResult
from tests.helpers import FakeSearch, ScriptedClient, saved_scraper

TEXT = (
    "Hi, this is Rahul from the HR team at Nexora Technologies.\n"
    "You have been shortlisted for our Business Analyst Internship.\n"
)
HOME = "https://nexora.example/"
CAREERS = "https://nexora.example/careers"
LISTING = "https://nexora.example/jobs/business-analyst-internship"
NO_DOMAIN = PlanProposal(official_domain=None, questions=[])
NEXORA = PlanProposal(official_domain="nexora.example", questions=[])
ROLE_LISTED = Observations(observations=[Observation(
    page_id="P2", topic="role", finding="matches",
    quote="Business Analyst Internship (6 months, Bengaluru)", explanation="Listed.",
)])
NOTHING = Observations(observations=[])


def _extraction() -> Extraction:
    return Extraction(
        company="Nexora Technologies",
        role="Business Analyst Internship",
        claims=[
            ExtractedClaim(kind="company", value="Nexora Technologies", excerpt="Nexora Technologies"),
            ExtractedClaim(kind="role", value="Business Analyst Internship", excerpt="Business Analyst Internship"),
        ],
        funnel_stages=[ExtractedStage(stage="opportunity", excerpt="You have been shortlisted for our Business Analyst Internship.")],
    )


def _record(result, claim_id):
    return next(r for r in result.evidence if r.claim_id == claim_id)


# The search client


def _http(status=200, payload=None, calls=None):
    def handler(request):
        if calls is not None:
            calls.append(str(request.url))
        return httpx.Response(status, json=payload or {})

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(search_module, "CACHE_DIR", tmp_path)
    return tmp_path


def test_search_is_off_without_a_key():
    calls = []
    assert Search(api_key="", http=_http(calls=calls)).search("anything") is None
    assert calls == []


def test_a_repeated_query_is_answered_from_the_cache_for_free(cache_dir):
    calls = []
    payload = {"organic_results": [{"title": "Nexora", "link": "https://nexora.example/", "snippet": "Data consulting"}],
               "knowledge_graph": {"website": "https://nexora.example/"}}
    first = Search(api_key="k", http=_http(payload=payload, calls=calls))
    answer = first.search("Nexora Technologies official website")
    assert answer.website == "https://nexora.example/" and answer.results[0].url == HOME
    second = Search(api_key="k", http=_http(payload=payload, calls=calls))
    again = second.search("Nexora Technologies official website")
    assert again.cached and second.searches == 0
    assert len(calls) == 1  # one real search for two investigations


def test_searches_per_investigation_are_capped(cache_dir):
    search = Search(api_key="k", max_searches=2, http=_http(payload={}))
    search.search("one")
    search.search("two")
    with pytest.raises(SearchBudgetExceeded):
        search.search("three")


def test_a_failed_search_is_nothing_not_a_crash(cache_dir):
    assert Search(api_key="k", http=_http(status=429)).search("x") is None


# Finding the official domain


def test_candidates_skip_sites_that_only_write_about_the_company():
    answer = SearchAnswer(results=[
        SearchResult(title="", url="https://www.linkedin.com/company/nexora"),
        SearchResult(title="", url="https://en.wikipedia.org/wiki/Nexora"),
        SearchResult(title="", url="https://randomblog.example/nexora-review"),
        SearchResult(title="", url="https://www.nexora.example/about"),
    ])
    assert domain_candidates(answer, "Nexora Technologies", tried=None) == ["nexora.example"]
    tcs = SearchAnswer(results=[SearchResult(title="", url="https://www.tcs.com/")])
    assert domain_candidates(tcs, "Tata Consultancy Services", tried=None) == ["tcs.com"]


def test_domain_found_by_search_still_has_to_pass_the_identity_checks():
    search = FakeSearch({"official website": SearchAnswer(website="https://nexora.example/")})
    client = ScriptedClient(_extraction(), NO_DOMAIN, ROLE_LISTED)
    result = run_investigation(TEXT, client, saved_scraper({HOME: "nexora_home.html", CAREERS: "nexora_careers_with_role.html"}), search=search)
    domain = _record(result, "official_domain")
    assert domain.status == "verified" and domain.observation.startswith("Found through a web search")
    assert result.decision == "PROCEED"
    assert result.searches == 1


def test_a_search_result_that_fails_the_identity_checks_is_not_trusted():
    search = FakeSearch({"official website": SearchAnswer(website="https://nexora-hiring.example/")})
    client = ScriptedClient(_extraction(), NO_DOMAIN, ROLE_LISTED)
    result = run_investigation(TEXT, client, saved_scraper({"https://nexora-hiring.example/": "name_only.html"}), search=search)
    assert _record(result, "official_domain").status == "unknown"
    assert result.decision == "VERIFY FIRST"


# Careers pages that need JavaScript


def test_a_javascript_careers_page_is_read_in_the_browser():
    scraper = saved_scraper(
        {HOME: "nexora_home.html", CAREERS: "js_careers.html"},
        rendered={CAREERS: "nexora_careers_with_role.html"},
    )
    client = ScriptedClient(_extraction(), NEXORA, ROLE_LISTED)
    result = run_investigation(TEXT, client, scraper)
    assert _record(result, "opportunity").status == "verified"
    assert result.decision == "PROCEED"
    assert scraper.rendered == 1


def test_without_a_browser_a_javascript_page_stays_unknown():
    client = ScriptedClient(_extraction(), NEXORA, ROLE_LISTED)
    result = run_investigation(TEXT, client, saved_scraper({HOME: "nexora_home.html", CAREERS: "js_careers.html"}))
    assert _record(result, "opportunity").status == "unknown"


# Finding the listing on the official site


def _listing_search(url=LISTING, title="Business Analyst Internship - Nexora Careers"):
    return FakeSearch({"site:nexora.example": SearchAnswer(results=[SearchResult(title=title, url=url, snippet="Apply now")])})


def test_role_found_through_search_and_confirmed_on_the_page_is_verified():
    search = _listing_search()
    scraper = saved_scraper({HOME: "nexora_home.html", CAREERS: "nexora_careers_without_role.html", LISTING: "nexora_careers_with_role.html"})
    result = run_investigation(TEXT, ScriptedClient(_extraction(), NEXORA, NOTHING), scraper, search=search)
    record = _record(result, "opportunity")
    assert record.status == "verified" and record.source_url == LISTING
    assert "confirmed by reading the page" in record.observation
    assert result.decision == "PROCEED"
    assert search.queries == ["site:nexora.example Business Analyst Internship"]


def test_a_search_snippet_alone_never_verifies():
    search = _listing_search()
    scraper = saved_scraper({HOME: "nexora_home.html", CAREERS: "nexora_careers_without_role.html", LISTING: "nexora_careers_without_role.html"})
    result = run_investigation(TEXT, ScriptedClient(_extraction(), NEXORA, NOTHING), scraper, search=search)
    assert _record(result, "opportunity").status == "unverified"
    assert result.decision == "VERIFY FIRST"


def test_search_is_not_used_when_the_careers_page_already_verifies():
    search = _listing_search()
    scraper = saved_scraper({HOME: "nexora_home.html", CAREERS: "nexora_careers_with_role.html"})
    run_investigation(TEXT, ScriptedClient(_extraction(), NEXORA, ROLE_LISTED), scraper, search=search)
    assert search.queries == []  # searches are spent only when the normal check fails


@pytest.mark.parametrize(
    ("role", "line", "found"),
    [
        ("Business Analyst Internship", "Business Analyst Intern - Bengaluru", True),
        ("Business Analyst Internship", "Business Analyst - 3 years experience", False),
        ("Data Analyst", "Senior Data Analyst, Pune", True),
        ("Internship", "Summer internships 2026", False),  # nothing specific to look for
    ],
    ids=["intern-vs-internship", "not-an-internship", "plain-role", "too-generic"],
)
def test_role_matching(role, line, found):
    assert (role_in(role, line) is not None) == found


# The browser itself


class _Route:
    def __init__(self, url):
        self.request = type("R", (), {"url": url})()
        self.result = None

    def continue_(self):
        self.result = "continue"

    def abort(self):
        self.result = "abort"


@pytest.mark.parametrize(
    ("url", "expected"),
    [("http://127.0.0.1:8000/admin", "abort"), ("http://169.254.169.254/latest/meta-data", "abort"),
     ("file:///etc/passwd", "abort"), ("data:image/png;base64,AAAA", "continue")],
)
def test_the_browser_never_reaches_private_addresses(url, expected):
    handlers = []
    page = type("P", (), {"route": lambda self, pattern, handler: handlers.append(handler)})()
    _public_requests_only(page)
    route = _Route(url)
    handlers[0](route)
    assert route.result == expected


def test_browser_fetches_are_capped_and_count_as_fetches():
    scraper = saved_scraper({}, rendered={"https://a.example/": "nexora_home.html", "https://b.example/": "nexora_home.html"})
    scraper.max_rendered = 1
    assert scraper.fetch_rendered("https://a.example/").ok
    assert not scraper.can_render
    assert scraper.fetches == 1


def test_a_browser_that_lands_on_a_private_address_is_refused():
    class Landed:
        url = "http://10.0.0.5/"

    scraper = Scraper(get=lambda u: None, guard=lambda u: (u.startswith("https://"), "private"), render=lambda u: Landed())
    page = scraper.fetch_rendered("https://redirects.example/")
    assert not page.ok and page.failure == "private"
