"""
Named OpenRouter LLM opponents, shared by the web chooser (`app.py`) and the
tournament CLI (`tournament.py`).

Each named opponent maps to a concrete OpenRouter model id. Those ids drift over
time, so every one stays overridable via an environment variable without touching
code. Keeping the registry here is the single source of truth so the web app and a
tournament always agree on which model "kimi"/"haiku" mean.

An opponent may also pin a system-prompt version (see `game/llm_prompts.py`).
`gemini` and `gemini-opus` are the same model behind different prompts — enter
both in one tournament and the rating gap measures the prompt alone.
"""

import os

from .llm_prompts import DEFAULT_VERSION

# One shared spec so an env override moves every Gemini entrant together —
# otherwise the prompt A/B silently becomes a model comparison.
_GEMINI = {"env": "CAMBIO_GEMINI_MODEL", "default": "google/gemini-3.1-flash-lite"}

NAMED_LLM_OPPONENTS = {
    "kimi":  {"name": "Kimi K2 (LLM)",      "env": "CAMBIO_KIMI_MODEL",  "default": "moonshotai/kimi-k2"},
    "haiku": {"name": "Claude Haiku (LLM)", "env": "CAMBIO_HAIKU_MODEL", "default": "anthropic/claude-haiku-4.5"},
    "gemini":      {"name": "Gemini Flash (LLM)", **_GEMINI},
    "gemini-opus": {"name": "Gemini Flash · Opus prompt (LLM)", **_GEMINI,
                    "prompt": "opus"},
}


def llm_model(key):
    """Resolve a named opponent key to its OpenRouter model id (env override wins)."""
    spec = NAMED_LLM_OPPONENTS[key]
    return os.environ.get(spec["env"]) or spec["default"]


def llm_prompt(key):
    """Resolve a named opponent key to its system-prompt version."""
    return NAMED_LLM_OPPONENTS[key].get("prompt", DEFAULT_VERSION)
