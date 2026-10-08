"""Link input: fetch the job posting the person linked and return its readable text.

The page is a user-provided source, never the company's official site by itself.
The scraper's address guard refuses private and internal addresses on every hop.
See spec.md > Components > Backend > app/input/link.py.
"""

import re
from urllib.parse import urlsplit

from pydantic import BaseModel

from app.config import MAX_INPUT_CHARS
from app.input import InputUnreadable
from app.web.scraper import Scraper

PASTE_INSTEAD = "JobXray couldn't read this page. Paste the text instead."
MIN_READABLE_CHARS = 200
LOGIN_WALL = re.compile(r"\b(sign in|log in|login|join now|create an account)\b", re.I)
LOGIN_HOSTS = ("linkedin.com", "whatsapp.com", "wa.me", "instagram.com", "facebook.com", "t.me", "telegram.me")


class LinkedPage(BaseModel):
    url: str
    title: str | None
    text: str


def read_link(url: str, scraper: Scraper) -> LinkedPage:
    url = url.strip()
    if urlsplit(url).scheme not in ("http", "https"):
        raise InputUnreadable("Only http and https links can be investigated.")

    page = scraper.fetch(url)
    if not page.ok:
        raise InputUnreadable(f"{PASTE_INSTEAD} ({page.failure})")

    host = urlsplit(page.url).hostname or ""
    text = page.text.strip()
    behind_login = any(host == h or host.endswith(f".{h}") for h in LOGIN_HOSTS) and (
        len(text) < 1500 or len(LOGIN_WALL.findall(text)) >= 2
    )
    if len(text) < MIN_READABLE_CHARS or behind_login:
        raise InputUnreadable(f"{PASTE_INSTEAD} (The page needs a login or has too little readable text.)")

    return LinkedPage(url=page.url, title=page.title, text=text[:MAX_INPUT_CHARS])
