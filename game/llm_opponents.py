"""
Named OpenRouter LLM opponents, shared by the web chooser (`app.py`) and the
tournament CLI (`tournament.py`).

Each named opponent maps to a concrete OpenRouter model id. Those ids drift over
time, so every one stays overridable via an environment variable without touching
code. Keeping the registry here is the single source of truth so the web app and a
tournament always agree on which model "kimi"/"haiku" mean.
"""

import os

NAMED_LLM_OPPONENTS = {
    "kimi":  {"name": "Kimi K2 (LLM)",      "env": "CAMBIO_KIMI_MODEL",  "default": "moonshotai/kimi-k2"},
    "haiku": {"name": "Claude Haiku (LLM)", "env": "CAMBIO_HAIKU_MODEL", "default": "anthropic/claude-haiku-4.5"},
}


def llm_model(key):
    """Resolve a named opponent key to its OpenRouter model id (env override wins)."""
    spec = NAMED_LLM_OPPONENTS[key]
    return os.environ.get(spec["env"]) or spec["default"]
