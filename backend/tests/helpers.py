"""Test doubles: a model client scripted by output schema, and a scraper serving saved pages."""

from pathlib import Path

from pydantic import BaseModel

from app.investigation.challenge import ChallengePlan
from app.investigation.plan import PlanProposal
from app.llm.llm_client import LLMClient
from app.web.scraper import FetchResult, Scraper, _result

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


def saved_scraper(routes: dict[str, str | int], max_fetches: int = 8) -> Scraper:
    """routes maps a URL to a fixture file name under tests/fixtures/pages, or to an HTTP status."""

    def get(url: str):
        target = routes.get(url)
        if target is None:
            raise ConnectionError("not reachable")
        if isinstance(target, int):
            return _SavedResponse(url, "<html></html>", status=target)
        return _SavedResponse(url, (PAGES / target).read_text(encoding="utf-8"))

    return Scraper(max_fetches=max_fetches, get=get, guard=lambda url: (True, ""))


def fetched(url: str, fixture: str) -> FetchResult:
    return _result(url, url, _SavedResponse(url, (PAGES / fixture).read_text(encoding="utf-8")))
