"""
Computer strategy: random decisions.

Public interface (stable — swap for a smarter strategy without touching engine):
  choose_move(state, known_indices) -> move dict
  should_snap(state, hand_index)    -> bool
  choose_computer_special(state, stype) -> list of state-mutating ops (dicts)
"""

import random
from .rules import card_value, snap_eligible_indices


def choose_move(state, known_indices):
    """Called twice per computer turn:
    1. drawn_card is None  → return draw_deck | draw_discard | call_cambio
    2. drawn_card is set   → return swap | discard_drawn
    """
    drawn = state["drawn_card"]

    if drawn is None:
        if state["cambio_called_by"] is None and random.random() < 0.08:
            return {"action": "call_cambio"}
        discard_pile = state["discard_pile"]
        if discard_pile and card_value(discard_pile[-1]) <= 3 and random.random() < 0.75:
            return {"action": "draw_discard"}
        return {"action": "draw_deck"}

    drawn_val = card_value(drawn)
    if drawn_val >= 10 and random.random() < 0.7:
        return {"action": "discard_drawn"}
    if random.random() < 0.4:
        return {"action": "discard_drawn"}
    hand_size = len(state["computer_hand"])
    return {"action": "swap", "hand_index": random.randint(0, hand_size - 1)}


def should_snap(state, hand_index):
    """Return True if computer should snap the card at hand_index."""
    return random.random() < 0.7


def apply_computer_special(state, stype):
    """Apply the computer's special ability in-place. Returns updated state.

    Called by the engine after the computer discards a special card.
    Mutates state directly (engine context, not a pure rules function).
    """
    computer_hand = state["computer_hand"]
    player_hand   = state["player_hand"]
    computer_known = state["computer_known"]
    player_known   = state["player_known"]
    player_opp_known = state["player_opponent_known"]

    if stype == "peek_own":
        unknown = [i for i, k in enumerate(computer_known) if not k]
        if unknown:
            idx = random.choice(unknown)
            computer_known[idx] = True
            c = computer_hand[idx]
            msg = f"Computer used 7/8: peeked at its own position {idx+1} ({c['rank']}{c['suit']})."
        else:
            msg = "Computer used 7/8: already knows all its cards."
        state["message"] = msg
        state["log"].append(msg)

    elif stype == "peek_opponent":
        if player_hand:
            idx = random.randint(0, len(player_hand) - 1)
            c = player_hand[idx]
            msg = f"Computer used 9/10: peeked at your position {idx+1}!"
            state["message"] = msg
            state["log"].append(msg)

    elif stype == "blind_switch":
        if computer_hand and player_hand:
            my_idx   = random.randint(0, len(computer_hand) - 1)
            opp_idx  = random.randint(0, len(player_hand) - 1)
            computer_hand[my_idx], player_hand[opp_idx] = \
                player_hand[opp_idx], computer_hand[my_idx]
            computer_known[my_idx]     = False
            player_known[opp_idx]      = False
            if my_idx < len(player_opp_known):
                player_opp_known[my_idx] = False
            msg = (f"Computer used J/Q: blind-switched its position {my_idx+1} "
                   f"with your position {opp_idx+1}!")
            state["message"] = msg
            state["log"].append(msg)

    elif stype == "looking_switch":
        if computer_hand and player_hand:
            my_idx  = random.randint(0, len(computer_hand) - 1)
            opp_idx = random.randint(0, len(player_hand) - 1)
            my_card  = computer_hand[my_idx]
            opp_card = player_hand[opp_idx]
            # Switch if opponent's card is better (lower value) for computer
            if card_value(opp_card) < card_value(my_card):
                computer_hand[my_idx]  = opp_card
                player_hand[opp_idx]   = my_card
                computer_known[my_idx] = True
                player_known[opp_idx]  = False
                if my_idx < len(player_opp_known):
                    player_opp_known[my_idx] = False
                msg = (f"Computer used K: looked and switched its position {my_idx+1} "
                       f"with your position {opp_idx+1}!")
            else:
                computer_known[my_idx] = True
                msg = "Computer used K: looked at cards but chose not to switch."
            state["message"] = msg
            state["log"].append(msg)

    return state
