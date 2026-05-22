---
name: file
description: Archive a Cambio self-play HTML report into reports/<date>-<time>-<id>/, analyze its headline stats, interview the user about their findings, write a summary.md alongside it, and commit it. Use when the user runs /file with a report path, or asks to file / archive / log / check in a self-play report.
---

# file

Archive a self-play HTML report (the kind `simulate.py` produces — see
`game/report.py`), capture the user's read of it, and check the whole thing into
the repo so every run is tracked over time.

The skill argument is a path to the report HTML file (local path; `file://` and
`http(s)://` also work). If the argument is missing, ask the user for the path.

## Steps

### 1. Archive
Run the helper from the repo/worktree root:

```bash
.claude/skills/file/scripts/file_report.sh "<path>"
```

It creates `reports/<date>-<time>-<id>/report.html` and prints `DIR`, `ID`,
`DATE`, `TIME`, `SOURCE`. Capture those values — every later step needs them. If
it errors (file not found / download failed), surface the message and stop.

### 2. Analyze
`Read` `<DIR>/report.html` and pull out the headline figures already written into
the report's text (the stat cards and `<p class="note">` lines):

- games count, seed, total runtime / speed
- starting-player win rate and the Player / Computer / Tie split
- mean game length (and median / min / max)
- mean final scores (player, computer) and mean win margin
- Cambio call rate and the caller win rate
- endings breakdown: cambio / empty_hand / aborted
- special abilities per game (peek own, peek opp, blind switch, looking switch)
- mean snaps per game, and deck-vs-discard draw split

If `reports/INDEX.md` already lists prior runs, glance at the most recent one and
note any notable shift.

### 3. Present
Give the user a tight readout of those numbers. Call out anything notable: a win
rate far from 50%, any aborted games (hit the turn cap), lopsided scores, or a
clear move vs. the previous run.

### 4. Interview
Use `AskUserQuestion` to capture the user's read of the report — 3–4 questions,
anchored to the dimensions below, with extra options chosen dynamically from what
step 2/3 surfaced. Keep options concrete; the user can always free-type.

- **Tested** — what prompted this run / what change or strategy was being tested?
- **Takeaway** — the key thing they take away from reviewing the report.
- **Concerns** — anything that looks wrong, surprising, or worth investigating.
- **Verdict** — next step: keep the change, revert, tune a param, run more games, etc.

### 5. Write the summary
Write `<DIR>/summary.md`, weaving the objective stats (step 2) together with the
user's answers (step 4):

```markdown
---
id: <ID>
date: <DATE>
time: <TIME>
source: <SOURCE>
games: <n>
seed: <seed or "random">
filed_at: <DATE> <HH:MM>
---

# Self-play report <ID>

## Headline stats
- <objective figures from step 2>

## Analysis
- <your observations / anomalies / trend vs. previous run>

## Findings (interview)
- **Tested:** …
- **Key takeaway:** …
- **Surprises / concerns:** …
- **Verdict / next step:** …
```

### 6. Log to INDEX
If `reports/INDEX.md` does not exist, create it with this header:

```markdown
# Self-play report log

| ID | Date | Games | Verdict / one-line takeaway | Folder |
|----|------|-------|-----------------------------|--------|
```

Then append one row for this run (newest at the bottom), e.g.:

```markdown
| <ID> | <DATE> <HH:MM> | <n> | <one-line verdict> | [link](<date>-<time>-<id>/) |
```

The folder link is relative to `reports/` (just the folder name, no `reports/` prefix).

### 7. Commit
Stage and commit just this report:

```bash
git add "<DIR>" reports/INDEX.md
git commit -m "report: file self-play run <ID> (<DATE>)"
```

Report the commit and the folder path back to the user.

## Notes
- Each run gets a fresh `<date>-<time>-<id>/` folder, so reports are never
  overwritten — re-filing the same source HTML just makes another dated archive.
- The helper uses only shell built-ins for the id (`printf '%04x' $RANDOM`), so no
  extra tools are invoked.
