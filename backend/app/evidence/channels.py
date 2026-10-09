"""Recruiter emails and application links, compared with the company's official domain.

Plain string checks, no model. A personal webmail address or a form or link
shortener holds back a Proceed. An address that dresses the company's name up as
a hiring domain (infosys-careers.com when the official site is infosys.com) is an
identity contradiction, which the rules treat as a Stop.
"""

import re
from urllib.parse import urlsplit

from pydantic import BaseModel

from app.investigation.plan import ATS_HOSTS, HOSTING_PLATFORMS, LOOKALIKE_WORDS, _company_tokens, registrable

EMAIL = re.compile(r"\b[\w.+-]+@((?:[\w-]+\.)+[a-z]{2,})\b", re.I)
URL = re.compile(r"\b(?:https?://|www\.)[^\s<>\"')\]]+", re.I)
WEBMAIL = (
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "ymail.com", "outlook.com", "hotmail.com",
    "live.com", "rediffmail.com", "proton.me", "protonmail.com", "icloud.com", "aol.com", "zoho.com",
)
FORMS_AND_SHORTENERS = (
    "forms.gle", "docs.google.com", "bit.ly", "tinyurl.com", "cutt.ly", "rb.gy", "shorturl.at",
    "t.ly", "is.gd", "rebrand.ly", "jotform.com", "typeform.com", "forms.office.com", *HOSTING_PLATFORMS,
)
# Places where real companies also post jobs; a link there is not a mismatch by itself.
JOB_PLATFORMS = (
    "linkedin.com", "lnkd.in", "naukri.com", "internshala.com", "indeed.com", "glassdoor.com", "glassdoor.co.in",
    "foundit.in", "unstop.com", "wellfound.com", "instahyre.com", "cutshort.io", "hirist.tech", *ATS_HOSTS,
)
# Group-chat links are already part of the recruitment funnel, not a domain question.
CHAT_HOSTS = ("whatsapp.com", "wa.me", "t.me", "telegram.me", "telegram.org", "discord.gg", "discord.com")


class ChannelFinding(BaseModel):
    kind: str  # "impersonation" or "caution"
    claim: str
    observation: str
    excerpt: str


def _on(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == d or host.endswith(f".{d}") for d in domains)


def _host(url: str) -> str:
    return (urlsplit(url if "//" in url else f"//{url}").hostname or "").lower().removeprefix("www.")


def looks_like(host: str, company: str, official: str) -> bool:
    """The company's name dressed up as a hiring domain, but not the official site."""
    if registrable(host) == registrable(official):
        return False
    label = registrable(host).split(".")[0]
    token = next((t for t in _company_tokens(company) if len(t) >= 3 and t in label), None)
    if token is None:
        return False
    return "-" in label or bool(LOOKALIKE_WORDS.search(label.replace(token, "")))


def check_channels(text: str, company: str | None, official: str | None, application_links: list[str]) -> list[ChannelFinding]:
    findings: list[ChannelFinding] = []
    if not company:
        return findings
    seen: set[str] = set()

    for match in EMAIL.finditer(text):
        address, domain = match.group(0), match.group(1).lower()
        if address in seen:
            continue
        seen.add(address)
        if _on(domain, WEBMAIL):
            findings.append(ChannelFinding(
                kind="caution",
                claim=f"Recruiter contact: {address}",
                observation=f"The recruiter writes from a personal email address, not a {company} company address.",
                excerpt=address,
            ))
        elif official and looks_like(domain, company, official):
            findings.append(ChannelFinding(
                kind="impersonation",
                claim=f"Recruiter contact: {address}",
                observation=f"{domain} imitates {company}'s official domain ({official}) but is not part of it.",
                excerpt=address,
            ))
        elif official and registrable(domain) != registrable(official):
            findings.append(ChannelFinding(
                kind="caution",
                claim=f"Recruiter contact: {address}",
                observation=f"The recruiter's email domain ({domain}) is not {company}'s official domain ({official}).",
                excerpt=address,
            ))

    links = [(m.group(0).rstrip(".,;:!?"), False) for m in URL.finditer(text)]
    links += [(link, True) for link in application_links]
    for link, is_application in links:
        host = _host(link)
        if not host or host in seen or _on(host, CHAT_HOSTS) or _on(host, JOB_PLATFORMS):
            continue
        seen.add(host)
        if official and looks_like(host, company, official):
            findings.append(ChannelFinding(
                kind="impersonation",
                claim=f"Link in the message: {host}",
                observation=f"{host} imitates {company}'s official domain ({official}) but is not part of it.",
                excerpt=link,
            ))
        elif _on(host, FORMS_AND_SHORTENERS):
            findings.append(ChannelFinding(
                kind="caution",
                claim=f"Application link: {host}",
                observation=f"The link goes to {host}, a form or link service anyone can use, not {company}'s own site.",
                excerpt=link,
            ))
        elif is_application and official and registrable(host) != registrable(official):
            findings.append(ChannelFinding(
                kind="caution",
                claim=f"Application link: {host}",
                observation=f"The application link is not on {company}'s official site ({official}).",
                excerpt=link,
            ))
    return findings
