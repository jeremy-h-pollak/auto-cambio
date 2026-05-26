"""
Advanced Cambio strategies — a step up from the parameterized `SmartStrategy`.

The existing `PROFILES` are all one rule-engine with different constants, which
caps how good they can get. These strategies add the three things that engine
lacks and that actually decide Cambio games:

  1. **Opponent memory.** A 9/10/K peek is recorded in per-game scratch memory
     (`state["_amem"][seat]`) and reused on later turns — the parameterized
     strategies peek and immediately forget. `apply_move` deep-copies the state
     each call (see rules.apply_move), so memory stashed in the state dict
     persists within a game and resets when the next game's state is created.
  2. **Expected-value reasoning.** Unknown cards are valued at the deck mean
     (≈6.46), so a strategy can estimate its own and the opponent's totals and
     time Cambio by *who is ahead* rather than a crude known-sum threshold.
  3. **Purposeful powers.** K looks and switches only on a strict gain; J/Q dumps
     a known-high card only when it clears the deck mean; peeks target the slot
     that teaches the most.

Fair information only: a strategy reads a card's value solely where it legitimately
knows it — its own `*_known` slots and opponent slots it has peeked. Memory is
pruned by *confirming* a remembered slot still holds the same card (a swap/snap
is publicly visible); a changed slot is forgotten, never re-read for its new value.

Objective is to **win**, not to win big — margins are ignored in the tournament,
so the Cambio rules below aim at *being ahead* (and dodging the +5 mis-call
penalty), not at maximizing the lead.

Each class exposes the duck-typed interface the simulator and tournament use:
    choose_move(state, known_indices)     -> move dict
    should_snap(state, hand_index, seat)  -> bool
    apply_special(state, seat, stype)     -> state   (seat-general; mutates)
    apply_computer_special(state, stype)  -> state   (engine entry point)
"""

from .rules import card_value, special_type

# Deck mean: A..10 + J(11) + Q(12) + red K(-1, x2) + black K(13, x2) over 52 cards
# = 336 / 52 ≈ 6.46. The value of a slot we know nothing about.
EV_UNKNOWN = 6.46


def _other(seat):
    return "computer" if seat == "player" else "player"


def _known_value_slots(hand, known):
    """[(index, value)] for slots whose card the owner knows."""
    return [
        (i, card_value(c))
        for i, c in enumerate(hand)
        if c is not None and i < len(known) and known[i]
    ]


def _highest_known(hand, known):
    slots = _known_value_slots(hand, known)
    return max(slots, key=lambda s: s[1]) if slots else None


def _unknown_slots(hand, known):
    return [
        i for i, c in enumerate(hand)
        if c is not None and (i >= len(known) or not known[i])
    ]


class AdvancedStrategy:
    """Shared machinery; subclasses set the knobs and override a hook or two."""

    key = "advanced"
    name = "Advanced"
    rules = []

    # ── Knobs (overridden per strategy) ──────────────────────────────────────
    cambio_abs_cap = 13      # never call Cambio unless our estimated total ≤ this
    cambio_margin = 2        # ...and we estimate we lead the opponent by ≥ this
    gamble_max = 6           # gamble a drawn card ≤ this onto an unknown slot
    grab_discard_max = 4     # grab a discard top ≤ this when it improves a slot
    snap_negatives = False   # snap red Kings too (shrink the hand at all costs)
    blind_switch_min_give = 9   # only J/Q-dump a known card worth ≥ this

    # ── Per-game opponent memory ─────────────────────────────────────────────
    def _memory(self, state, seat):
        return state.setdefault("_amem", {}).setdefault(seat, {})

    def _prune_memory(self, state, seat):
        """Forget any remembered opponent card that is gone or has changed.

        Only confirms a card we already saw is still there (a publicly visible
        swap/snap); a changed slot is dropped without reading its new value.
        """
        mem = self._memory(state, seat)
        opp_hand = state[f"{_other(seat)}_hand"]
        for i in list(mem):
            c = opp_hand[i] if i < len(opp_hand) else None
            if c is None or c["rank"] != mem[i]["rank"] or c["suit"] != mem[i]["suit"]:
                del mem[i]

    def _remember(self, state, seat, idx, card):
        self._memory(state, seat)[idx] = {"rank": card["rank"], "suit": card["suit"]}

    # ── Estimators ───────────────────────────────────────────────────────────
    def _est_own_total(self, state, seat):
        hand, known = state[f"{seat}_hand"], state[f"{seat}_known"]
        total = 0.0
        for i, c in enumerate(hand):
            if c is None:
                continue
            total += card_value(c) if (i < len(known) and known[i]) else EV_UNKNOWN
        return total

    def _est_opp_total(self, state, seat):
        opp_hand = state[f"{_other(seat)}_hand"]
        mem = self._memory(state, seat)
        total = 0.0
        for i, c in enumerate(opp_hand):
            if c is None:
                continue
            total += card_value(mem[i]) if i in mem else EV_UNKNOWN
        return total

    # ── Decisions ──────────────────────────────────────────────────────────
    def choose_move(self, state, known_indices=None):
        seat = state["current_turn"]
        self._prune_memory(state, seat)
        drawn = state["drawn_card"]
        # Opponent already called Cambio (or emptied a hand): this is our final
        # turn. Calling Cambio ourselves is illegal/pointless — just improve.
        last_turn = state["cambio_called_by"] is not None

        if drawn is None:
            if not last_turn and self._should_call_cambio(state, seat):
                return {"action": "call_cambio"}
            return self._draw_source(state, seat)
        return self._action_with_drawn(state, seat, drawn, last_turn)

    def _should_call_cambio(self, state, seat):
        own = self._est_own_total(state, seat)
        if own > self.cambio_abs_cap:
            return False
        return own + self.cambio_margin <= self._est_opp_total(state, seat)

    def _improves(self, state, seat, value):
        """Would a card of `value` find a useful home in our hand?"""
        hand, known = state[f"{seat}_hand"], state[f"{seat}_known"]
        hi = _highest_known(hand, known)
        if hi and value < hi[1]:
            return True
        return bool(_unknown_slots(hand, known)) and value <= self.gamble_max

    def _draw_source(self, state, seat):
        discard = state["discard_pile"]
        if discard:
            top = card_value(discard[-1])
            if top <= self.grab_discard_max and self._improves(state, seat, top):
                return {"action": "draw_discard"}
        return {"action": "draw_deck"}

    def _wants_opp_info(self, state, seat):
        """Still opponent slots left to learn?"""
        opp_cards = sum(c is not None for c in state[f"{_other(seat)}_hand"])
        return len(self._memory(state, seat)) < opp_cards

    def _action_with_drawn(self, state, seat, drawn, last_turn):
        hand, known = state[f"{seat}_hand"], state[f"{seat}_known"]
        drawn_val = card_value(drawn)
        hi = _highest_known(hand, known)
        stype = special_type(drawn)
        unknown = _unknown_slots(hand, known)

        # 1. A big guaranteed improvement (burying an 11/12/13) beats everything.
        if hi and drawn_val < hi[1] and hi[1] >= 11:
            return {"action": "swap", "hand_index": hi[0]}
        # 2. Spend a peek card on its power while the table is still fuzzy — knowing
        #    our own cards unlocks snaps and a precise Cambio; mapping theirs sharpens
        #    switches and the lead estimate. (This information edge decides games.)
        if not last_turn and stype in ("peek_own", "peek_opponent"):
            if (stype == "peek_own" and unknown) or self._wants_opp_info(state, seat):
                return {"action": "discard_drawn"}
        # 3. Any other guaranteed improvement: bury a known high card.
        if hi and drawn_val < hi[1]:
            return {"action": "swap", "hand_index": hi[0]}
        # 4. Gamble a below-mean draw onto an unknown slot.
        if unknown and drawn_val <= self.gamble_max:
            return {"action": "swap", "hand_index": unknown[0]}
        # 5. Otherwise discard (fires a switch power too, if any).
        return {"action": "discard_drawn"}

    def should_snap(self, state, hand_index, seat="computer"):
        card = state[f"{seat}_hand"][hand_index]
        if card is None:
            return False
        if card_value(card) < 0 and not self.snap_negatives:
            return False        # keep red Kings — snapping one *raises* our sum
        return True

    # ── Powers (seat-general) ─────────────────────────────────────────────────
    def apply_special(self, state, seat, stype):
        self._prune_memory(state, seat)
        opp = _other(seat)
        me_hand, me_known = state[f"{seat}_hand"], state[f"{seat}_known"]
        opp_hand = state[f"{opp}_hand"]

        if stype == "peek_own":
            self._peek_own(me_hand, me_known)
        elif stype == "peek_opponent":
            self._peek_opponent(state, seat, opp_hand)
        elif stype == "blind_switch":
            self._blind_switch(state, seat, me_hand, me_known, opp_hand)
        elif stype == "looking_switch":
            self._looking_switch(state, seat, me_hand, me_known, opp_hand)
        return state

    def apply_computer_special(self, state, stype):
        return self.apply_special(state, "computer", stype)

    def _peek_own(self, me_hand, me_known):
        for i, c in enumerate(me_hand):
            if c is not None and not me_known[i]:
                me_known[i] = True      # now we can swap it sensibly / snap it
                return

    def _peek_opponent(self, state, seat, opp_hand):
        mem = self._memory(state, seat)
        for i, c in enumerate(opp_hand):       # learn a slot we don't know yet
            if c is not None and i not in mem:
                self._remember(state, seat, i, c)
                return

    def _blind_switch(self, state, seat, me_hand, me_known, opp_hand):
        """Dump a known-high card; grab a remembered-low card if we have one."""
        hi = _highest_known(me_hand, me_known)
        if not hi or hi[1] < self.blind_switch_min_give:
            return                              # nothing worth dumping
        mi = hi[0]
        mem = self._memory(state, seat)
        opp_valid = [i for i, c in enumerate(opp_hand) if c is not None]
        if not opp_valid:
            return
        remembered_low = sorted(
            ((i, card_value(mem[i])) for i in opp_valid if i in mem),
            key=lambda s: s[1],
        )
        if remembered_low and remembered_low[0][1] < hi[1]:
            oi, take_known = remembered_low[0][0], True   # steal a card we know is low
        else:
            unseen = [i for i in opp_valid if i not in mem]
            oi, take_known = (unseen[0] if unseen else opp_valid[0]), False
        my_card = dict(me_hand[mi])
        me_hand[mi], opp_hand[oi] = opp_hand[oi], me_hand[mi]
        me_known[mi] = take_known               # known only if we'd peeked the taken card
        self._remember(state, seat, oi, my_card)  # opp now holds our old card

    def _looking_switch(self, state, seat, me_hand, me_known, opp_hand):
        """Look at one of our cards and one of theirs; switch only on a strict gain."""
        me_valid = [i for i, c in enumerate(me_hand) if c is not None]
        opp_valid = [i for i, c in enumerate(opp_hand) if c is not None]
        if not me_valid or not opp_valid:
            return
        hi = _highest_known(me_hand, me_known)
        mi = hi[0] if hi else me_valid[0]
        me_known[mi] = True                     # the power reveals our chosen card
        my_val = card_value(me_hand[mi])

        mem = self._memory(state, seat)
        remembered_low = sorted(
            ((i, card_value(mem[i])) for i in opp_valid if i in mem and card_value(mem[i]) < my_val),
            key=lambda s: s[1],
        )
        if remembered_low:
            oi = remembered_low[0][0]
        else:
            unseen = [i for i in opp_valid if i not in mem]
            oi = unseen[0] if unseen else opp_valid[0]

        self._remember(state, seat, oi, opp_hand[oi])    # we look at it
        if card_value(opp_hand[oi]) < my_val:            # strict gain → switch
            my_card = dict(me_hand[mi])
            me_hand[mi], opp_hand[oi] = opp_hand[oi], me_hand[mi]
            me_known[mi] = True                          # we saw what we took
            self._remember(state, seat, oi, my_card)     # opp now holds our old card


# ── The five strategies ────────────────────────────────────────────────────────

class Architect(AdvancedStrategy):
    """Expected-value maximizer: estimates both totals and times everything by them."""
    key, name = "architect", "The Architect"
    rules = [
        "Values every unknown card at the deck mean (≈6.5) to estimate its own "
        "and the opponent's totals, and decides by who is ahead.",
        "Records every 9/10/K peek and reuses it; fires peek cards it can't use "
        "to improve, to keep mapping the table.",
        "K switches only on a strict gain; J/Q dumps a known card only when it is "
        "worth 9+ (above the deck mean). Snaps positives, keeps red Kings.",
        "Calls Cambio when its estimated total is ≤13 and it estimates a lead.",
    ]
    cambio_abs_cap, cambio_margin = 13, 2
    gamble_max, grab_discard_max, blind_switch_min_give = 6, 4, 9


class Cartographer(AdvancedStrategy):
    """Information-first: maps both hands with peeks, then calls Cambio with confidence."""
    key, name = "cartographer", "The Cartographer"
    rules = [
        "Spends 7/8/9/10 on their peeks to map both hands before committing — "
        "discards them for the power even when a small swap is available.",
        "Builds a memory of the opponent's cards and only commits to Cambio once "
        "it has peeked enough of them to trust its read.",
        "K/J-Q switch on gains; keeps red Kings; gambles only draws ≤5.",
        "Calls Cambio at an estimated total ≤12 with a lead — or earlier if its "
        "own total is already tiny.",
    ]
    cambio_abs_cap, cambio_margin = 12, 1
    gamble_max, grab_discard_max, blind_switch_min_give = 5, 3, 10

    def _still_exploring(self, state, seat):
        own_unknown = bool(_unknown_slots(state[f"{seat}_hand"], state[f"{seat}_known"]))
        opp_mapped = len(self._memory(state, seat))
        opp_cards = sum(c is not None for c in state[f"{_other(seat)}_hand"])
        return own_unknown or opp_mapped < min(3, opp_cards)

    def _action_with_drawn(self, state, seat, drawn, last_turn):
        # Prioritize learning: fire a drawn peek while the table is still fuzzy.
        if (not last_turn and special_type(drawn) in ("peek_own", "peek_opponent")
                and self._still_exploring(state, seat)):
            return {"action": "discard_drawn"}
        return super()._action_with_drawn(state, seat, drawn, last_turn)

    def _should_call_cambio(self, state, seat):
        if len(self._memory(state, seat)) < 2:
            # Too little read on the opponent — only bail out on a genuinely tiny hand.
            own = self._est_own_total(state, seat)
            return own <= 6 and own + self.cambio_margin <= self._est_opp_total(state, seat)
        return super()._should_call_cambio(state, seat)


class Saboteur(AdvancedStrategy):
    """Switch specialist: peeks to find the opponent's low cards, then steals them."""
    key, name = "saboteur", "The Saboteur"
    rules = [
        "Hunts the opponent's hand with 9/10 peeks, then uses K and J/Q to steal "
        "their lowest known card while offloading its own worst.",
        "Dumps known cards worth 8+ via blind switch (more eagerly than most), "
        "and always takes a remembered-low card when one is on offer.",
        "Snaps positives, keeps red Kings, gambles draws ≤6.",
        "Calls Cambio at an estimated total ≤14 with a lead.",
    ]
    cambio_abs_cap, cambio_margin = 12, 2
    gamble_max, grab_discard_max, blind_switch_min_give = 6, 4, 8


class Sprinter(AdvancedStrategy):
    """Tempo: snaps relentlessly to shrink (even empty) its hand, then closes fast."""
    key, name = "sprinter", "The Sprinter"
    rules = [
        "Snaps every match — including red Kings — to shrink its hand; an empty "
        "hand scores 0 and ends the game on the opponent's last turn.",
        "Grabs cheap discards (≤5) and peeks its own cards to unlock more snaps.",
        "Gambles below-mean draws (≤6) onto unknown slots to churn toward low cards.",
        "Calls Cambio early — estimated total ≤12 with a lead.",
    ]
    cambio_abs_cap, cambio_margin = 12, 1
    gamble_max, grab_discard_max = 6, 5
    snap_negatives = True
    blind_switch_min_give = 10


class Sentinel(AdvancedStrategy):
    """Risk-averse closer: minimizes variance and calls Cambio only when safe."""
    key, name = "sentinel", "The Sentinel"
    rules = [
        "Never gambles onto unknowns unless the draw is ≤3; converts unknowns to "
        "knowns with peeks before committing.",
        "Keeps every negative card; never blind-switches (won't take a card sight "
        "unseen); only K-switches on a strict, seen gain.",
        "Snaps positives only.",
        "Calls Cambio only with a comfortable margin — estimated total ≤9 and a "
        "lead of 5+ — so the +5 mis-call penalty almost never bites.",
    ]
    cambio_abs_cap, cambio_margin = 9, 5
    gamble_max, grab_discard_max = 3, 3
    blind_switch_min_give = 99      # effectively never blind-switch


ADVANCED = {
    cls.key: cls
    for cls in (Architect, Cartographer, Saboteur, Sprinter, Sentinel)
}


def get_advanced(key):
    return ADVANCED[key]()
