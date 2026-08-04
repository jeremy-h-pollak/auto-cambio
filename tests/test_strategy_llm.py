"""Tests for the LLM strategy (game/strategy_llm.py) with a mocked client.

The OpenRouter client is monkeypatched so no network is touched: each test
supplies a fake `llm_client.chat` that returns canned JSON. A "smart" fake that
returns a legal move for any prompt lets us drive whole games through the real
choose_move / special / snapshot machinery.
"""

import re
import pytest

from game import llm_client, strategy_llm
from game.strategy_llm import get_llm_strategy, _extract_json, _card_str
from game.rules import create_initial_state
import game.strategy as random_strategy
from game.simulator import run_simulation


# ── A competent fake LLM ─────────────────────────────────────────────────────
def smart_reply(content):
    """Return a legal JSON move for whatever decision the prompt asks for."""
    decision = content.split("\n\n")[-1]
    low = decision.lower()

    def ints():
        return [int(g.split(",")[0]) for g in re.findall(r"\[([0-9, ]+)\]", decision)]

    if "draw phase" in low:
        return '{"action": "draw_deck"}'
    if "you drew" in low:
        return '{"action": "discard_drawn"}'          # fire any power
    if "peek at one of your own" in low or "peek at one opponent" in low:
        return '{"index": %d}' % ints()[0]
    if "blind switch" in low or "to look at" in low:
        nums = ints()
        return '{"own": %d, "opp": %d}' % (nums[0], nums[1])
    if "switch them?" in low:
        return '{"switch": true}'
    if "may snap" in low:
        return '{"snap": true}'
    return '{"action": "draw_deck"}'


@pytest.fixture(autouse=True)
def _tmp_llm_log(tmp_path, monkeypatch):
    """Keep the prompt transcript out of the repo: each test writes its JSONL to
    an isolated tmp file instead of the default llm_logs/prompts.jsonl."""
    monkeypatch.setenv("CAMBIO_LLM_LOG", str(tmp_path / "prompts.jsonl"))


def patch(monkeypatch, fn):
    """Point llm_client.chat at `fn`, which receives the last message content."""
    monkeypatch.setattr(llm_client, "chat",
                        lambda messages, **kw: fn(messages[-1]["content"]))


def _computer_state():
    state = create_initial_state(starting_turn="computer")
    state["current_turn"] = "computer"
    return state


# ── Module helpers ───────────────────────────────────────────────────────────
def test_extract_json_helper():
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _extract_json("nope") is None


def test_card_str_helper():
    assert _card_str(None) == "empty"
    s = _card_str({"rank": "K", "suit": "♥"})
    assert "K♥" in s and "-1" in s            # red King renders its value


def test_factory_returns_strategy():
    strat = get_llm_strategy(model="x/y", llm_snaps=True)
    assert strat.model == "x/y" and strat.llm_snaps is True
    assert strat.key == "llm"
    assert strat.prompt_version == "v1"           # rules-only prompt by default


# ── System-prompt versions ───────────────────────────────────────────────────
def test_system_message_uses_selected_prompt_version(monkeypatch):
    from game.llm_prompts import PLAYBOOK_BOT

    def sys_msg(version):
        _capture_prompt(monkeypatch, {})
        state = _computer_state()
        get_llm_strategy(prompt_version=version).choose_move(state)
        return state["_llm"]["computer"]["messages"][0]["content"]

    v1, v2, v3 = sys_msg("v1"), sys_msg("v2"), sys_msg("v3")
    assert all("Lowest hand total wins" in v for v in (v1, v2, v3))
    assert PLAYBOOK_BOT.name not in v1            # v1 hands over no tactics
    assert PLAYBOOK_BOT.name in v2
    assert PLAYBOOK_BOT.rules[0] in v2            # generated from the bot's own rules
    assert "DRAW PHASE" in v3                     # v3 is the operational form


def test_unknown_prompt_version_rejected_at_construction():
    with pytest.raises(ValueError, match="unknown prompt version"):
        get_llm_strategy(prompt_version="v9")


@pytest.mark.parametrize("version", ["v2", "v3"])
def test_playbook_versions_play_full_games(monkeypatch, version):
    patch(monkeypatch, smart_reply)
    strat = get_llm_strategy(prompt_version=version)
    recs, _ = run_simulation(3, smart=strat, opponent=random_strategy,
                             seed=5, max_turns=400)
    assert len(recs) == 3
    assert strat.call_count > 0 and strat.fallback_count == 0


# ── Full games through the real machinery ────────────────────────────────────
def test_full_games_complete_no_fallback(monkeypatch):
    patch(monkeypatch, smart_reply)
    strat = get_llm_strategy()
    recs, _ = run_simulation(4, smart=strat, opponent=random_strategy,
                             seed=3, max_turns=400)
    assert len(recs) == 4
    assert all(r.ending in ("cambio", "empty", "capped") for r in recs)
    assert strat.call_count > 0
    assert strat.fallback_count == 0          # smart_reply is always legal


def test_forced_fallback_completes_games(monkeypatch):
    def boom(_content):
        raise llm_client.LLMError("simulated outage")
    patch(monkeypatch, boom)
    strat = get_llm_strategy()
    recs, _ = run_simulation(2, smart=strat, opponent=random_strategy,
                             seed=1, max_turns=400)
    assert len(recs) == 2
    assert all(r.ending in ("cambio", "empty", "capped") for r in recs)
    assert strat.fallback_count > 0           # every decision fell back to greedy


# ── Draw / action phase + retry + fallback ───────────────────────────────────
def test_retry_on_invalid_then_valid(monkeypatch):
    replies = iter(["not json at all", '{"action": "draw_deck"}'])
    monkeypatch.setattr(llm_client, "chat", lambda m, **k: next(replies))
    strat = get_llm_strategy()
    move = strat.choose_move(_computer_state())
    assert move == {"action": "draw_deck"}
    assert strat.fallback_count == 0


def test_two_bad_replies_fall_back(monkeypatch):
    replies = iter(["bad", "still bad"])
    monkeypatch.setattr(llm_client, "chat", lambda m, **k: next(replies))
    strat = get_llm_strategy()
    move = strat.choose_move(_computer_state())
    assert move["action"] in ("draw_deck", "draw_discard", "call_cambio")
    assert strat.fallback_count == 1


def test_action_phase_swap_validated(monkeypatch):
    patch(monkeypatch, lambda c: '{"action": "swap", "hand_index": 2}')
    strat = get_llm_strategy()
    state = _computer_state()
    state["drawn_card"] = {"rank": "3", "suit": "♣"}
    move = strat.choose_move(state)
    assert move == {"action": "swap", "hand_index": 2}


def test_action_phase_illegal_swap_falls_back(monkeypatch):
    # hand_index 9 is not a held position → invalid twice → greedy fallback
    patch(monkeypatch, lambda c: '{"action": "swap", "hand_index": 9}')
    strat = get_llm_strategy()
    state = _computer_state()
    state["drawn_card"] = {"rank": "3", "suit": "♣"}
    move = strat.choose_move(state)
    assert move["action"] in ("swap", "discard_drawn")
    assert strat.fallback_count == 1


# ── Snapping ─────────────────────────────────────────────────────────────────
def _snap_state():
    state = _computer_state()
    state["discard_pile"] = [{"rank": "5", "suit": "♣"}]
    state["computer_hand"][0] = {"rank": "5", "suit": "♦"}
    state["computer_known"][0] = True
    return state


def test_snap_heuristic_default(monkeypatch):
    # llm_snaps off → never calls the model; greedy heuristic decides.
    patch(monkeypatch, lambda c: (_ for _ in ()).throw(AssertionError("should not call")))
    strat = get_llm_strategy()
    assert strat.should_snap(_snap_state(), 0, "computer") is True


def test_snap_llm_true_and_false(monkeypatch):
    strat = get_llm_strategy(llm_snaps=True)
    patch(monkeypatch, lambda c: '{"snap": true}')
    assert strat.should_snap(_snap_state(), 0, "computer") is True
    patch(monkeypatch, lambda c: '{"snap": false}')
    assert strat.should_snap(_snap_state(), 0, "computer") is False


def test_snap_llm_failure_falls_back(monkeypatch):
    strat = get_llm_strategy(llm_snaps=True)
    patch(monkeypatch, lambda c: "garbage")
    # invalid twice → fall back to greedy heuristic (snaps a positive known match)
    assert strat.should_snap(_snap_state(), 0, "computer") is True
    assert strat.fallback_count == 1


# ── Special abilities ────────────────────────────────────────────────────────
def test_peek_own_sets_known_and_acted(monkeypatch):
    patch(monkeypatch, lambda c: '{"index": 0}')      # 0 is unknown at start
    strat = get_llm_strategy()
    state = _computer_state()
    strat.apply_computer_special(state, "peek_own")
    assert state["computer_known"][0] is True
    assert state["computer_acted"] == [0]


def test_peek_own_no_unknown_is_noop(monkeypatch):
    patch(monkeypatch, lambda c: (_ for _ in ()).throw(AssertionError("should not call")))
    strat = get_llm_strategy()
    state = _computer_state()
    state["computer_known"] = [True, True, True, True]
    strat.apply_computer_special(state, "peek_own")    # early return, no model call


def test_peek_opponent_records_memory_and_reveal(monkeypatch):
    patch(monkeypatch, lambda c: '{"index": 0}')
    strat = get_llm_strategy()
    state = _computer_state()
    strat.apply_computer_special(state, "peek_opponent")
    assert 0 in strat._memory(state, "computer")
    assert 0 in state["player_reveal"]


def test_blind_switch_executes_and_remembers(monkeypatch):
    patch(monkeypatch, lambda c: '{"own": 0, "opp": 1}')
    strat = get_llm_strategy()
    state = _computer_state()
    state["computer_known"][0] = True                  # known card → remembered after give
    my0 = dict(state["computer_hand"][0])
    opp1 = dict(state["player_hand"][1])
    strat.apply_computer_special(state, "blind_switch")
    assert state["computer_hand"][0] == opp1           # took opponent's card
    assert state["player_hand"][1] == my0              # gave our card away
    assert state["computer_acted"] == [0] and state["player_touched"] == [1]
    assert strat._memory(state, "computer")[1] == {"rank": my0["rank"], "suit": my0["suit"]}


def test_blind_switch_decline(monkeypatch):
    patch(monkeypatch, lambda c: '{"switch": false}')
    strat = get_llm_strategy()
    state = _computer_state()
    before = [dict(c) if c else None for c in state["computer_hand"]]
    strat.apply_computer_special(state, "blind_switch")
    assert state["computer_hand"] == before            # nothing swapped
    assert any("declined" in line for line in state["log"])


def test_looking_switch_swaps_on_decision(monkeypatch):
    def reply(content):
        return '{"switch": true}' if "switch them?" in content.lower() \
            else '{"own": 0, "opp": 0}'
    patch(monkeypatch, reply)
    strat = get_llm_strategy()
    state = _computer_state()
    opp0 = dict(state["player_hand"][0])
    strat.apply_computer_special(state, "looking_switch")
    assert state["computer_hand"][0] == opp0
    assert state["computer_known"][0] is True


def test_looking_switch_decline_keeps_cards(monkeypatch):
    def reply(content):
        return '{"switch": false}' if "switch them?" in content.lower() \
            else '{"own": 0, "opp": 0}'
    patch(monkeypatch, reply)
    strat = get_llm_strategy()
    state = _computer_state()
    my0 = dict(state["computer_hand"][0])
    strat.apply_computer_special(state, "looking_switch")
    assert state["computer_hand"][0] == my0            # unchanged
    assert state["computer_known"][0] is True          # but we now know it
    assert 0 in strat._memory(state, "computer")       # and we saw the opp card


def test_special_fallback_when_model_fails(monkeypatch):
    patch(monkeypatch, lambda c: "garbage")
    strat = get_llm_strategy()
    state = _computer_state()
    # invalid replies → strategy falls back to the greedy special handler
    strat.apply_computer_special(state, "peek_opponent")
    assert strat.fallback_count >= 1


# ── Fair-information snapshot ─────────────────────────────────────────────────
def _capture_prompt(monkeypatch, store):
    def chat(messages, **kw):
        store["prompt"] = messages[-1]["content"]
        return '{"action": "draw_deck"}'
    monkeypatch.setattr(llm_client, "chat", chat)


def test_snapshot_masks_hidden_cards(monkeypatch):
    store = {}
    _capture_prompt(monkeypatch, store)
    strat = get_llm_strategy()
    strat.choose_move(_computer_state())
    your_line = [l for l in store["prompt"].splitlines() if l.startswith("Your hand")][0]
    opp_line = [l for l in store["prompt"].splitlines() if l.startswith("Opponent hand")][0]
    assert your_line.count("?") == 2          # two unknown own slots at start
    assert opp_line.count("[") == 4 and "8♣" not in opp_line   # opponent fully masked


def test_snapshot_cambio_status_variants(monkeypatch):
    store = {}
    _capture_prompt(monkeypatch, store)
    strat = get_llm_strategy()

    state = _computer_state()
    state["cambio_called_by"] = "player"      # opponent ended the round
    strat.choose_move(state)
    assert "LAST turn" in store["prompt"]

    strat2 = get_llm_strategy()
    state2 = _computer_state()
    state2["cambio_called_by"] = "computer"   # we called it
    strat2.choose_move(state2)
    assert "YOU called" in store["prompt"]


def test_who_moves_first_system_message(monkeypatch):
    _capture_prompt(monkeypatch, {})
    strat = get_llm_strategy()
    state = _computer_state()                  # fresh: empty log
    strat.choose_move(state)
    sys_msg = state["_llm"]["computer"]["messages"][0]["content"]
    assert "You move first" in sys_msg

    strat2 = get_llm_strategy()
    state2 = _computer_state()
    state2["log"] = ["computer discarded 9♣."]   # opponent already acted
    strat2.choose_move(state2)
    sys_msg2 = state2["_llm"]["computer"]["messages"][0]["content"]
    assert "opponent moved first" in sys_msg2


# ── Prompt/response trace ─────────────────────────────────────────────────────
def test_trace_records_state_prompt_and_move(monkeypatch):
    patch(monkeypatch, lambda c: '{"action": "draw_deck"}')
    strat = get_llm_strategy()
    state = _computer_state()
    strat.choose_move(state)
    trace = state["llm_trace"]
    assert len(trace) == 1
    e = trace[0]
    assert e["kind"] == "draw"
    assert e["state"] and e["state"].startswith("Your hand")   # GSi captured
    assert "draw phase" in e["prompt"].lower()                  # Pi captured
    assert e["parsed"] == {"action": "draw_deck"}              # Mi parsed
    assert e["error"] is None
    assert e["prompt_version"] == "v1"      # which system prompt drove the move


def test_trace_retry_then_success_has_two_entries(monkeypatch):
    replies = iter(["not json at all", '{"action": "draw_deck"}'])
    monkeypatch.setattr(llm_client, "chat", lambda m, **k: next(replies))
    strat = get_llm_strategy()
    state = _computer_state()
    strat.choose_move(state)
    trace = state["llm_trace"]
    assert len(trace) == 2
    assert trace[0]["error"] is not None and trace[0]["state"]   # first: GSi + error
    assert trace[1]["state"] is None                            # retry: no GSi
    assert trace[1]["parsed"] == {"action": "draw_deck"}


def test_trace_written_to_jsonl(monkeypatch):
    import json
    patch(monkeypatch, lambda c: '{"action": "draw_deck"}')
    strat = get_llm_strategy(prompt_version="v2")
    strat.choose_move(_computer_state())
    with open(strat.log_path, encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]
    assert len(lines) == 1
    assert lines[0]["session"] == strat.session_id
    assert lines[0]["kind"] == "draw" and "ts" in lines[0]
    assert lines[0]["prompt_version"] == "v2"   # A/B runs stay attributable


def test_trace_log_write_failure_does_not_break_game(monkeypatch):
    # A failed JSONL write must never interrupt a move: the in-state trace still
    # populates and the strategy keeps going (with a one-time stderr warning).
    patch(monkeypatch, lambda c: '{"action": "draw_deck"}')
    strat = get_llm_strategy()
    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr("game.strategy_llm.open", boom, raising=False)
    state = _computer_state()
    move = strat.choose_move(state)
    assert move == {"action": "draw_deck"}
    assert len(state["llm_trace"]) == 1          # in-memory trace unaffected
    assert strat._log_warned is True


def test_trace_records_api_error(monkeypatch):
    def boom(_content):
        raise llm_client.LLMError("simulated outage")
    patch(monkeypatch, boom)
    strat = get_llm_strategy()
    state = _computer_state()
    strat.choose_move(state)
    e = state["llm_trace"][0]
    assert e["response"] is None
    assert "API error" in e["error"]


# ── Memory pruning ───────────────────────────────────────────────────────────
def test_memory_prune_drops_changed_slot():
    strat = get_llm_strategy()
    state = _computer_state()
    strat._remember(state, "computer", 0, state["player_hand"][0])
    assert 0 in strat._memory(state, "computer")
    state["player_hand"][0] = {"rank": "2", "suit": "♠"}   # slot changed publicly
    strat._prune_memory(state, "computer")
    assert 0 not in strat._memory(state, "computer")
