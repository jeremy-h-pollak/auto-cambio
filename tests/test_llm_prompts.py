"""Tests for the versioned system prompts and the named-opponent registry.

Pure text + registry lookups — no network, no API key, nothing constructed that
would make a call. Guards the property the A/B depends on: `gemini` and
`gemini-v2` differ **only** in the prompt version.
"""

import pytest

from game import llm_prompts
from game.llm_opponents import NAMED_LLM_OPPONENTS, llm_model, llm_prompt
from game.tournament import entrants


def test_v1_is_rules_only():
    v1 = llm_prompts.RULES_V1
    assert "Lowest hand total wins" in v1
    assert llm_prompts.PLAYBOOK_BOT.name not in v1
    assert "Strategy guidance" not in v1


def test_v2_extends_v1_with_the_top_bot_playbook():
    v1, v2 = llm_prompts.RULES_V1, llm_prompts.RULES_V2
    assert v2.startswith(v1)                       # v2 is strictly additive
    bot = llm_prompts.PLAYBOOK_BOT
    assert bot.name in v2
    for rule in bot.rules:                         # generated, not hand-copied
        assert rule in v2


def test_playbook_bot_is_the_cartographer():
    # The bot v2 describes should be the ladder's #1 (reports 6994 / 6414).
    assert llm_prompts.PLAYBOOK_BOT.key == "cartographer"


def test_get_prompt_versions_and_errors():
    assert llm_prompts.get_prompt() is llm_prompts.RULES_V1
    assert llm_prompts.get_prompt("v2") is llm_prompts.RULES_V2
    with pytest.raises(ValueError, match="unknown prompt version"):
        llm_prompts.get_prompt("nope")


def test_gemini_variants_share_a_model_and_differ_only_by_prompt(monkeypatch):
    assert llm_model("gemini") == llm_model("gemini-v2")
    assert llm_prompt("gemini") == "v1"
    assert llm_prompt("gemini-v2") == "v2"
    # An env override must move both entrants together, or the A/B compares models.
    monkeypatch.setenv("CAMBIO_GEMINI_MODEL", "vendor/other")
    assert llm_model("gemini") == llm_model("gemini-v2") == "vendor/other"


def test_named_opponents_default_to_v1():
    for key in NAMED_LLM_OPPONENTS:
        if not key.endswith("-v2"):
            assert llm_prompt(key) == llm_prompts.DEFAULT_VERSION


def test_entrants_build_named_llm_variants():
    # Construction only — LLMStrategy makes no call until asked for a move.
    field = entrants(include_random=False, keys=[],
                     llm_keys=["gemini", "gemini-v2"])
    assert [e.key for e in field] == ["gemini", "gemini-v2"]
    assert [e.strat.prompt_version for e in field] == ["v1", "v2"]
    assert field[0].strat.model == field[1].strat.model
    assert "V2" in field[1].name          # the report must tell them apart
