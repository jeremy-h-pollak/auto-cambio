"""
Computer strategy: random decisions.
Interface: choose_move(state, known_indices) -> move dict

`known_indices` is a list of bools (True = computer has seen that position).
Keeping this interface stable means we can swap in a smarter strategy later
without touching engine or rules.
"""

import random
from .rules import card_value


def choose_move(state, known_indices):
    """Return a move dict. Called twice per computer turn:
    1. When drawn_card is None  → must return draw_deck, draw_discard, or call_cambio
    2. When drawn_card is set   → must return swap or discard_drawn
    """
    drawn = state["drawn_card"]

    if drawn is None:
        # Don't call cambio if it's already been called
        if state["cambio_called_by"] is None and random.random() < 0.08:
            return {"action": "call_cambio"}

        # Prefer drawing from discard if top card is low value
        discard_pile = state["discard_pile"]
        if discard_pile:
            top = discard_pile[-1]
            if card_value(top) <= 3 and random.random() < 0.75:
                return {"action": "draw_discard"}

        return {"action": "draw_deck"}

    # Has a drawn card: randomly swap or discard
    drawn_val = card_value(drawn)

    # Discard if drawn card is high value
    if drawn_val >= 10 and random.random() < 0.7:
        return {"action": "discard_drawn"}

    if random.random() < 0.4:
        return {"action": "discard_drawn"}

    # Swap with a random position
    hand_index = random.randint(0, 3)
    return {"action": "swap", "hand_index": hand_index}
