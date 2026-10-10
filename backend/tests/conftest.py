"""Tests never launch a real browser or spend a real search, whatever is in backend/.env."""

import pytest


@pytest.fixture(autouse=True)
def no_real_browser_or_search(monkeypatch):
    def no_browser(url):
        raise AssertionError(f"a test tried to open {url} in a real browser")

    monkeypatch.setattr("app.web.scraper._scrapling_render", no_browser)
    monkeypatch.setattr("app.web.search.SERPAPI_API_KEY", "")
