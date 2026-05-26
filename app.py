import uuid
from flask import Flask, render_template, request, session

from game.engine import GameEngine
import game.strategy as random_strategy
from game import strategies
from game.rules import (
    card_value, hand_value, hand_size, is_red, get_scores, get_winner,
    snap_eligible_indices, opp_snap_eligible_indices, PHASE_GAME_OVER,
)

app = Flask(__name__)
app.secret_key = "cambio-dev-secret"

GAMES: dict[str, GameEngine] = {}

RANDOM_DESCRIPTION = [
    "Draws, swaps, snaps, and calls Cambio at random.",
    "No memory and no planning — the baseline every strategy aims to beat.",
]

# Strongest of 15 tested strategies by win rate vs Random (multi-seed eval,
# 40k games each). Surfaced in the chooser as the "Hardest Mode" boss.
HARDEST_KEY = "minimalist"
HARDEST_WINRATE = "~75%"

# Chooser display order: Hardest Mode, the five original named strategies, Random.
NAMED_OPPONENTS = ["greedy", "aggressive", "conservative", "snapper", "power"]
OPPONENT_KEYS = ["hardest"] + NAMED_OPPONENTS + ["random"]


def _opponent_info(key):
    """(name, rules) for an opponent key."""
    if key == "hardest":
        p = strategies.PROFILES[HARDEST_KEY]
        return f"Hardest Mode — {p.name}", [
            f"The strongest AI found across 15 tested strategies "
            f"({HARDEST_WINRATE} win rate vs random).",
            *p.rules,
        ]
    if key in strategies.PROFILES:
        p = strategies.PROFILES[key]
        return p.name, p.rules
    return "Random AI", RANDOM_DESCRIPTION


def opponent_catalog():
    """List of (key, name, rules) in chooser display order."""
    return [(key, *_opponent_info(key)) for key in OPPONENT_KEYS]


def _strategy_object(key):
    """Resolve an opponent key to a strategy object the engine can drive."""
    if key == "hardest":
        return strategies.get(HARDEST_KEY)
    if key in strategies.PROFILES:
        return strategies.get(key)
    return random_strategy


def _get_engine() -> GameEngine:
    sid = session.get("sid")
    if not sid or sid not in GAMES:
        sid = str(uuid.uuid4())
        session["sid"] = sid
        GAMES[sid] = GameEngine(strategy=_strategy_object(session.get("opponent", "random")))
    return GAMES[sid]


def _template_context(engine: GameEngine) -> dict:
    s = engine.state
    if s["phase"] == PHASE_GAME_OVER:
        player_score, computer_score = get_scores(s)
        winner = get_winner(s)
        player_cards = hand_size(s["player_hand"])
        computer_cards = hand_size(s["computer_hand"])
    else:
        player_score = computer_score = winner = player_cards = computer_cards = None
    opponent = session.get("opponent", "random")
    name, rules = _opponent_info(opponent)
    return {
        "state": s,
        "card_value": card_value,
        "hand_value": hand_value,
        "is_red": is_red,
        "player_score": player_score,
        "computer_score": computer_score,
        "winner": winner,
        "player_cards": player_cards,
        "computer_cards": computer_cards,
        "snap_eligible": snap_eligible_indices(s["player_hand"], s["discard_pile"], s["player_known"]),
        "opp_snap_eligible": opp_snap_eligible_indices(
            s["computer_hand"], s["player_opponent_known"], s["discard_pile"]
        ),
        "opponent": opponent,
        "opponent_name": name,
        "opponent_rules": rules,
    }


@app.route("/")
def index():
    # Land on the opponent chooser — pick an AI before any game starts.
    return render_template("game.html", partial="partials/chooser.html",
                           catalog=opponent_catalog())


@app.route("/choose", methods=["POST"])
def choose():
    return render_template("partials/chooser.html", catalog=opponent_catalog())


@app.route("/describe", methods=["POST"])
def describe():
    key = request.form.get("opponent", "random")
    if key not in OPPONENT_KEYS:
        key = "random"
    name, rules = _opponent_info(key)
    return render_template("partials/confirm.html", key=key, name=name, rules=rules)


@app.route("/play")
def play():
    engine = _get_engine()
    ctx = _template_context(engine)
    return render_template("game.html", partial="partials/board.html", **ctx)


@app.route("/move", methods=["POST"])
def move():
    engine = _get_engine()
    action     = request.form.get("action")
    hand_index = request.form.get("hand_index")
    owner      = request.form.get("owner")
    do_switch  = request.form.get("do_switch")
    target     = request.form.get("target")

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
    if opponent in OPPONENT_KEYS:
        session["opponent"] = opponent
    sid = session.get("sid") or str(uuid.uuid4())
    session["sid"] = sid
    # Fresh engine so the chosen opponent strategy takes effect immediately.
    GAMES[sid] = GameEngine(strategy=_strategy_object(session.get("opponent", "random")))
    ctx = _template_context(GAMES[sid])
    return render_template("partials/board.html", **ctx)


if __name__ == "__main__":
    # Port 5000 is reserved by macOS AirPlay; use 5001 instead
    app.run(debug=True, port=5001)
