"""Quote check: a quoted passage counts only if it really appears in its source.

Used for excerpts from the pasted text (slice 2) and passages from fetched pages
(slice 4). Whitespace and letter case are normalized; wording is not.
"""

import re

_SPACE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _SPACE.sub(" ", text).strip().casefold()


def quote_in_text(quote: str, source: str) -> bool:
    quote = _normalize(quote)
    return bool(quote) and quote in _normalize(source)
