"""Limits and settings for JobXray, kept in one place.

See spec.md > Components > Backend > app/config.py.
"""

import os

from dotenv import load_dotenv

load_dotenv()

MAX_INPUT_CHARS = 10_000
MAX_FETCHES = 8
MAX_MODEL_CALLS = 4
MAX_MODEL_CALLS_IMAGE = 5  # one extra call to transcribe a screenshot
MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_SCREENSHOTS = 3  # read together in the same single transcription call
CHALLENGE_ROUNDS = 1

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
VISION_MODEL = os.getenv("VISION_MODEL", "dots-studio/dots-3-note-preview:free")

FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",")
