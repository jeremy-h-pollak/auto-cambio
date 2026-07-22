"""
Named OpenRouter LLM opponents, shared by the web chooser (`app.py`) and the
tournament CLI (`tournament.py`).

Each named opponent maps to a concrete OpenRouter model id and a system-prompt
version (`game/llm_prompts.py`). Model ids drift over time, so every one stays
overridable via an environment variable without touching code. Keeping the registry
here is the single source of truth so the web app and a tournament always agree on
which model "kimi"/"haiku"/"gemini" mean.

Two entries may share a model and differ only in `prompt` — that is how a prompt
change ships: `gemini` (v1) and `gemini-v2` are the same model under two prompts, so
entering both in one tournament measures the prompt itself. They deliberately read
the *same* env var, so overriding the model moves both and keeps the A/B honest.
"""

import os

from .llm_prompts import DEFAULT_VERSION

_GEMINI = {"env": "CAMBIO_GEMINI_MODEL", "default": "google/gemini-3.1-flash-lite"}

NAMED_LLM_OPPONENTS = {
    "kimi":  {"name": "Kimi K2 (LLM)",      "env": "CAMBIO_KIMI_MODEL",  "default": "moonshotai/kimi-k2"},
    "haiku": {"name": "Claude Haiku (LLM)", "env": "CAMBIO_HAIKU_MODEL", "default": "anthropic/claude-haiku-4.5"},
    "gemini":    {"name": "Gemini Flash (LLM)",    **_GEMINI},
    "gemini-v2": {"name": "Gemini Flash V2 (LLM)", **_GEMINI, "prompt": "v2"},
}


def llm_model(key):
    """Resolve a named opponent key to its OpenRouter model id (env override wins)."""
    spec = NAMED_LLM_OPPONENTS[key]
    return os.environ.get(spec["env"]) or spec["default"]


def llm_prompt(key):
    """Resolve a named opponent key to its system-prompt version (default: v1)."""
    return NAMED_LLM_OPPONENTS[key].get("prompt", DEFAULT_VERSION)
