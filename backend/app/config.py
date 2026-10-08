"""Limits and settings for JobXray, kept in one place.

See spec.md > Components > Backend > app/config.py.
"""

import os

from dotenv import load_dotenv

load_dotenv()

MAX_INPUT_CHARS = 10_000
MAX_FETCHES = 8
MAX_MODEL_CALLS = 4
CHALLENGE_ROUNDS = 1

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")

FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",")
