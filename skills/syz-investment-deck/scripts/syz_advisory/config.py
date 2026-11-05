"""Workspace paths, settings from .env, and logging setup."""

import logging
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv not installed yet
    load_dotenv = None

ROOT = Path(__file__).resolve().parents[2]
# SYZ_DATA moves inputs, outputs and caches elsewhere -- used by the packaged
# claude.ai skill, whose own folder is read-only.
DATA = Path(os.environ["SYZ_DATA"]) if os.environ.get("SYZ_DATA") else ROOT / "data"
# Tool codes (see INDEX.html): B01 Merle reader, G01 SP screener, R01 portfolio
# proposal, O01 presentation generator, O02 Investment Solutions decks, P01 earnings surprise
# detection, P02 technical review, S00 shared resources.
CODES = ("B01", "G01", "R01", "O01", "O02", "P01", "P02", "S00")

if load_dotenv:
    load_dotenv(ROOT / ".env")


def inputs(code: str) -> Path:
    """data/<code>/in — the tool's input files."""
    if code not in CODES:
        raise ValueError(f"unknown tool code {code!r}")
    return DATA / code / "in"


def outputs(code: str) -> Path:
    """data/<code>/out — everything the tool writes."""
    if code not in CODES:
        raise ValueError(f"unknown tool code {code!r}")
    return DATA / code / "out"


def get(key: str, default: str | None = None) -> str | None:
    """Return a setting from the environment / .env file."""
    return os.getenv(key, default)


def get_logger(name: str) -> logging.Logger:
    logging.basicConfig(
        level=get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return logging.getLogger(name)
