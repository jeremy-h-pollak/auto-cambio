"""
GameEngine: owns state, drives turn flow.
Computer turns (including snaps and special abilities) run synchronously.
"""

import random
from .rules import (
    apply_move, create_initial_state,
    snap_eligible_indices, opp_snap_eligible_indices, special_type,
    PHASE_GAME_OVER, PHASE_PLAYER_DRAW, PHASE_PLAYER_SPECIAL, COMPUTER_TURN,
)
from .strategy import choose_move, should_snap, apply_computer_special


class GameEngine:
    def __init__(self):
        self.state = create_initial_state()

    def reset(self):
        self.state = create_initial_state()

    def player_move(self, action, hand_index=None, owner=None, do_switch=None):
        move = {"action": action}
        if hand_index is not None: move["hand_index"] = hand_index
        if owner is not None:      move["owner"] = owner
        if do_switch is not None:  move["do_switch"] = do_switch

        self.state = apply_move(self.state, move)
        self._run_computer_snaps()

        while self.state["phase"] == COMPUTER_TURN:
            self._run_computer_turn()

    # ── Computer snap: check after any state change ───────────────────────────
    def _run_computer_snaps(self):
        while self.state["phase"] not in (PHASE_GAME_OVER, PHASE_PLAYER_SPECIAL):
            eligible = snap_eligible_indices(
                self.state["computer_hand"], self.state["discard_pile"]
            )
            snapped = False
            for idx in eligible:
                if should_snap(self.state, idx):
                    # Simultaneous snap: if player can also snap, 50/50 race
                    if self.state["phase"] == PHASE_PLAYER_DRAW:
                        player_own = snap_eligible_indices(
                            self.state["player_hand"], self.state["discard_pile"]
                        )
                        player_opp = opp_snap_eligible_indices(
                            self.state["computer_hand"],
                            self.state["player_opponent_known"],
                            self.state["discard_pile"],
                        )
                        if (player_own or player_opp) and random.random() < 0.5:
                            return  # player wins the race
                    self.state = apply_move(
                        self.state, {"action": "snap", "by": "computer", "hand_index": idx}
                    )
                    snapped = True
                    break  # re-evaluate eligible list after each snap
            if not snapped:
                break

    # ── Computer full turn ───────────────────────────────────────────────────
    def _run_computer_turn(self):
        if self.state["phase"] != COMPUTER_TURN:
            return

        known = self.state["computer_known"]

        # Step 1: draw or call cambio
        move1 = choose_move(self.state, known)
        self.state = apply_move(self.state, move1)
        if move1["action"] == "call_cambio":
            return

        # Step 2: swap or discard
        if self.state["phase"] == COMPUTER_TURN:
            drawn_card = self.state.get("drawn_card")
            move2 = choose_move(self.state, known)
            self.state = apply_move(self.state, move2)

            # Apply computer special ability if a special card was discarded
            if move2["action"] == "discard_drawn" and drawn_card:
                stype = special_type(drawn_card)
                blocked = (
                    stype in ("blind_switch", "looking_switch")
                    and self.state["cambio_called_by"] is not None
                )
                if stype and not blocked and self.state["phase"] != PHASE_GAME_OVER:
                    self.state = apply_computer_special(self.state, stype)

        self._run_computer_snaps()
