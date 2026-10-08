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

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "")

FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",")
