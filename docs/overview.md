# Overview

**auto-cambio** is a Python implementation of a custom two-player variant of the
card game **Cambio** (one human or bot vs. one bot), built for two purposes:

- **Play it** — a Flask + HTMX web app to play against a configurable AI opponent.
- **Optimize it** — tooling to pit AI strategies against each other across tens of
  thousands of games, measure them, and rank them on a single skill scale.

## The core mental model

Each player holds a small hand of face-down cards and mostly can't see them. Card
ranks map to point values (and a couple of cards are worth *negative* points). You
take turns drawing and swapping cards to lower your hand's total, peeking and
sabotaging via special-card powers, and "snapping" cards that match the discard
pile to shrink your hand. When you think your total is lowest, you **call Cambio**
to end the round. **Lowest total wins** — but miscall and you take a penalty.

The full rules are in [rules.md](rules.md).

## Three entry points

| Mode | Launch | Code | Output |
|---|---|---|---|
| **Play** the game | `./run-game.sh` (or `python app.py`) | [`app.py`](../app.py) + `templates/` | Web UI on <http://localhost:5001> |
| **Simulate** self-play | `./run-sim.sh` (or `python simulate.py`) | [`simulate.py`](../simulate.py) | `report.html` + console summary |
| **Run** a tournament | `./run-tournament.sh` (or `python tournament.py`) | [`tournament.py`](../tournament.py) | `tournament.html` + console rankings |

All three drive the **same rules engine** ([`game/rules.py`](../game/rules.py)); they
differ only in who makes the decisions and how results are presented. See
[architecture.md](architecture.md) for how the layers fit together.

- **Play** → driven by [`GameEngine`](../game/engine.py); the human plays one seat, a
  strategy plays the other. Details in [web-app.md](web-app.md).
- **Simulate** → a "smart" strategy vs. the random baseline over N games, reported as
  win rates and distributions. Details in [simulation.md](simulation.md).
- **Run a tournament** → every strategy vs. every other, fit to a Bradley-Terry / Elo
  rating with Random anchored at 1500. Details in [tournament.md](tournament.md).

## Why a simulator *and* a tournament?

The simulator answers "how does strategy X do **against random**?" — useful, but
random is a weak yardstick and strong strategies pile up near a ~75% ceiling that
says more about the opponent than about them. The tournament answers "how do the
strategies rank **against each other**?", separating bots that the simulator can't.
The experiment log in [reports-workflow.md](reports-workflow.md) tracks these runs
over time.

## Tech at a glance

- **Python 3.13**, standard library only for the game/sim/tournament logic.
- **Flask** is the single runtime dependency (`requirements.txt`); the web UI is
  **pure HTMX** with **no hand-written JavaScript**.
- **pytest** + **pytest-cov** for tests (`requirements-dev.txt`), run in CI.
- Reports are **dependency-free standalone HTML** (inline CSS, plain bars) that open
  offline.
