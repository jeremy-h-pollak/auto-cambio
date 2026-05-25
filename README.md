# auto-cambio

A simulator and optimizer for a custom variant of the card game Cambio, written in Python.

## Overview

There are two ways to interact with this project:
- **Play the game** — a Flask web app where you play the Cambio variant against the computer.
- **Run a simulation** — play out many self-play AI games and generate an HTML analysis report, used to evaluate and tune strategies.

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

Then open <http://localhost:5001> in a browser. (Port 5001 is used because macOS
AirPlay reserves 5000.) This is equivalent to running `python app.py` directly.

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
