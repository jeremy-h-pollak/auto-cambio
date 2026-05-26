"""Integration smoke test for the GameEngine turn-flow layer (game/engine.py)."""

import random

from game.engine import GameEngine
from game.rules import (
    get_scores,
    PHASE_GAME_OVER,
    PHASE_PEEK,
    PHASE_PLAYER_ACTION,
    PHASE_PLAYER_DRAW,
    PHASE_PLAYER_SPECIAL,
)


def _legal_player_action(phase):
    """Pick a simple legal player action for the current phase, or None to stop."""
    if phase == PHASE_PEEK:
        return "start"
    if phase == PHASE_PLAYER_DRAW:
        return "draw_deck"
    if phase == PHASE_PLAYER_ACTION:
        return "discard_drawn"   # always discard (may trigger a player special)
    if phase == PHASE_PLAYER_SPECIAL:
        return "skip_special"
    return None


def test_full_game_plays_to_completion():
    """A whole game, driven by a trivial legal-move player, reaches game_over and
    scores cleanly. Exercises rules + strategy + engine end to end."""
    random.seed(0)
    engine = GameEngine()

    for _ in range(5000):  # safety cap against an unexpected infinite loop
        if engine.state["phase"] == PHASE_GAME_OVER:
            break
        action = _legal_player_action(engine.state["phase"])
        assert action is not None, f"no legal action for phase {engine.state['phase']}"
        engine.player_move(action)
    else:
        raise AssertionError("game did not reach game_over within the iteration cap")

    assert engine.state["phase"] == PHASE_GAME_OVER
    player_score, computer_score = get_scores(engine.state)
    assert isinstance(player_score, int)
    assert isinstance(computer_score, int)


def test_reset_alternates_starting_player():
    """reset() flips who goes first relative to the freshly constructed game."""
    engine = GameEngine()
    first_starter = engine.state["current_turn"]
    engine.reset()
    assert engine.state["current_turn"] != first_starter


def test_player_move_forwards_target_for_opponent_snap():
    """Snapping a known computer card (target=computer) must reach apply_move.

    Regression: player_move dropped the `target` kwarg the /move route forwards,
    so clicking the opponent's matching card raised TypeError instead of snapping.
    The snap should remove the computer's card and enter the give_card special.
    """
    engine = GameEngine()
    s = engine.state
    s["phase"] = PHASE_PLAYER_DRAW
    s["current_turn"] = "player"
    s["discard_pile"] = [{"rank": "5", "suit": "♥"}]
    s["computer_hand"] = [{"rank": "5", "suit": "♠"}, None, None, None]
    s["player_opponent_known"] = [True, False, False, False]
    s["player_hand"] = [{"rank": "9", "suit": "♣"}, None, None, None]
    s["player_known"] = [True, False, False, False]

    engine.player_move("snap", hand_index=0, target="computer")  # must not raise

    assert engine.state["computer_hand"][0] is None
    assert engine.state["phase"] == PHASE_PLAYER_SPECIAL
    assert engine.state["special_action"]["type"] == "give_card"
