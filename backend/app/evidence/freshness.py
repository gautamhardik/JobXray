"""Is the post still current? Plain date arithmetic, no model.

Clues come from the extracted claims (posted date, deadline, eligible batch) and
from the source text itself: LinkedIn prints a post's age on its own line ("3 weeks
ago", "3y") and marks closed jobs "No longer accepting applications". An outdated
post is not a scam signal; it holds back a Proceed and changes the advice.
"""

import re
from datetime import date, timedelta

from pydantic import BaseModel

STALE_AFTER_DAYS = 30

CLOSED = re.compile(r"no longer accepting applications|applications? (are|is) (now )?closed|this job (is|has) (expired|closed)", re.I)
UNITS = {
    "minute": 0, "min": 0, "m": 0, "hour": 0, "hr": 0, "h": 0,
    "day": 1, "d": 1, "week": 7, "wk": 7, "w": 7,
    "month": 30, "mo": 30, "year": 365, "yr": 365, "y": 365,
}
LONG_AGE = re.compile(r"\b(\d+|an?)\s+(minute|min|hour|hr|day|week|wk|month|year|yr)s?\s+ago\b", re.I)
AGE_LABEL = re.compile(r"^((re)?posted|active)?\s*(\d+|an?)\s+(minute|min|hour|hr|day|week|wk|month|year|yr)s?\s+ago\.?$", re.I)
SHORT_AGE_LINE = re.compile(r"^(\d{1,2})\s?(mo|yr|y|w|d|h|m)\b(\s*[•·].*)?$", re.I)
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1
)}
DAY_MONTH_YEAR = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3})[a-z]*\.?,?\s+(\d{4})\b", re.I)
MONTH_DAY_YEAR = re.compile(r"\b([a-z]{3})[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", re.I)
NUMERIC = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b|\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")
YEAR = re.compile(r"\b(20\d{2})\b")


class FreshnessFinding(BaseModel):
    observation: str
    excerpt: str | None = None
    closed: bool = False


def _date(text: str) -> date | None:
    """A calendar date written with its year. Numeric dates are read day first, as in India."""
    try:
        if m := NUMERIC.search(text):
            if m.group(1):
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return date(int(m.group(6)), int(m.group(5)), int(m.group(4)))
        if (m := DAY_MONTH_YEAR.search(text)) and m.group(2).lower() in MONTHS:
            return date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
        if (m := MONTH_DAY_YEAR.search(text)) and m.group(1).lower() in MONTHS:
            return date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2)))
    except ValueError:  # 31 Feb and similar
        return None
    return None


def _age_days(text: str) -> int | None:
    """An age such as "3 weeks ago", "a month ago", or LinkedIn's "2mo" / "3y"."""
    text = text.strip()
    if m := LONG_AGE.search(text):
        count = 1 if m.group(1).lower() in ("a", "an") else int(m.group(1))
        return count * UNITS[m.group(2).lower()]
    if m := SHORT_AGE_LINE.match(text):
        return int(m.group(1)) * UNITS[m.group(2).lower()]
    return None


def _ago(days: int) -> str:
    if days >= 365:
        years = days // 365
        return f"about {years} year{'s' if years > 1 else ''}"
    if days >= 60:
        return f"about {days // 30} months"
    return f"{days} days"


def check_freshness(claims, source_text: str, today: date | None = None) -> FreshnessFinding | None:
    """The strongest sign that the post is outdated or closed, or None when nothing says so."""
    today = today or date.today()

    closed = CLOSED.search(source_text)
    if closed:
        line = next((l.strip() for l in source_text.splitlines() if closed.group(0).lower() in l.lower()), closed.group(0))
        return FreshnessFinding(observation="The post says it is no longer accepting applications.", excerpt=line[:200], closed=True)

    deadlines = [(c, _date(c.value) or _date(c.excerpt)) for c in claims if c.kind == "deadline"]
    deadlines = [(c, d) for c, d in deadlines if d]
    if deadlines and all(d < today for _, d in deadlines):
        claim, last = max(deadlines, key=lambda x: x[1])
        return FreshnessFinding(
            observation=f"The application deadline ({last:%d %b %Y}) passed {_ago((today - last).days)} ago.",
            excerpt=claim.excerpt,
            closed=True,
        )

    ages: list[tuple[int, str]] = []
    for claim in claims:
        if claim.kind != "posted_date":
            continue
        posted = _date(claim.value) or _date(claim.excerpt)
        days = (today - posted).days if posted else _age_days(claim.value) or _age_days(claim.excerpt)
        if days is not None:
            ages.append((days, claim.excerpt))
    for line in source_text.splitlines()[:80]:  # a page's own age label sits near the top
        line = line.strip()
        if (AGE_LABEL.match(line) or SHORT_AGE_LINE.match(line)) and (days := _age_days(line)) is not None:
            ages.append((days, line))
    if ages:
        days, excerpt = min(ages)  # the most recent date wins
        if days > STALE_AFTER_DAYS:
            return FreshnessFinding(observation=f"The post is {_ago(days)} old, so the opening may already be filled.", excerpt=excerpt)
        return None

    batches = [c for c in claims if c.kind == "eligible_batch"]
    years = [int(y) for c in batches for y in YEAR.findall(f"{c.value} {c.excerpt}")]
    if years and max(years) < today.year:
        return FreshnessFinding(
            observation=f"The post is for the {', '.join(str(y) for y in sorted(set(years)))} batch, which has already graduated, so it is likely old.",
            excerpt=batches[0].excerpt,
        )
    return None
