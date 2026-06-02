#!/usr/bin/env python3
"""
Run a round-robin tournament across every Cambio strategy and write a standalone
HTML report (rankings + head-to-head matrix) plus a console summary.

Every pair of strategies plays K games with balanced sides; outcomes are fit to
a Bradley-Terry model on an Elo-style scale (ties = half a win, margins ignored).
Random is included as a calibration anchor unless --no-random is given.

Examples:
    python tournament.py                       # 15 profiles + random, 100 games/pairing
    python tournament.py -k 400 --seed 1 --quiet
    python tournament.py --no-random -o profiles.html
"""

import argparse

from game.tournament import entrants, run_tournament, rankings
from game.tournament_report import write_tournament_report


def _print_summary(result, path):
    rows = rankings(result)
    bar = "=" * 60
    print("\n" + bar)
    print(f"  {'#':>2}  {'Strategy':<22}{'Rating':>7}{'Win%':>8}  {'W–L–T':>16}")
    print("  " + "-" * 56)
    for r in rows:
        wlt = f"{r['wins']}–{r['losses']}–{r['ties']}"
        print(f"  {r['rank']:>2}  {r['name']:<22}{r['rating']:>7.0f}"
              f"{r['win_pct']:>7.1f}%  {wlt:>16}")
    print(bar)
    t = result.timing
    print(f"  {result.total_games:,} games over {t['pairs']} pairings "
          f"in {t['total_s']:.1f}s ({t['games_per_s']:,.0f} games/s)")
    print(f"  HTML report: {path}")


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Round-robin tournament across all Cambio strategies.")
    p.add_argument("-k", "--games", type=int, default=100,
                   help="games per pairing; a multiple of 4 balances sides exactly "
                        "(default: 100)")
    p.add_argument("-o", "--output", default="tournament.html",
                   help="path for the HTML report (default: tournament.html)")
    p.add_argument("--seed", type=int, default=None,
                   help="random seed for reproducible runs")
    p.add_argument("--no-random", action="store_true",
                   help="exclude the random baseline (profiles only)")
    p.add_argument("--max-turns", type=int, default=1000,
                   help="safety cap on turns per game (default: 1000)")
    p.add_argument("--quiet", action="store_true",
                   help="suppress per-pairing progress")
    p.add_argument("--enable-llm", action="store_true",
                   help="add the OpenRouter LLM entrant (slow, costs money; needs "
                        "OPENROUTER_API_KEY). Off by default. WARNING: it plays "
                        "every other entrant, so cost scales with -k × field size.")
    p.add_argument("--llm-model", default=None,
                   help="OpenRouter model id for the LLM entrant "
                        "(default: $OPENROUTER_MODEL or a cheap built-in default)")
    p.add_argument("--llm-snaps", action="store_true",
                   help="let the LLM decide snaps too (many more API calls)")
    args = p.parse_args(argv)

    if args.enable_llm:
        from game import llm_client
        llm_client.reset_usage()
        n_others = len(entrants(include_random=not args.no_random))
        print(f"  ⚠ LLM entrant ON — model {llm_client.model_name()}. It will play "
              f"~{n_others * args.games:,} games, each turn a live API call. "
              f"This can be slow and expensive; keep -k small (e.g. 4).")

    field_ = entrants(include_random=not args.no_random, include_llm=args.enable_llm,
                      llm_model=args.llm_model, llm_snaps=args.llm_snaps)

    def on_pair(idx, total, a, b):
        if args.quiet:
            if (idx + 1) % 10 == 0 or (idx + 1) == total:
                print(f"\r  played {idx + 1}/{total} pairings", end="", flush=True)
        else:
            print(f"  [{idx + 1:>3}/{total}] {a.name} vs {b.name}")

    seed_note = f", seed={args.seed}" if args.seed is not None else ""
    n_pairs = len(field_) * (len(field_) - 1) // 2
    print(f"Tournament: {len(field_)} entrants · {n_pairs} pairings · "
          f"{args.games} games/pairing ({n_pairs * args.games:,} games){seed_note} …")

    result = run_tournament(field_, args.games, seed=args.seed,
                            max_turns=args.max_turns, on_pair=on_pair)
    if args.quiet:
        print()

    config = {"seed": args.seed, "max_turns": args.max_turns}
    write_tournament_report(result, config, args.output)
    _print_summary(result, args.output)

    if args.enable_llm:
        from game import llm_client
        llm = next((e.strat for e in field_ if e.key == "llm"), None)
        print(f"\n  {llm_client.summary_line()}")
        if llm is not None:
            print(f"  Heuristic fallbacks: {llm.fallback_count} "
                  f"(of {llm.call_count} LLM calls)")


if __name__ == "__main__":
    main()
