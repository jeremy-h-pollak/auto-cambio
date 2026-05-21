"""
Parameterized "smart" Cambio strategies.

A `StrategyProfile` captures the tunable rules (snapping, draw source, when to
gamble, when to call Cambio). `SmartStrategy` binds a profile and exposes the
same duck-typed interface the engine and simulator expect:

    choose_move(state, known_indices)     -> move dict
    should_snap(state, hand_index, seat)  -> bool
    apply_special(state, seat, stype)     -> state   (simulator / seat-general)
    apply_computer_special(state, stype)  -> state   (engine entry point)

`PROFILES` holds the named variants compared in the reports; each carries a
human-readable `rules` list that the report prints at the top.
"""

from dataclasses import dataclass, field

from .rules import card_value, hand_value, special_type


@dataclass
class StrategyProfile:
    key: str
    name: str
    rules: list                       # human-readable bullet lines for the report
    snap_mode: str = "always"         # "always" | "high_only"
    snap_min_value: int = 7           # used when snap_mode == "high_only"
    draw_discard: bool = True         # draw from discard when it beats largest known
    gamble_max: int = 6               # max drawn value to gamble onto an unknown slot
    cambio_all_known_sum: int = 8     # call Cambio when all known and sum <= this
    cambio_known_sum: int | None = None   # call with <=1 unknown when known-sum <= this
    discard_specials_for_info: bool = False  # always discard peek cards (7-10) to use them


def _largest_known(hand, known):
    """(index, value) of the highest-valued card the owner knows, or None."""
    best = None
    for i, c in enumerate(hand):
        if c is not None and i < len(known) and known[i]:
            v = card_value(c)
            if best is None or v > best[1]:
                best = (i, v)
    return best


class SmartStrategy:
    def __init__(self, profile):
        self.profile = profile

    # ── Decisions ──────────────────────────────────────────────────────────
    def _should_call_cambio(self, hand, known):
        p = self.profile
        idxs = [i for i, c in enumerate(hand) if c is not None]
        if not idxs:
            return False
        all_known = all(known[i] for i in idxs)
        if all_known and hand_value(hand) <= p.cambio_all_known_sum:
            return True
        if p.cambio_known_sum is not None:
            n_unknown = sum(1 for i in idxs if not known[i])
            known_sum = sum(card_value(hand[i]) for i in idxs if known[i])
            if n_unknown <= 1 and any(known[i] for i in idxs) and known_sum <= p.cambio_known_sum:
                return True
        return False

    def choose_move(self, state, known_indices):
        p = self.profile
        seat = state["current_turn"]
        hand = state[f"{seat}_hand"]
        known = state[f"{seat}_known"]
        drawn = state["drawn_card"]

        if drawn is None:
            if state["cambio_called_by"] is None and self._should_call_cambio(hand, known):
                return {"action": "call_cambio"}
            largest = _largest_known(hand, known)
            discard = state["discard_pile"]
            if p.draw_discard and discard and largest and card_value(discard[-1]) < largest[1]:
                return {"action": "draw_discard"}
            return {"action": "draw_deck"}

        drawn_val = card_value(drawn)
        if p.discard_specials_for_info and special_type(drawn) in ("peek_own", "peek_opponent"):
            return {"action": "discard_drawn"}

        largest = _largest_known(hand, known)
        if largest and drawn_val < largest[1]:
            return {"action": "swap", "hand_index": largest[0]}

        unknown = [i for i, c in enumerate(hand) if c is not None and not known[i]]
        if drawn_val <= p.gamble_max and unknown:
            return {"action": "swap", "hand_index": unknown[0]}

        return {"action": "discard_drawn"}

    def should_snap(self, state, hand_index, seat="computer"):
        if self.profile.snap_mode == "always":
            return True
        card = state[f"{seat}_hand"][hand_index]
        if card is None:
            return False
        return card_value(card) >= self.profile.snap_min_value

    # ── Powers (seat-general; sets UI fields for the live app on seat=computer)
    def apply_special(self, state, seat, stype):
        opp = "player" if seat == "computer" else "computer"
        me_hand, me_known = state[f"{seat}_hand"], state[f"{seat}_known"]
        opp_hand, opp_known = state[f"{opp}_hand"], state[f"{opp}_known"]
        is_comp = seat == "computer"

        def reveal_opp(idx):
            if is_comp:
                state["player_reveal"].append(idx)

        def touch(mi, oi=None):
            if is_comp:
                state["computer_acted"] = [mi]
                if oi is not None:
                    state["player_touched"] = [oi]

        def forget_opp(oi):
            opp_known[oi] = False
            if oi < len(state["player_opponent_known"]):
                state["player_opponent_known"][oi] = False

        if stype == "peek_own":
            unknown = [i for i, k in enumerate(me_known) if not k and me_hand[i] is not None]
            if unknown:
                idx = unknown[0]
                me_known[idx] = True
                touch(idx)
                state["log"].append(f"{seat} used 7/8: peeked at its own position {idx+1}.")

        elif stype == "peek_opponent":
            valid = [i for i, c in enumerate(opp_hand) if c is not None]
            if valid:
                idx = valid[0]
                reveal_opp(idx)
                state["log"].append(f"{seat} used 9/10: peeked at opponent position {idx+1}.")

        elif stype == "blind_switch":
            largest = _largest_known(me_hand, me_known)
            me_valid = [i for i, c in enumerate(me_hand) if c is not None]
            opp_valid = [i for i, c in enumerate(opp_hand) if c is not None]
            if me_valid and opp_valid:
                mi = largest[0] if largest else me_valid[0]
                oi = opp_valid[0]
                me_hand[mi], opp_hand[oi] = opp_hand[oi], me_hand[mi]
                me_known[mi] = False
                forget_opp(oi)
                touch(mi, oi)
                state["log"].append(
                    f"{seat} used J/Q: blind-switched its position {mi+1} with opponent's {oi+1}.")

        elif stype == "looking_switch":
            largest = _largest_known(me_hand, me_known)
            me_valid = [i for i, c in enumerate(me_hand) if c is not None]
            opp_valid = [i for i, c in enumerate(opp_hand) if c is not None]
            if me_valid and opp_valid:
                mi = largest[0] if largest else me_valid[0]
                oi = opp_valid[0]
                reveal_opp(oi)
                if card_value(opp_hand[oi]) < card_value(me_hand[mi]):
                    me_hand[mi], opp_hand[oi] = opp_hand[oi], me_hand[mi]
                    me_known[mi] = True
                    forget_opp(oi)
                    touch(mi, oi)
                    state["log"].append(
                        f"{seat} used K: looked and switched its position {mi+1} with opponent's {oi+1}.")
                else:
                    me_known[mi] = True
                    touch(mi)
                    state["log"].append(f"{seat} used K: looked but chose not to switch.")

        return state

    def apply_computer_special(self, state, stype):
        return self.apply_special(state, "computer", stype)


PROFILES = {
    "greedy": StrategyProfile(
        key="greedy",
        name="Greedy Minimizer",
        rules=[
            "Snaps any known card the instant its rank matches the discard pile.",
            "Draws from the discard pile only when its top card is lower than the highest "
            "card it knows; otherwise draws from the deck.",
            "Replaces its highest known card when the draw is lower; if the draw is its new "
            "highest but 6 or lower, gambles it onto an unknown card; otherwise discards the "
            "draw and uses its power.",
            "Calls Cambio once all four cards are known and their total is 8 or less.",
        ],
    ),
    "aggressive": StrategyProfile(
        key="aggressive",
        name="Aggressive Caller",
        rules=[
            "Snaps any known matching card immediately.",
            "Draws from the discard pile whenever its top beats the highest card it knows.",
            "Gambles boldly: swaps a drawn card of 8 or lower onto an unknown slot.",
            "Calls Cambio early — when all cards are known and total ≤ 12, or with at most "
            "one unknown card when its known cards total ≤ 6.",
        ],
        gamble_max=8,
        cambio_all_known_sum=12,
        cambio_known_sum=6,
    ),
    "conservative": StrategyProfile(
        key="conservative",
        name="Patient Perfectionist",
        rules=[
            "Snaps any known matching card immediately.",
            "Always draws a fresh card from the deck (never trusts the discard pile).",
            "Never gambles: only replaces a known card when the draw is strictly lower; "
            "otherwise discards the draw and uses its power.",
            "Calls Cambio only when all four cards are known and their total is 5 or less.",
        ],
        draw_discard=False,
        gamble_max=0,
        cambio_all_known_sum=5,
    ),
    "snapper": StrategyProfile(
        key="snapper",
        name="Selective Snapper",
        rules=[
            "Only snaps high cards (value 7 or above) — deliberately keeps low and negative "
            "cards (like red Kings, worth −1) in hand.",
            "Draws from the discard pile when its top beats the highest card it knows.",
            "Replaces its highest known card when the draw is lower; gambles a drawn card 6 "
            "or lower onto an unknown slot; otherwise discards and uses the power.",
            "Calls Cambio once all four cards are known and their total is 8 or less.",
        ],
        snap_mode="high_only",
        snap_min_value=7,
    ),
    "power": StrategyProfile(
        key="power",
        name="Power Player",
        rules=[
            "Snaps any known matching card immediately.",
            "Always discards drawn peek cards (7–10) to fire their power and learn cards, "
            "rather than keeping them in hand.",
            "Draws from the discard pile when its top beats the highest card it knows; only "
            "gambles a non-special draw of 4 or lower onto an unknown slot.",
            "Calls Cambio once all four cards are known and their total is 8 or less.",
        ],
        discard_specials_for_info=True,
        gamble_max=4,
    ),
}


def get(key):
    return SmartStrategy(PROFILES[key])
