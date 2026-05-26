# Reports & experiment workflow

Strategy tuning is empirical, so every meaningful self-play run gets **archived and
logged** rather than thrown away. This is how the project tracks "did that change
actually help?" over time.

## The `reports/` archive

```
reports/
├── INDEX.md                      # one-row-per-run log (newest at the bottom)
└── <date>-<time>-<id>/           # e.g. 2026-05-24-235734-288b/
    ├── report.html               # the archived HTML report (frozen copy of a sim run)
    └── summary.md                # objective stats + the user's interpretation
```

- Folder names are `YYYY-MM-DD-HHMMSS-<4-hex-id>` — runs are **never overwritten**;
  re-filing the same source HTML just makes another dated archive.
- The bare `report.html` / `tournament.html` at the repo root are **gitignored** — filing
  is what makes a run permanent.

### `INDEX.md`

A single table, one row per filed run:

```markdown
| ID | Date | Games | Verdict / one-line takeaway | Folder |
|----|------|-------|-----------------------------|--------|
| 288b | 2026-05-24 23:57 | 2000 | Bargain Hunter ties Minimalist (75.2%)… | [link](2026-05-24-235734-288b/) |
```

### `summary.md`

YAML frontmatter (`id`, `date`, `time`, `source`, `games`, `seed`, `filed_at`) followed by:

- **Headline stats** — objective figures lifted from the report (win rates, scores,
  Cambio-caller success, game length, snaps/game, endings).
- **Strategy under test** — the bot's rules.
- **Analysis** — observations and trend vs. the previous run (often a comparison table).
- **Findings (interview)** — Tested / Key takeaway / Surprises & concerns / Verdict.

These summaries are the project's running lab notebook — read the latest ones to see what
has and hasn't moved the needle (e.g. the recurring finding that random is too weak an
opponent to separate strong strategies, motivating the [tournament](tournament.md)).

## The `/file` skill

Filing is automated by the **`file` skill** (`.claude/skills/file/`), invoked as `/file
<path-to-report.html>` (or just `/file` and it asks for the path). Its steps:

1. **Archive** — `.claude/skills/file/scripts/file_report.sh "<path>"` copies the HTML
   into a fresh `reports/<date>-<time>-<id>/` and prints `DIR`, `ID`, `DATE`, `TIME`,
   `SOURCE`. (The id is `printf '%04x' $RANDOM` — shell built-ins only.)
2. **Analyze** — read the archived `report.html` and pull out the headline figures.
3. **Present** — give a tight readout, flagging anything notable (win rate far from 50%,
   capped games, lopsided scores, a clear move vs. the previous run).
4. **Interview** — 3–4 questions (Tested / Takeaway / Concerns / Verdict).
5. **Write** `summary.md` weaving the objective stats together with the answers.
6. **Log** a one-line row to `reports/INDEX.md`.
7. **Commit** just that report folder + `INDEX.md`
   (`git commit -m "report: file self-play run <ID> (<DATE>)"`).

So a normal optimization loop is: tweak a `StrategyProfile`
([strategies.md](strategies.md)) → `./run-sim.sh --strategy <key> --seed 1 -n 2000` →
review `report.html` → `/file report.html` to capture the verdict and check it in.

## See also

- [simulation.md](simulation.md) — producing the reports that get filed.
- [strategies.md](strategies.md) — what you're usually tuning between runs.
