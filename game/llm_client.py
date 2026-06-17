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
import time

import requests

# Load a repo-root .env (if present) so OPENROUTER_API_KEY / OPENROUTER_MODEL can
# live in a gitignored file instead of the shell. Best-effort: python-dotenv is
# only needed for the opt-in LLM path, so a normal run without it still works.
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(usecwd=True))
except ImportError:
    pass

# Single place to change the model. Override per-run with $OPENROUTER_MODEL.
# Defaults to a cheap model; confirm the current cheapest on
# https://openrouter.ai/models before a big batch. For zero-cost experiments use
# a ":free" variant (e.g. "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free").
DEFAULT_MODEL = "google/gemini-3.1-flash-lite"

API_URL = "https://openrouter.ai/api/v1/chat/completions"

# HTTP statuses worth retrying with backoff (rate limit + transient server errors).
_RETRY_STATUS = {429, 500, 502, 503, 504}
_BACKOFFS = (1, 2, 4)   # seconds before retry attempts 1, 2, 3


def _is_structured_output_rejection(text):
    """True if a 400 body says the model/provider doesn't accept response_format.
    Some providers (e.g. Novita's Kimi) hard-reject the JSON-mode flag with a 400
    instead of ignoring it; we detect that so the caller can retry without it."""
    t = (text or "").lower()
    return ("structured" in t or "response_format" in t or "json_object" in t
            or "json mode" in t)


class LLMError(RuntimeError):
    """Any failure reaching OpenRouter or reading its reply."""


# ── Usage accounting (cumulative across a run) ──────────────────────────────
_USAGE = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
# Same counters split by resolved model id, so a multi-model run can report
# per-model spend (e.g. Kimi vs Haiku in a tournament).
_USAGE_BY_MODEL = {}


def _blank_usage():
    return {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}


def reset_usage():
    for k in _USAGE:
        _USAGE[k] = 0 if k != "cost" else 0.0
    _USAGE_BY_MODEL.clear()


def usage():
    return dict(_USAGE)


def usage_by_model():
    return {m: dict(u) for m, u in _USAGE_BY_MODEL.items()}


def model_name():
    return os.environ.get("OPENROUTER_MODEL") or DEFAULT_MODEL


def _api_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise LLMError(
            "OPENROUTER_API_KEY is not set. Export your OpenRouter key:\n"
            "    export OPENROUTER_API_KEY='sk-or-...'")
    return key


def chat(messages, *, model=None, temperature=0.2, timeout=30, force_json=True,
         max_tokens=512):
    """Send `messages` (OpenAI chat format) to OpenRouter; return reply text.

    Raises LLMError on transport errors, non-200 responses, or a malformed body.
    Accumulates token/cost usage in the module-level counter.

    `max_tokens` is capped low on purpose: our replies are tiny JSON moves, and
    OpenRouter reserves (and credit-checks) the *requested* max — not the actual
    output — so a model's huge default (32k–64k) triggers premature HTTP 402s
    when little credit remains. A small cap lets a run use nearly its full budget
    without changing real cost.
    """
    body = {
        "model": model or model_name(),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        # Ask OpenRouter to include cost in the usage block when the model
        # supports it (ignored otherwise).
        "usage": {"include": True},
    }
    if force_json:
        # Best-effort: honored by models that support structured output. Most
        # providers ignore it when unsupported, but some hard-reject it with a
        # 400 — handled below by retrying once without it (we parse leniently
        # regardless).
        body["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "X-Title": "auto-cambio",
    }

    # Retry transport errors and 429/5xx with simple exponential backoff. A 429
    # may carry a Retry-After hint; honor it when present. Other 4xx (400 bad
    # model, 401 bad key, 402 no credit) are not retried — they won't fix
    # themselves and should surface immediately.
    last_err = "unknown error"
    for attempt in range(len(_BACKOFFS) + 1):
        try:
            resp = requests.post(API_URL, headers=headers, json=body, timeout=timeout)
        except requests.RequestException as e:
            last_err = f"request to OpenRouter failed: {e}"
            resp = None
        else:
            if resp.status_code == 200:
                break
            last_err = f"OpenRouter returned HTTP {resp.status_code}: {resp.text[:300]}"
            if resp.status_code not in _RETRY_STATUS:
                # A provider that rejects JSON mode with a 400: drop the flag and
                # retry immediately (once) — the reply is parsed leniently anyway.
                if (resp.status_code == 400 and "response_format" in body
                        and _is_structured_output_rejection(resp.text)):
                    body.pop("response_format")
                    continue
                raise LLMError(last_err)

        if attempt < len(_BACKOFFS):
            delay = _BACKOFFS[attempt]
            if resp is not None:
                try:
                    delay = max(delay, float(resp.headers.get("Retry-After", 0)))
                except (TypeError, ValueError):
                    pass
            time.sleep(delay)
    else:
        raise LLMError(f"{last_err} (after {len(_BACKOFFS)} retries)")

    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise LLMError(f"unexpected OpenRouter response: {resp.text[:300]}") from e

    _record_usage(data.get("usage"), body["model"])
    return content


def _bump(acc, u):
    acc["calls"] += 1
    if not isinstance(u, dict):
        return
    acc["prompt_tokens"] += int(u.get("prompt_tokens") or 0)
    acc["completion_tokens"] += int(u.get("completion_tokens") or 0)
    cost = u.get("cost")
    if cost is not None:
        try:
            acc["cost"] += float(cost)
        except (TypeError, ValueError):
            pass


def _record_usage(u, model=None):
    _bump(_USAGE, u)
    if model is not None:
        _bump(_USAGE_BY_MODEL.setdefault(model, _blank_usage()), u)


def summary_line():
    """One-line human summary of accumulated usage across all models."""
    u = _USAGE
    cost = f"~${u['cost']:.4f}" if u["cost"] else "cost n/a"
    return (f"LLM calls: {u['calls']}  ·  tokens: {u['prompt_tokens']:,} in / "
            f"{u['completion_tokens']:,} out  ·  {cost}")


def summary_by_model():
    """One '<model> · …' line per model used (empty if none)."""
    lines = []
    for m, u in _USAGE_BY_MODEL.items():
        cost = f"~${u['cost']:.4f}" if u["cost"] else "cost n/a"
        lines.append(f"{m}  ·  calls: {u['calls']}  ·  tokens: "
                     f"{u['prompt_tokens']:,} in / {u['completion_tokens']:,} out  ·  {cost}")
    return lines
