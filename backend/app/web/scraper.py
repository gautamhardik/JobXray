"""Scrapling wrapper: fetch a page, keep its readable text and links, never raise on failure.

Every fetch counts against the per-investigation budget (MAX_FETCHES), and every
hop is checked so JobXray never fetches private or internal addresses.
See spec.md > Components > Backend > app/web/scraper.py.

Scrapling 0.4.15 API used (checked against the installed package):
`Fetcher.get(url, timeout=, retries=, follow_redirects=)` returns a response with
`.status`, `.url`, `.headers`, `.css(selector)` (elements with `.attrib` / `.text`),
`.urljoin(href)` and `.get_all_text(strip=True)`. Network failures raise
`curl_cffi` exceptions.
"""

import ipaddress
import socket
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

from app.config import MAX_FETCHES, MAX_RENDERED_FETCHES, RENDER_PAGES

PAGE_TEXT_LIMIT = 20_000
TIMEOUT_SECONDS = 20
MAX_REDIRECTS = 4
RENDER_WAIT_MS = 3000
RENDER_TIMEOUT_MS = 15_000
WEB_PAGE_TYPES = ("html", "text/plain", "xml")


class FetchBudgetExceeded(Exception):
    """Raised instead of a fetch that would exceed MAX_FETCHES."""


class PageLink(BaseModel):
    url: str
    text: str


class FetchResult(BaseModel):
    requested_url: str
    url: str
    ok: bool
    status: int | None = None
    title: str | None = None
    text: str = ""
    links: list[PageLink] = Field(default_factory=list)
    failure: str | None = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def is_public_url(url: str) -> tuple[bool, str]:
    """Only http(s) URLs whose host resolves exclusively to public addresses."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return False, "Only http and https links can be checked."
    host = parts.hostname
    if not host:
        return False, "The link has no host name."
    try:
        infos = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80))
    except socket.gaierror:
        return False, "The site's address could not be found."
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            return False, "That address points to a private or internal network, so JobXray will not fetch it."
    return True, ""


def _scrapling_get(url: str) -> Any:
    from scrapling.fetchers import Fetcher

    return Fetcher.get(url, timeout=TIMEOUT_SECONDS, retries=1, follow_redirects=False)


def _public_requests_only(page: Any) -> None:
    """Inside the browser, every request (redirects, scripts, XHR) must go to a public address too."""
    verdicts: dict[str, bool] = {}

    def handle(route: Any) -> None:
        url = route.request.url
        scheme = urlsplit(url).scheme
        if scheme in ("data", "blob"):
            return route.continue_()
        host = urlsplit(url).hostname or ""
        if host not in verdicts:
            verdicts[host] = scheme in ("http", "https") and is_public_url(url)[0]
        return route.continue_() if verdicts[host] else route.abort()

    page.route("**/*", handle)


def _scrapling_render(url: str) -> Any:
    """The page after its JavaScript has run, read in headless Chromium (Scrapling's DynamicFetcher)."""
    from scrapling.fetchers import DynamicFetcher

    return DynamicFetcher.fetch(
        url,
        headless=True,
        network_idle=False,  # tracker-heavy sites never go idle; a short fixed wait is enough
        load_dom=False,  # measured: same text, about 8 s faster than waiting for every script
        wait=RENDER_WAIT_MS,
        disable_resources=True,  # no images, fonts or media: faster, same text
        timeout=RENDER_TIMEOUT_MS,
        page_setup=_public_requests_only,
    )


class Scraper:
    """One instance per investigation, so the fetch counter is per investigation."""

    def __init__(
        self,
        max_fetches: int = MAX_FETCHES,
        get: Callable[[str], Any] = _scrapling_get,
        guard: Callable[[str], tuple[bool, str]] = is_public_url,
        render: Callable[[str], Any] | None | str = "default",
        max_rendered: int = MAX_RENDERED_FETCHES,
    ):
        self.max_fetches = max_fetches
        self.fetches = 0
        self.rendered = 0
        self.max_rendered = max_rendered
        self._get = get
        self._guard = guard
        # Looked up when called, so tests can swap the real browser out.
        self._render = (lambda url: _scrapling_render(url)) if render == "default" and RENDER_PAGES else (None if render == "default" else render)

    @property
    def can_render(self) -> bool:
        return self._render is not None and self.rendered < self.max_rendered and self.remaining > 0

    def fetch_rendered(self, url: str) -> FetchResult:
        """Read a page in a real browser, for pages that only show their text after JavaScript runs.
        Counts against the fetch budget and against MAX_RENDERED_FETCHES."""
        if not self.can_render:
            raise FetchBudgetExceeded("Browser-fetch budget reached.")
        self.fetches += 1
        self.rendered += 1
        allowed, reason = self._guard(url)
        if not allowed:
            return FetchResult(requested_url=url, url=url, ok=False, failure=reason)
        try:
            response = self._render(url)
        except Exception:  # browser launch, navigation timeout, crash
            return FetchResult(requested_url=url, url=url, ok=False, failure="The page could not be opened in the browser.")
        final = str(getattr(response, "url", "") or url)
        allowed, reason = self._guard(final)
        if not allowed:
            return FetchResult(requested_url=url, url=final, ok=False, failure=reason)
        return _result(url, final, response)

    @property
    def remaining(self) -> int:
        return self.max_fetches - self.fetches

    def fetch(self, url: str) -> FetchResult:
        if self.fetches >= self.max_fetches:
            raise FetchBudgetExceeded(f"Fetch budget of {self.max_fetches} reached.")
        self.fetches += 1

        current = url
        for _ in range(MAX_REDIRECTS + 1):
            allowed, reason = self._guard(current)
            if not allowed:
                return FetchResult(requested_url=url, url=current, ok=False, failure=reason)
            try:
                response = self._get(current)
            except Exception:  # curl_cffi DNS, TLS, timeout, connection errors
                return FetchResult(requested_url=url, url=current, ok=False, failure="The page could not be reached.")

            status = getattr(response, "status", None)
            if status in (301, 302, 303, 307, 308):
                location = (getattr(response, "headers", {}) or {}).get("location")
                if not location:
                    break
                current = response.urljoin(location)
                continue
            return _result(url, current, response)

        return FetchResult(requested_url=url, url=current, ok=False, failure="The page redirected too many times.")


def _result(requested: str, url: str, response: Any) -> FetchResult:
    status = response.status
    if status is None or status >= 400:
        return FetchResult(
            requested_url=requested,
            url=url,
            ok=False,
            status=status,
            failure=f"The site refused or blocked the request (HTTP {status}).",
        )

    content_type = str((getattr(response, "headers", {}) or {}).get("content-type") or "").lower()
    if content_type and not any(t in content_type for t in WEB_PAGE_TYPES):
        kind = "a PDF" if "pdf" in content_type else "an image" if content_type.startswith("image/") else "a file"
        return FetchResult(
            requested_url=requested,
            url=url,
            ok=False,
            status=status,
            failure=f"The link opens {kind}, not a web page.",
        )
    try:
        return _parsed(requested, url, response)
    except (UnicodeDecodeError, ValueError):  # bytes that are not really HTML
        return FetchResult(requested_url=requested, url=url, ok=False, status=status, failure="The page's content could not be read as text.")


def _parsed(requested: str, url: str, response: Any) -> FetchResult:
    status = response.status
    titles = response.css("title")
    links: list[PageLink] = []
    seen: set[str] = set()
    for element in response.css("a"):
        href = (element.attrib.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = response.urljoin(href)
        if absolute in seen:
            continue
        seen.add(absolute)
        text = " ".join(str(element.get_all_text(strip=True)).split())[:120]
        links.append(PageLink(url=absolute, text=text))

    return FetchResult(
        requested_url=requested,
        url=url,
        ok=True,
        status=status,
        title=" ".join(str(titles[0].text).split()) if titles else None,
        text=str(response.get_all_text(strip=True))[:PAGE_TEXT_LIMIT],
        links=links,
    )
