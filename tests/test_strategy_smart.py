"""Smoke tests for the `game/strategy_smart.py` module-level facade.

The facade just rebinds methods from the greedy `SmartStrategy` profile so the
engine and web app can import a module instead of an object. These tests cover
the import-time bindings — without them the module never loads in CI.
"""

import random

from game import strategy_smart
from game.rules import apply_move, create_initial_state


def test_smart_ai_description_is_a_non_empty_list():
    assert isinstance(strategy_smart.SMART_AI_DESCRIPTION, list)
    assert strategy_smart.SMART_AI_DESCRIPTION   # at least one rule line


def test_facade_methods_drive_a_legal_computer_turn():
    """One pass through draw + action covers `choose_move` twice and exercises
    every bound facade name without touching the engine layer."""
    random.seed(0)
    state = apply_move(create_initial_state("computer"), {"action": "start"})
    # Step 1: choose_move with drawn_card=None → draw_deck or call_cambio.
    move1 = strategy_smart.choose_move(state, state["computer_known"])
    assert move1["action"] in {"draw_deck", "draw_discard", "call_cambio"}
    state = apply_move(state, move1)
    if move1["action"] == "call_cambio":
        return  # nothing further to drive on the strategy in this branch
    # Step 2: choose_move with a drawn_card → swap or discard_drawn.
    move2 = strategy_smart.choose_move(state, state["computer_known"])
    assert move2["action"] in {"swap", "discard_drawn"}


def test_should_snap_returns_bool():
    state = create_initial_state("computer")
    # Force a snappable scenario: discard top matches a known computer card.
    state["computer_hand"][0] = {"rank": "5", "suit": "♠"}
    state["computer_known"][0] = True
    state["discard_pile"] = [{"rank": "5", "suit": "♥"}]
    result = strategy_smart.should_snap(state, 0, "computer")
    assert isinstance(result, bool)


def test_apply_computer_special_returns_a_state():
    random.seed(0)
    state = apply_move(create_initial_state("computer"), {"action": "start"})
    out = strategy_smart.apply_computer_special(state, "peek_own")
    assert isinstance(out, dict)
    assert "computer_hand" in out
