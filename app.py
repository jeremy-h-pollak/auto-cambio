import uuid
from flask import Flask, render_template, request, session, redirect, url_for

from game.engine import GameEngine
import game.strategy as random_strategy
import game.strategy_smart as smart_strategy
from game.rules import (
    card_value, hand_value, is_red, get_scores,
    snap_eligible_indices, opp_snap_eligible_indices, PHASE_GAME_OVER,
)

app = Flask(__name__)
app.secret_key = "cambio-dev-secret"

GAMES: dict[str, GameEngine] = {}

STRATEGY_MODULES = {"random": random_strategy, "smart": smart_strategy}

# Bullet summary of the smart AI, shown in the UI (keep in sync with strategy_smart.py).
SMART_AI_DESCRIPTION = [
    "Snaps instantly whenever a card it knows matches the discard pile.",
    "Draws from the discard pile when its top card is lower than the AI's "
    "highest known card; otherwise draws a fresh card from the deck.",
    "If the draw beats its highest known card, it replaces that card. If the "
    "draw is its new highest but 6 or lower, it gambles it onto an unknown "
    "card. Otherwise it discards the draw and uses the card's power.",
    "Calls Cambio once it knows all four of its cards and their total is 8 or less.",
]


def _strategy_module():
    return STRATEGY_MODULES.get(session.get("opponent", "random"), random_strategy)


def _get_engine() -> GameEngine:
    sid = session.get("sid")
    if not sid or sid not in GAMES:
        sid = str(uuid.uuid4())
        session["sid"] = sid
        GAMES[sid] = GameEngine(strategy=_strategy_module())
    return GAMES[sid]


def _template_context(engine: GameEngine) -> dict:
    s = engine.state
    player_score, computer_score = (
        get_scores(s) if s["phase"] == PHASE_GAME_OVER else (None, None)
    )
    return {
        "state": s,
        "card_value": card_value,
        "hand_value": hand_value,
        "is_red": is_red,
        "player_score": player_score,
        "computer_score": computer_score,
        "snap_eligible": snap_eligible_indices(s["player_hand"], s["discard_pile"], s["player_known"]),
        "opp_snap_eligible": opp_snap_eligible_indices(
            s["computer_hand"], s["player_opponent_known"], s["discard_pile"]
        ),
        "opponent": session.get("opponent", "random"),
        "smart_description": SMART_AI_DESCRIPTION,
    }


@app.route("/")
def index():
    engine = _get_engine()
    engine.reset()
    return redirect(url_for("play"))


@app.route("/play")
def play():
    engine = _get_engine()
    ctx = _template_context(engine)
    return render_template("game.html", **ctx)


@app.route("/move", methods=["POST"])
def move():
    engine = _get_engine()
    action     = request.form.get("action")
    hand_index = request.form.get("hand_index")
    owner      = request.form.get("owner")
    do_switch  = request.form.get("do_switch")

    target    = request.form.get("target")

    kwargs = {}
    if hand_index is not None: kwargs["hand_index"] = int(hand_index)
    if owner is not None:      kwargs["owner"] = owner
    if do_switch is not None:  kwargs["do_switch"] = (do_switch == "true")
    if target is not None:     kwargs["target"] = target

    engine.player_move(action, **kwargs)
    ctx = _template_context(engine)
    return render_template("partials/board.html", **ctx)


@app.route("/new", methods=["POST"])
def new_game():
    opponent = request.form.get("opponent")
    if opponent in STRATEGY_MODULES:
        session["opponent"] = opponent
    sid = session.get("sid") or str(uuid.uuid4())
    session["sid"] = sid
    # Fresh engine so a newly chosen opponent strategy takes effect immediately.
    GAMES[sid] = GameEngine(strategy=_strategy_module())
    ctx = _template_context(GAMES[sid])
    return render_template("partials/board.html", **ctx)


if __name__ == "__main__":
    # Port 5000 is reserved by macOS AirPlay; use 5001 instead
    app.run(debug=True, port=5001)
