"""Tests for the versioned system prompts and the named-opponent registry.

Pure text + registry lookups + construction — no network, no API key, nothing
that would make a call. Guards the property the A/B depends on: `gemini` and
`gemini-opus` differ **only** in the prompt version.
"""

import pytest

from game import llm_prompts
from game.llm_opponents import NAMED_LLM_OPPONENTS, llm_model, llm_prompt
from game.strategy_llm import LLMStrategy, get_llm_strategy
from game.tournament import entrants


def test_v1_is_rules_only():
    v1 = llm_prompts.RULES_V1
    assert "Lowest hand total wins" in v1
    assert "EMPTY SLOTS ARE GOOD" not in v1
    assert "MINE" not in v1


def test_opus_keeps_the_mechanical_contract():
    # The opus prompt reshapes strategy but must preserve the rules facts and
    # the JSON reply contract the parser depends on.
    op = llm_prompts.RULES_OPUS
    for fact in ("A=1", "J=11, Q=12", "-1",              # card values, red King
                 "7 or 8", "9 or 10", "J or Q",          # powers table
                 "+5 penalty",                            # Cambio scoring
                 "ONLY a single JSON object",
                 'FIRST key is "reason"'):
        assert fact in op, fact


def test_opus_adds_a_log_derived_strategy_layer():
    op = llm_prompts.RULES_OPUS
    assert "EMPTY SLOTS ARE GOOD" in op          # top observed failure mode
    assert "MINE" in op and "THEIRS" in op       # the named quantities
    assert "never trade ? for ?" in op           # blind-switch discipline


def test_get_prompt_versions_and_errors():
    assert llm_prompts.get_prompt() is llm_prompts.RULES_V1
    assert llm_prompts.get_prompt("opus") is llm_prompts.RULES_OPUS
    with pytest.raises(ValueError, match="unknown prompt version"):
        llm_prompts.get_prompt("nope")


def test_gemini_variants_share_a_model_and_differ_only_by_prompt(monkeypatch):
    assert llm_model("gemini") == llm_model("gemini-opus")
    assert llm_prompt("gemini") == "v1"
    assert llm_prompt("gemini-opus") == "opus"
    # An env override must move both entrants together, or the A/B compares models.
    monkeypatch.setenv("CAMBIO_GEMINI_MODEL", "vendor/other")
    assert llm_model("gemini") == llm_model("gemini-opus") == "vendor/other"


def test_other_named_opponents_default_to_v1():
    for key in ("kimi", "haiku", "gemini"):
        assert llm_prompt(key) == llm_prompts.DEFAULT_VERSION


def test_strategy_resolves_prompt_at_construction():
    assert LLMStrategy().system_prompt is llm_prompts.RULES_V1
    strat = get_llm_strategy(prompt_version="opus")
    assert strat.system_prompt is llm_prompts.RULES_OPUS
    with pytest.raises(ValueError, match="unknown prompt version"):
        LLMStrategy(prompt_version="v9")


def test_conversation_system_message_uses_the_version(monkeypatch):
    monkeypatch.setenv("CAMBIO_LLM_LOG", "/dev/null")
    strat = LLMStrategy(prompt_version="opus")
    state = {"log": []}
    conv = strat._conv(state, "player")
    system = conv["messages"][0]
    assert system["role"] == "system"
    assert system["content"].startswith(llm_prompts.RULES_OPUS)
    assert "'player' player" in system["content"]


def test_entrants_build_gemini_llm_variants():
    # Construction only — LLMStrategy makes no call until asked for a move.
    field = entrants(include_random=False, keys=[],
                     llm_keys=["gemini", "gemini-opus"])
    assert [e.key for e in field] == ["gemini", "gemini-opus"]
    assert [e.strat.prompt_version for e in field] == ["v1", "opus"]
    assert field[0].strat.model == field[1].strat.model
    assert "Opus" in NAMED_LLM_OPPONENTS["gemini-opus"]["name"]  # report tells them apart
