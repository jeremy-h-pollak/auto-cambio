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

from game.tournament import entrants, run_tournament, rankings, bootstrap_ratings
from game.tournament_report import write_tournament_report


def _print_summary(result, path, cis=None):
    rows = rankings(result)
    has_ci = cis is not None
    width = 78 if has_ci else 60
    bar = "=" * width
    print("\n" + bar)
    header = f"  {'#':>2}  {'Strategy':<22}{'Rating':>7}{'Win%':>8}  {'W–L–T':>16}"
    if has_ci:
        header += f"  {'95% CI':>16}"
    print(header)
    print("  " + "-" * (width - 4))
    for r in rows:
        wlt = f"{r['wins']}–{r['losses']}–{r['ties']}"
        line = (f"  {r['rank']:>2}  {r['name']:<22}{r['rating']:>7.0f}"
                f"{r['win_pct']:>7.1f}%  {wlt:>16}")
        if has_ci:
            c = cis[r["index"]]
            band = f"[{c['lo']:.0f}, {c['hi']:.0f}]"
            line += f"  {band:>16}"
        print(line)
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
    p.add_argument("--strategies", default=None,
                   help="comma-separated entrant keys to use as the field instead "
                        "of all of them (e.g. 'cartographer,greedy,random'). Keys "
                        "are profile/advanced names or 'random'.")
    p.add_argument("--max-turns", type=int, default=1000,
                   help="safety cap on turns per game (default: 1000)")
    p.add_argument("--bootstrap", type=int, default=0, metavar="N",
                   help="add bootstrap confidence intervals to every rating using N "
                        "resampled replicates (e.g. 2000); 0 = off (default). Fast — "
                        "it resamples recorded outcomes, it does not replay games.")
    p.add_argument("--ci-level", type=float, default=0.95,
                   help="confidence level for --bootstrap intervals (default: 0.95)")
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
    p.add_argument("--enable-kimi", action="store_true",
                   help="add Kimi K2 as a named LLM entrant (slow, costs money; needs "
                        "OPENROUTER_API_KEY). Model overridable via CAMBIO_KIMI_MODEL.")
    p.add_argument("--enable-haiku", action="store_true",
                   help="add Claude Haiku as a named LLM entrant (slow, costs money; needs "
                        "OPENROUTER_API_KEY). Model overridable via CAMBIO_HAIKU_MODEL.")
    args = p.parse_args(argv)

    keys = ([s.strip() for s in args.strategies.split(",") if s.strip()]
            if args.strategies else None)

    llm_keys = ([k for k, on in (("kimi", args.enable_kimi),
                                 ("haiku", args.enable_haiku)) if on])
    any_llm = args.enable_llm or bool(llm_keys)

    if any_llm:
        from game import llm_client
        from game.llm_opponents import llm_model as named_model
        llm_client.reset_usage()
        n_others = len(entrants(include_random=not args.no_random, keys=keys))
        models = []
        if args.enable_llm:
            models.append(llm_client.model_name())
        models += [named_model(k) for k in llm_keys]
        print(f"  ⚠ LLM entrants ON — {', '.join(models)}. Each plays "
              f"~{n_others * args.games:,} games, every turn a live API call. "
              f"This can be slow and expensive; keep -k small (e.g. 4).")

    field_ = entrants(include_random=not args.no_random, include_llm=args.enable_llm,
                      llm_model=args.llm_model, llm_snaps=args.llm_snaps,
                      llm_keys=llm_keys, keys=keys)

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

    cis = None
    if args.bootstrap > 0:
        print(f"  bootstrapping {args.bootstrap:,} replicates "
              f"for {args.ci_level:.0%} intervals …")
        cis = bootstrap_ratings(result, n_boot=args.bootstrap,
                                ci=args.ci_level, seed=args.seed)

    config = {"seed": args.seed, "max_turns": args.max_turns,
              "ci_level": args.ci_level}
    write_tournament_report(result, config, args.output, cis=cis)
    _print_summary(result, args.output, cis=cis)

    if any_llm:
        from game import llm_client
        from game.llm_opponents import NAMED_LLM_OPPONENTS
        print(f"\n  {llm_client.summary_line()}")
        for line in llm_client.summary_by_model():
            print(f"    {line}")
        for e in field_:
            if e.key == "llm" or e.key in NAMED_LLM_OPPONENTS:
                print(f"  {e.name}: heuristic fallbacks {e.strat.fallback_count} "
                      f"(of {e.strat.call_count} LLM calls)")


if __name__ == "__main__":
    main()
