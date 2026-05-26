# auto-cambio

A simulator and optimizer for a custom variant of the card game Cambio, written in Python.

## Overview

There are three ways to interact with this project:
- **Play the game** — a Flask web app where you play the Cambio variant against the computer.
- **Run a simulation** — play out many self-play AI games and generate an HTML analysis report, used to evaluate and tune strategies.
- **Run a tournament** — play every strategy against every other in a round robin and rank them all on a single Elo-style scale.

## Rules

*Custom rules TBD — to be documented here.*

## Project Structure

*To be defined as the project grows.*

## Getting Started

### Setup

Install the runtime dependency (Flask):

```bash
pip install -r requirements.txt
```

### Play the game

```bash
./run-game.sh
```

The app prefers port 5001 (macOS AirPlay reserves 5000), but if 5001 is already
in use it automatically falls back to the next free port — so it always starts,
even with another copy already running. On startup it prints the exact URL, e.g.
`Cambio is running at -> http://127.0.0.1:5001`; open the URL shown in the
terminal. This is equivalent to running `python app.py` directly.

### Run a simulation

```bash
./run-sim.sh                                        # 500 games, greedy vs random
./run-sim.sh --strategy minimalist --seed 1 -n 2000 --quiet
./run-sim.sh --strategy random --seed 1 -n 1000     # random-vs-random baseline
```

This writes a standalone HTML report (default `report.html`) and prints a summary
to the console. All arguments are forwarded to `simulate.py`:

| Flag | Default | Meaning |
|---|---|---|
| `-n, --games` | `500` | number of games to simulate |
| `-o, --output` | `report.html` | path for the HTML report |
| `--strategy` | `greedy` | strategy profile to evaluate, or `random` for the random-vs-random baseline |
| `--seed` | none | random seed for reproducible runs |
| `--quiet` | off | suppress the per-game log; show progress only |
| `--max-turns` | `1000` | safety cap on turns per game |

### Run a tournament

```bash
./run-tournament.sh                                 # 15 profiles + random, 100 games/pairing
./run-tournament.sh -k 400 --seed 1 --quiet
./run-tournament.sh --no-random -o profiles.html    # profiles only, no random anchor
```

Every pair of strategies plays `K` games with balanced sides (each starts half the
games), and results are fit to a [Bradley-Terry](https://en.wikipedia.org/wiki/Bradley%E2%80%93Terry_model)
model mapped onto an Elo-style scale — so all strategies are ranked on one
comparable number. Only win rate matters; margins are ignored and a tie counts as
half a win. Random is included as a fixed 1500-point calibration floor. This writes
a standalone HTML report (default `tournament.html`) with a ranking table and a
head-to-head win-rate matrix, and prints the rankings to the console. All arguments
are forwarded to `tournament.py`:

| Flag | Default | Meaning |
|---|---|---|
| `-k, --games` | `100` | games per pairing (a multiple of 4 balances sides exactly) |
| `-o, --output` | `tournament.html` | path for the HTML report |
| `--seed` | none | random seed for reproducible runs |
| `--no-random` | off | exclude the random baseline (profiles only) |
| `--max-turns` | `1000` | safety cap on turns per game |
| `--quiet` | off | suppress per-pairing progress |
