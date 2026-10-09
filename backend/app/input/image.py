"""Screenshot input: transcribe the image with the vision model.

The person sees the transcription, and every excerpt is checked against it.
An unreadable image is an error, never a guess.
See spec.md > Components > Backend > app/input/image.py.
"""

import base64
import binascii
import re
from pathlib import Path

from app.config import MAX_IMAGE_BYTES, MAX_INPUT_CHARS, MAX_SCREENSHOTS
from app.input import InputUnreadable
from app.llm.llm_client import LLMClient

PROMPT = (Path(__file__).parent.parent / "prompts" / "transcribe.md").read_text(encoding="utf-8")
DATA_URL = re.compile(r"^data:image/(png|jpeg|jpg|webp);base64,(.+)$", re.S)
SIGNATURES = {
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpeg": (b"\xff\xd8\xff",),
    "jpg": (b"\xff\xd8\xff",),
    "webp": (b"RIFF",),
}


def validate_image(data_url: str) -> None:
    """PNG, JPEG, or WebP as a base64 data URL, at most MAX_IMAGE_BYTES. Checked before any model call."""
    match = DATA_URL.match(data_url.strip())
    if not match:
        raise InputUnreadable("Only PNG, JPEG, or WebP screenshots can be investigated.")
    kind, encoded = match.groups()
    if len(encoded) * 3 // 4 > MAX_IMAGE_BYTES:
        raise InputUnreadable("That screenshot is larger than 4 MB. Crop it or take a smaller one.")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise InputUnreadable("That screenshot could not be read. Try pasting it again.")
    if len(raw) > MAX_IMAGE_BYTES:
        raise InputUnreadable("That screenshot is larger than 4 MB. Crop it or take a smaller one.")
    if not raw.startswith(SIGNATURES[kind]):
        raise InputUnreadable("That file is not a valid image.")


def transcribe(data_urls: str | list[str], client: LLMClient) -> str:
    """One call for up to MAX_SCREENSHOTS screenshots, read in the order given."""
    urls = [data_urls] if isinstance(data_urls, str) else list(data_urls)
    if not urls:
        raise InputUnreadable("Add a screenshot before investigating.")
    if len(urls) > MAX_SCREENSHOTS:
        raise InputUnreadable(f"Add at most {MAX_SCREENSHOTS} screenshots at a time.")
    for url in urls:
        validate_image(url)
    instruction = (
        "Transcribe all the text in this screenshot."
        if len(urls) == 1
        else f"Transcribe all the text in these {len(urls)} screenshots, in order. They are one conversation or post."
    )
    text = client.read_image(PROMPT, instruction, [u.strip() for u in urls])
    if not text or text.strip() == "NO_TEXT":
        raise InputUnreadable("JobXray couldn't read any text in that screenshot. Paste the text instead.")
    return text[:MAX_INPUT_CHARS]
