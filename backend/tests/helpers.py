"""Test doubles: a model client scripted by output schema, and a scraper serving saved pages."""

from pathlib import Path

from pydantic import BaseModel

from app.investigation.challenge import ChallengePlan
from app.investigation.plan import PlanProposal
from app.llm.llm_client import LLMClient
from app.web.scraper import FetchResult, Scraper, _result
from app.web.search import Search, SearchAnswer, SearchBudgetExceeded

PAGES = Path(__file__).parent / "fixtures" / "pages"


class ScriptedClient(LLMClient):
    """Answers each call with the scripted object for its output schema."""

    def __init__(self, *answers: BaseModel, transcription: str = "", max_calls: int | None = None):
        super().__init__() if max_calls is None else super().__init__(max_calls=max_calls)
        self.answers = {type(a): a for a in answers}
        self.answers.setdefault(PlanProposal, PlanProposal(official_domain=None, questions=[]))
        self.answers.setdefault(ChallengePlan, ChallengePlan(hypotheses=[]))
        self.transcription = transcription

    def read_image(self, system, instruction, image_data_url, max_tokens=4000):
        if self.calls >= self.max_calls:
            from app.llm.llm_client import ModelBudgetExceeded

            raise ModelBudgetExceeded("budget")
        self.calls += 1
        return self.transcription

    def structured(self, system, user, output_format, max_tokens=8000):
        if self.calls >= self.max_calls:
            from app.llm.llm_client import ModelBudgetExceeded

            raise ModelBudgetExceeded("budget")
        self.calls += 1
        return self.answers[output_format].model_copy(deep=True)


class _SavedResponse:
    """Just enough of a Scrapling response for scraper._result, built from saved HTML."""

    def __init__(self, url: str, html: str, status: int = 200):
        from scrapling.parser import Selector

        self._page = Selector(html, url=url)
        self.url = url
        self.status = status
        self.headers = {}

    def css(self, selector):
        return self._page.css(selector)

    def urljoin(self, href):
        return self._page.urljoin(href)

    def get_all_text(self, **kwargs):
        return self._page.get_all_text(**kwargs)


def saved_scraper(routes: dict[str, str | int], max_fetches: int = 10, rendered: dict[str, str] | None = None) -> Scraper:
    """routes maps a URL to a fixture file name under tests/fixtures/pages, or to an HTTP status.
    rendered maps a URL to the fixture a browser would see after JavaScript runs (no browser is started)."""

    def get(url: str):
        target = routes.get(url)
        if target is None:
            raise ConnectionError("not reachable")
        if isinstance(target, int):
            return _SavedResponse(url, "<html></html>", status=target)
        return _SavedResponse(url, (PAGES / target).read_text(encoding="utf-8"))

    def render(url: str):
        if url not in (rendered or {}):
            raise ConnectionError("not reachable in the browser")
        return _SavedResponse(url, (PAGES / rendered[url]).read_text(encoding="utf-8"))

    return Scraper(max_fetches=max_fetches, get=get, guard=lambda url: (True, ""), render=render if rendered else None)


class FakeSearch(Search):
    """Answers queries from a dict of query substring to SearchAnswer; counts like the real one."""

    def __init__(self, answers: dict[str, SearchAnswer], max_searches: int = 2):
        super().__init__(max_searches=max_searches, api_key="test")
        self.answers = answers
        self.queries: list[str] = []

    def search(self, query: str) -> SearchAnswer | None:
        if self.searches >= self.max_searches:
            raise SearchBudgetExceeded("budget")
        self.searches += 1
        self.queries.append(query)
        return next((a for key, a in self.answers.items() if key in query), SearchAnswer())


def fetched(url: str, fixture: str) -> FetchResult:
    return _result(url, url, _SavedResponse(url, (PAGES / fixture).read_text(encoding="utf-8")))
