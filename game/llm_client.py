"""
Thin OpenRouter chat client for the LLM strategy.

Everything network-facing lives here so `game/strategy_llm.py` stays pure game
logic. One function — `chat(messages)` — POSTs an OpenAI-style chat-completion
request to OpenRouter and returns the assistant's text. Token/cost usage is
accumulated module-side so the simulate/tournament drivers can print a cost
summary at the end of a run.

This module is imported lazily (only behind the opt-in flag), so a normal run
never touches the network and never needs an API key.
"""

import json
import os

import requests

# Single place to change the model. Override per-run with $OPENROUTER_MODEL.
# Defaults to a cheap model; confirm the current cheapest on
# https://openrouter.ai/models before a big batch. For zero-cost experiments use
# a ":free" variant (e.g. "meta-llama/llama-3.3-70b-instruct:free").
DEFAULT_MODEL = "google/gemini-2.5-flash-lite"

API_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMError(RuntimeError):
    """Any failure reaching OpenRouter or reading its reply."""


# ── Usage accounting (cumulative across a run) ──────────────────────────────
_USAGE = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}


def reset_usage():
    for k in _USAGE:
        _USAGE[k] = 0 if k != "cost" else 0.0


def usage():
    return dict(_USAGE)


def model_name():
    return os.environ.get("OPENROUTER_MODEL") or DEFAULT_MODEL


def _api_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise LLMError(
            "OPENROUTER_API_KEY is not set. Export your OpenRouter key:\n"
            "    export OPENROUTER_API_KEY='sk-or-...'")
    return key


def chat(messages, *, model=None, temperature=0.2, timeout=30, force_json=True):
    """Send `messages` (OpenAI chat format) to OpenRouter; return reply text.

    Raises LLMError on transport errors, non-200 responses, or a malformed body.
    Accumulates token/cost usage in the module-level counter.
    """
    body = {
        "model": model or model_name(),
        "messages": messages,
        "temperature": temperature,
        # Ask OpenRouter to include cost in the usage block when the model
        # supports it (ignored otherwise).
        "usage": {"include": True},
    }
    if force_json:
        # Best-effort: honored by models that support structured output, a no-op
        # for those that don't (we parse leniently regardless).
        body["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "X-Title": "auto-cambio",
    }

    try:
        resp = requests.post(API_URL, headers=headers, json=body, timeout=timeout)
    except requests.RequestException as e:
        raise LLMError(f"request to OpenRouter failed: {e}") from e

    if resp.status_code != 200:
        raise LLMError(f"OpenRouter returned HTTP {resp.status_code}: {resp.text[:300]}")

    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise LLMError(f"unexpected OpenRouter response: {resp.text[:300]}") from e

    _record_usage(data.get("usage"))
    return content


def _record_usage(u):
    _USAGE["calls"] += 1
    if not isinstance(u, dict):
        return
    _USAGE["prompt_tokens"] += int(u.get("prompt_tokens") or 0)
    _USAGE["completion_tokens"] += int(u.get("completion_tokens") or 0)
    cost = u.get("cost")
    if cost is not None:
        try:
            _USAGE["cost"] += float(cost)
        except (TypeError, ValueError):
            pass


def summary_line():
    """One-line human summary of accumulated usage."""
    u = _USAGE
    cost = f"~${u['cost']:.4f}" if u["cost"] else "cost n/a"
    return (f"LLM calls: {u['calls']}  ·  tokens: {u['prompt_tokens']:,} in / "
            f"{u['completion_tokens']:,} out  ·  {cost}  ·  model: {model_name()}")
