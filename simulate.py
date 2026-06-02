#!/usr/bin/env python3
"""
Run many self-play Cambio games (a smart strategy vs a random strategy, or the
random-vs-random baseline) , stream a per-game log, and write a standalone HTML
analysis report.

Examples:
    python simulate.py                       # 500 games, greedy vs random
    python simulate.py --strategy minimalist --seed 1 -n 2000 --quiet
    python simulate.py --strategy random --seed 1 -n 1000   # random-vs-random baseline
"""

import argparse

from game import strategies
from game.strategies_advanced import ADVANCED, get_advanced
import game.strategy as random_strategy
from game.simulator import run_simulation
from game.report import write_report

# The random strategy's coded rules, surfaced in the report's strategy box when
# running the random-vs-random baseline.
_RANDOM_RULES = [
    "Draw phase: calls Cambio 8% of the time; otherwise draws from the discard pile "
    "75% of the time when its top card is worth 3 or less, else draws from the deck.",
    "Action phase: discards the drawn card 70% of the time when it is worth 10 or more "
    "(else 40%); otherwise swaps it into a random hand slot.",
    "Snaps each eligible matching card with 70% probability.",
    "Special abilities (7–K) target random valid cards.",
]


def _result_line(rec):
    scores = f"P={rec.player_score} C={rec.computer_score}"
    if rec.is_tie:
        return f"tie · {scores} · {rec.length} turns · {rec.ending}"
    strat = rec.seat_strategy[rec.winner_seat]
    return f"{rec.winner_seat} ({strat}) wins · {scores} · {rec.length} turns · {rec.ending}"


def _print_summary(stats, path):
    s = stats
    bar = "=" * 54
    print("\n" + bar)
    print(f"  Games:             {s['n']:,}")
    print(f"  Smart wins:        {s['smart_wins']:,} ({s['smart_winrate']:.1f}%)")
    print(f"  Random wins:       {s['random_wins']:,} ({s['random_winrate']:.1f}%)")
    print(f"  Ties:              {s['ties']:,} ({s['tie_rate']:.1f}%)")
    print(f"  Starter win rate:  {s['starter_winrate']:.1f}%")
    print(f"  Smart 1st / 2nd:   {s['smart_first_winrate']:.1f}% / {s['smart_second_winrate']:.1f}%")
    print(f"  Avg game length:   {s['avg_length']:.1f} turns ({s['min_length']}–{s['max_length']})")
    print(f"  Total time:        {s['timing']['total_s']:.2f}s "
          f"({s['timing']['games_per_s']:,.0f} games/s)")
    print(bar)
    print(f"  HTML report: {path}")


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Simulate many Cambio games (smart vs random) and write an HTML report.")
    p.add_argument("-n", "--games", type=int, default=500,
                   help="number of games to simulate (default: 500)")
    p.add_argument("-o", "--output", default="report.html",
                   help="path for the HTML report (default: report.html)")
    p.add_argument("--strategy", default="greedy",
                   choices=list(strategies.PROFILES) + list(ADVANCED) + ["random", "llm"],
                   help="strategy to evaluate — a named profile, an advanced "
                        "strategy, 'random' for the random-vs-random baseline, or "
                        "'llm' for the OpenRouter LLM (requires --enable-llm) "
                        "(default: greedy)")
    p.add_argument("--seed", type=int, default=None,
                   help="random seed for reproducible runs")
    p.add_argument("--quiet", action="store_true",
                   help="suppress the per-game log; show progress only")
    p.add_argument("--max-turns", type=int, default=1000,
                   help="safety cap on turns per game (default: 1000)")
    p.add_argument("--enable-llm", action="store_true",
                   help="opt in to the OpenRouter LLM strategy (slow, costs money; "
                        "needs OPENROUTER_API_KEY). Off by default.")
    p.add_argument("--llm-model", default=None,
                   help="OpenRouter model id for --strategy llm "
                        "(default: $OPENROUTER_MODEL or a cheap built-in default)")
    p.add_argument("--llm-snaps", action="store_true",
                   help="let the LLM decide snaps too (more API calls); off by "
                        "default the LLM strategy snaps with a cheap heuristic")
    args = p.parse_args(argv)

    if args.strategy == "llm" and not args.enable_llm:
        p.error("--strategy llm requires --enable-llm (and OPENROUTER_API_KEY). "
                "The LLM strategy is off by default because it is slow and costs money.")

    def on_game(g, rec):
        if args.quiet:
            if (g + 1) % 50 == 0 or (g + 1) == args.games:
                print(f"\r  played {g + 1}/{args.games} games", end="", flush=True)
            return
        print(f"\n─── Game {g + 1}/{args.games} ───  "
              f"smart={rec.smart_seat}, moves first: {rec.starting_seat}")
        for line in rec.log:
            print(f"   {line}")
        print(f"   ▶ {_result_line(rec)}")

    if args.strategy == "random":
        # Random-vs-random baseline: both seats run the random strategy. Seat A
        # ("smart") is randomized per game by run_simulation, so neither label is
        # pinned to a physical seat — hence the neutral "Random A / Random B".
        smart = random_strategy
        smart_label, opp_label = "Random A", "Random B"
        run_desc = "Random vs Random (baseline)"
        config_extra = {
            "strategy_name": "Random",
            "strategy_rules": _RANDOM_RULES,
            "label_a": smart_label,
            "label_b": opp_label,
            "a_is_random": True,
            "vs_label": "— random vs random baseline",
        }
    elif args.strategy == "llm":
        from game.strategy_llm import get_llm_strategy
        from game import llm_client
        llm_client.reset_usage()
        smart = get_llm_strategy(model=args.llm_model, llm_snaps=args.llm_snaps)
        smart_label, opp_label = "smart", "random"
        run_desc = f"{smart.name} ({llm_client.model_name()}) vs Random"
        config_extra = {
            "strategy_name": smart.name,
            "strategy_key": smart.key,
            "strategy_rules": smart.rules,
        }
        print(f"  ⚠ LLM strategy ON — model {llm_client.model_name()}. This makes a "
              f"live API call per decision: expect slow, metered runs. Keep -n small.")
    elif args.strategy in ADVANCED:
        smart = get_advanced(args.strategy)
        smart_label, opp_label = "smart", "random"
        run_desc = f"{smart.name} vs Random"
        config_extra = {
            "strategy_name": smart.name,
            "strategy_key": smart.key,
            "strategy_rules": smart.rules,
        }
    else:
        profile = strategies.PROFILES[args.strategy]
        smart = strategies.SmartStrategy(profile)
        smart_label, opp_label = "smart", "random"
        run_desc = f"{profile.name} vs Random"
        config_extra = {
            "strategy_name": profile.name,
            "strategy_key": profile.key,
            "strategy_rules": profile.rules,
        }

    seed_note = f", seed={args.seed}" if args.seed is not None else ""
    print(f"Simulating {args.games} games ({run_desc}){seed_note} …")
    records, timing = run_simulation(
        args.games, smart=smart, opponent=random_strategy,
        seed=args.seed, max_turns=args.max_turns, on_game=on_game,
        smart_label=smart_label, opponent_label=opp_label)
    if args.quiet:
        print()

    config = {"seed": args.seed, "max_turns": args.max_turns, **config_extra}
    stats = write_report(records, timing, config, args.output)
    print(f"\n  Strategy: {run_desc}")
    _print_summary(stats, args.output)

    if args.strategy == "llm":
        from game import llm_client
        print(f"\n  {llm_client.summary_line()}")
        print(f"  Heuristic fallbacks: {smart.fallback_count} "
              f"(of {smart.call_count} LLM calls)"
              + ("  ← check OPENROUTER_API_KEY / model id" if smart.fallback_count else ""))


if __name__ == "__main__":
    main()
