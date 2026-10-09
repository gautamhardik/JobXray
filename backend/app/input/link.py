"""Link input: fetch the job posting the person linked and return its readable text.

The page is a user-provided source, never the company's official site by itself.
The scraper's address guard refuses private and internal addresses on every hop.
LinkedIn job and post links are read through LinkedIn's public guest views (the
same pages a logged-out visitor sees), and lnkd.in short links are followed to
their target. Sign-in boxes are stripped before deciding whether anything is left.
See spec.md > Components > Backend > app/input/link.py.
"""

import re
from urllib.parse import parse_qs, unquote, urlsplit

from pydantic import BaseModel

from app.config import MAX_INPUT_CHARS
from app.input import InputUnreadable
from app.web.scraper import FetchResult, Scraper

SCREENSHOT_INSTEAD = (
    "JobXray couldn't open this page: it may need a login, or it is no longer available. "
    "Upload a screenshot of the post, or paste its text instead."
)
MIN_READABLE_CHARS = 200
LOGIN_WALL = re.compile(r"\b(sign in|log in|login|join now|create an account)\b", re.I)
LOGIN_HOSTS = ("linkedin.com", "whatsapp.com", "wa.me", "instagram.com", "facebook.com", "t.me", "telegram.me")
# Short interface lines that come with a sign-in box rather than with the posting.
LOGIN_CHROME = re.compile(
    r"^(email or phone|password|show|forgot password\?|or|new to linkedin\?|user agreement|privacy policy"
    r"|cookie policy|, and|,|\.|agree & join linkedin|skip to main content|clear text|expand search|save"
    r"|report this (job|post)|like|comment|share|share this post|join to apply for the|join to save)$",
    re.I,
)
SHORT_LOGIN_LINE = 200

LINKEDIN_JOB_ID = re.compile(r"/jobs/view/(?:[^/?#]*-)?(\d{6,})")
LINKEDIN_POST = re.compile(r"(?:urn:li:|-)(activity|share|ugcPost)[:-](\d{15,})")


class LinkedPage(BaseModel):
    url: str
    title: str | None
    text: str


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def _on(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == d or host.endswith(f".{d}") for d in domains)


def public_view(url: str) -> str | None:
    """The logged-out view LinkedIn serves for a job or post link, or None for other links."""
    if not _on(_host(url), ("linkedin.com",)):
        return None
    decoded = unquote(url)
    job = LINKEDIN_JOB_ID.search(urlsplit(decoded).path)
    job_id = job.group(1) if job else (parse_qs(urlsplit(decoded).query).get("currentJobId") or [None])[0]
    if job_id and job_id.isdigit():
        return f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    post = LINKEDIN_POST.search(decoded)
    if post:
        return f"https://www.linkedin.com/embed/feed/update/urn:li:{post.group(1)}:{post.group(2)}"
    return None


def strip_login_chrome(text: str) -> str:
    """Drop sign-in boxes and button labels, keep everything else in order."""
    kept = []
    for line in text.splitlines():
        line = line.strip()
        if not line or LOGIN_CHROME.match(line):
            continue
        if len(line) < SHORT_LOGIN_LINE and (LOGIN_WALL.search(line) or line.startswith("By clicking Continue")):
            continue
        kept.append(line)
    return "\n".join(kept)


def _readable(page: FetchResult) -> str | None:
    """The page's posting text, or None when only a login wall or too little text is left."""
    if not page.ok:
        return None
    text = page.text.strip()
    if _on(_host(page.url), LOGIN_HOSTS):
        text = strip_login_chrome(text)
        if len(LOGIN_WALL.findall(text)) >= 2:
            return None
    return text if len(text) >= MIN_READABLE_CHARS else None


def _short_link_target(page: FetchResult) -> str | None:
    """lnkd.in shows an interstitial for outside sites; its link is where the post really points."""
    if not page.ok or _host(page.url) != "lnkd.in":
        return None
    for link in page.links:
        if urlsplit(link.url).scheme in ("http", "https") and not _on(_host(link.url), ("lnkd.in", "linkedin.com")):
            return link.url
    return None


def read_link(url: str, scraper: Scraper) -> LinkedPage:
    url = url.strip()
    if urlsplit(url).scheme not in ("http", "https"):
        raise InputUnreadable("Only http and https links can be investigated.")

    page = None
    if _host(url) == "lnkd.in":
        page = scraper.fetch(url)
        target = _short_link_target(page)
        if target:
            url = target
            page = None
        elif page.ok:
            url = page.url

    # Try LinkedIn's public guest view first, then the link exactly as given.
    attempts = [u for u in (public_view(url), url) if u]
    reason = "The page needs a login or has too little readable text."
    for attempt in attempts:
        if page is None or (page.requested_url != attempt and page.url != attempt):
            page = scraper.fetch(attempt)
        text = _readable(page)
        if text:
            # A guest view is read on the person's behalf; the evidence keeps the link they gave.
            return LinkedPage(url=page.url if attempt == url else url, title=page.title, text=text[:MAX_INPUT_CHARS])
        if not page.ok and page.failure:
            reason = page.failure

    raise InputUnreadable(f"{SCREENSHOT_INSTEAD} ({reason})")
