"""Recognise statements that a company does NOT charge candidates.

Used two ways: a no-fee statement in the pasted text is never a payment request,
and an official no-fee statement contradicts a payment request.
"""

import re

NO_FEE_POLICY = re.compile(
    r"(never|do not|don't|does not|doesn't|will not|won't|not)\s+(charge|ask|request|collect)\w*\b[^.]{0,80}\b(fee|fees|money|payment|deposit)"
    r"|\b(no|zero)\s+(registration\s+|application\s+|recruitment\s+)?(fee|fees|charges?)\b[^.]{0,60}\b(candidate|applicant|recruit|hiring|interview|job)"
    r"|\b(free of (cost|charge)|no cost to (you|candidates|applicants))\b",
    re.I,
)


def is_no_fee_statement(text: str) -> bool:
    return bool(NO_FEE_POLICY.search(text))
