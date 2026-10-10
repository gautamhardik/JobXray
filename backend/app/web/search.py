"""Web search through SerpAPI (Google results as JSON), used only as a fallback.

Search finds pages; it never decides anything. A result only points JobXray at
a page to read with the scraper, or at a domain the identity check must still
establish. Searches are scarce (a small monthly quota), so each investigation
gets at most MAX_SEARCHES, and every answer is cached on disk by query: running
the same investigation again, or a demo, spends nothing.
Without SERPAPI_API_KEY the search is simply off and the investigation runs as before.
See spec.md > Components > Backend > app/web/search.py.
"""

import hashlib
import json
import time
from pathlib import Path

import httpx
from pydantic import BaseModel

from app.config import MAX_SEARCHES, SEARCH_CACHE_DAYS, SERPAPI_API_KEY

SERPAPI_URL = "https://serpapi.com/search.json"
CACHE_DIR = Path(__file__).resolve().parents[2] / ".search-cache"
TIMEOUT_SECONDS = 20.0


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str = ""


class SearchAnswer(BaseModel):
    results: list[SearchResult] = []
    website: str | None = None  # the knowledge panel's website, when Google shows one
    cached: bool = False


class SearchBudgetExceeded(Exception):
    """Raised instead of a search that would exceed MAX_SEARCHES."""


def _cache_file(query: str) -> Path:
    return CACHE_DIR / f"{hashlib.sha256(query.encode('utf-8')).hexdigest()[:24]}.json"


def _parse(payload: dict) -> SearchAnswer:
    results = [
        SearchResult(title=r.get("title") or "", url=r["link"], snippet=r.get("snippet") or "")
        for r in payload.get("organic_results") or []
        if r.get("link")
    ]
    website = (payload.get("knowledge_graph") or {}).get("website")
    return SearchAnswer(results=results[:10], website=website)


class Search:
    """One instance per investigation, so the search counter is per investigation."""

    def __init__(self, max_searches: int = MAX_SEARCHES, api_key: str | None = None, http: httpx.Client | None = None):
        self.max_searches = max_searches
        self.searches = 0  # searches charged to the quota (cache hits are free)
        self._key = SERPAPI_API_KEY if api_key is None else api_key  # read when created, so tests can blank it
        self._http = http

    @property
    def enabled(self) -> bool:
        return bool(self._key) and self.max_searches > 0

    def search(self, query: str) -> SearchAnswer | None:
        """Google results for query, from the cache when possible. None when off or failed."""
        if not self.enabled:
            return None
        cache = _cache_file(query)
        try:
            saved = json.loads(cache.read_text(encoding="utf-8"))
            if time.time() - saved["saved_at"] < SEARCH_CACHE_DAYS * 86400:
                return SearchAnswer.model_validate(saved["answer"]).model_copy(update={"cached": True})
        except (OSError, ValueError, KeyError):
            pass

        if self.searches >= self.max_searches:
            raise SearchBudgetExceeded(f"Search budget of {self.max_searches} reached.")
        self.searches += 1
        try:
            client = self._http or httpx.Client(timeout=TIMEOUT_SECONDS)
            response = client.get(SERPAPI_URL, params={"engine": "google", "q": query, "num": 10, "api_key": self._key})
            if response.status_code != 200:
                return None
            answer = _parse(response.json())
        except (httpx.HTTPError, ValueError):
            return None
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({"saved_at": time.time(), "query": query, "answer": answer.model_dump()}), encoding="utf-8")
        except OSError:
            pass
        return answer
