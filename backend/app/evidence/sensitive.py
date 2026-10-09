"""Requests for sensitive information, told apart by what is asked for.

Secrets that unlock money or accounts (an OTP, a PIN, card details, a password)
are never needed to hire anyone, so asking for them is a Stop on its own.
Identity and bank documents can be legitimate after a confirmed offer, so they
only hold back a Proceed. A sentence warning people NOT to share these is not a request.
"""

import re

CREDENTIAL = re.compile(
    r"\b(otp|one[- ]time password|verification code|upi pin|atm pin|card pin|m-?pin|cvv|card number|card details|"
    r"net ?banking|password|login details|remote access|anydesk|teamviewer)\b",
    re.I,
)
REFUSAL = re.compile(
    r"\b(never|do not|don't|does not|doesn't|will not|won't|not)\s+(ask|share|request|collect|need|require|give)\w*\b",
    re.I,
)


def is_refusal(text: str) -> bool:
    return bool(REFUSAL.search(text))


def asks_for_credentials(text: str) -> bool:
    return bool(CREDENTIAL.search(text)) and not is_refusal(text)
