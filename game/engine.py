"""
GameEngine: owns state, drives turn flow.
The computer's turn is run synchronously (random AI is instant).
"""

from .rules import apply_move, create_initial_state, PHASE_GAME_OVER
from .strategy import choose_move

COMPUTER_TURN = "computer_turn"


class GameEngine:
    def __init__(self):
        self.state = create_initial_state()

    def reset(self):
        self.state = create_initial_state()

    def player_move(self, action, hand_index=None):
        move = {"action": action}
        if hand_index is not None:
            move["hand_index"] = hand_index

        self.state = apply_move(self.state, move)

        # Run computer turn(s) synchronously if it's now the computer's turn
        while self.state["phase"] == COMPUTER_TURN:
            self._run_computer_turn()

    def _run_computer_turn(self):
        known = self.state["computer_known"]

        # Step 1: draw or call cambio
        move1 = choose_move(self.state, known)
        self.state = apply_move(self.state, move1)

        if move1["action"] == "call_cambio":
            return  # player gets last turn, handled by UI

        # Step 2: swap or discard
        if self.state["phase"] == COMPUTER_TURN:
            move2 = choose_move(self.state, known)
            self.state = apply_move(self.state, move2)
