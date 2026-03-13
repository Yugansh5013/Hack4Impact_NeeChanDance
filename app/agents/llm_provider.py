"""
Chakravyuh — Groq LLM Provider with Round-Robin Key Rotation
==============================================================
Reads GROQ_API_KEYS (comma-separated) from the environment.
Each call to ``get_llm()`` picks the next key in rotation.
On a RateLimitError the caller can retry — the next call
automatically uses a different key.
"""

from __future__ import annotations

import os
import threading
from typing import Optional

from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()  # load .env at import time

# ---------------------------------------------------------------------------
# Key Rotation
# ---------------------------------------------------------------------------

_keys: list[str] = [
    k.strip()
    for k in os.getenv("GROQ_API_KEYS", "").split(",")
    if k.strip()
]

if not _keys:
    raise RuntimeError(
        "GROQ_API_KEYS env var is missing or empty. "
        "Set it to a comma-separated list of Groq API keys."
    )

_index: int = 0
_lock = threading.Lock()


def _next_key() -> str:
    """Thread-safe round-robin key selection."""
    global _index
    with _lock:
        key = _keys[_index % len(_keys)]
        _index += 1
    return key


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "llama-3.3-70b-versatile"


def get_llm(
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_retries: int = 2,
) -> ChatGroq:
    """
    Return a ``ChatGroq`` instance using the next API key in rotation.

    Parameters
    ----------
    model : str
        Groq model identifier.
    temperature : float
        Sampling temperature (0 = deterministic, 1 = creative).
    max_retries : int
        LangChain-level retries on transient errors.

    Returns
    -------
    ChatGroq
        Ready-to-invoke LLM client.
    """
    return ChatGroq(
        api_key=_next_key(),
        model=model,
        temperature=temperature,
        max_retries=max_retries,
    )


def get_total_keys() -> int:
    """Return the number of loaded API keys (useful for retry logic)."""
    return len(_keys)
