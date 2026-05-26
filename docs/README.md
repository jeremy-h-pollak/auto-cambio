# auto-cambio documentation

Reference docs for the **auto-cambio** project — a Flask + HTMX web game, a
self-play simulator, and a round-robin rating tournament for a custom variant of
the card game **Cambio**.

These docs exist so contributors (human or AI) can get rich context without
re-reading the whole codebase each time. `CLAUDE.md` points here as the source of
truth; the root [`README.md`](../README.md) is the short, human-facing entry point.

## Map

| Doc | What it covers |
|---|---|
| [overview.md](overview.md) | What the project is, the three entry points, the core mental model. |
| [rules.md](rules.md) | **Full rules** of the Cambio variant — setup, turns, snapping, specials, Cambio, scoring. Playable from this alone. |
| [architecture.md](architecture.md) | The three-layer design (rules / strategy / engine), the full game-state dict, the phase machine, and key invariants. |
| [project-structure.md](project-structure.md) | Annotated directory tree and a per-file responsibility note. |
| [web-app.md](web-app.md) | The Flask app: routes, sessions, template context, the HTMX flow, and `board.html`'s form fields. |
| [strategies.md](strategies.md) | The strategy interface, `StrategyProfile` tunables, the 15 named bots, and how to add one. |
| [simulation.md](simulation.md) | `simulate.py` / `run-sim.sh`, the HTML report, and the snap-symmetry the simulator enforces. |
| [tournament.md](tournament.md) | `tournament.py` / `run-tournament.sh`, the Bradley-Terry → Elo rating, and the bot ladder. |
| [testing.md](testing.md) | Test layout, how to run pytest with coverage, and the CI workflow. |
| [reports-workflow.md](reports-workflow.md) | The `/file` skill and the `reports/` archive convention for logging experiments. |

## Suggested reading order

1. **[overview.md](overview.md)** — orient yourself.
2. **[rules.md](rules.md)** — understand the game the code implements.
3. **[architecture.md](architecture.md)** — the layering and state model everything else builds on.
4. Then dip into whichever layer you're touching: [web-app](web-app.md),
   [strategies](strategies.md), [simulation](simulation.md), or [tournament](tournament.md).

## Keeping these docs honest

Code is the ground truth. When you change behavior, update the matching doc in the
same PR. Where a doc cites a concrete value or `file:line`, it was accurate at the
time of writing — verify before relying on a line number, since they drift.
