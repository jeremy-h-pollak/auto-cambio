import uuid
from flask import Flask, render_template, request, session, redirect, url_for

from game.engine import GameEngine
from game.rules import card_value, hand_value, is_red, get_scores, PHASE_GAME_OVER

app = Flask(__name__)
app.secret_key = "cambio-dev-secret"

# In-memory game store: session_id -> GameEngine
GAMES: dict[str, GameEngine] = {}


def _get_engine() -> GameEngine:
    sid = session.get("sid")
    if not sid or sid not in GAMES:
        sid = str(uuid.uuid4())
        session["sid"] = sid
        GAMES[sid] = GameEngine()
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
    action = request.form.get("action")
    hand_index = request.form.get("hand_index")
    if hand_index is not None:
        hand_index = int(hand_index)
    engine.player_move(action, hand_index)
    ctx = _template_context(engine)
    return render_template("partials/board.html", **ctx)


@app.route("/new", methods=["POST"])
def new_game():
    engine = _get_engine()
    engine.reset()
    ctx = _template_context(engine)
    return render_template("partials/board.html", **ctx)


if __name__ == "__main__":
    # Port 5000 is reserved by macOS AirPlay; use 5001 instead
    app.run(debug=True, port=5001)
