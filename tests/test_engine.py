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
