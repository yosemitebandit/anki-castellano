"""Shared utilities for the three anki-castellano scripts."""

import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def make_client():
    from google import genai

    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_GENAI_API_KEY")
    if not key:
        sys.exit("No API key found. Set GEMINI_API_KEY in .env")
    return genai.Client(api_key=key)


def load_vocab(path: str | Path) -> list:
    return json.loads(Path(path).read_text())
