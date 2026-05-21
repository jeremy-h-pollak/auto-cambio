#!/usr/bin/env python3
"""
Run many self-play Cambio games (the smart strategy vs a random strategy),
stream a per-game log, and write a standalone HTML analysis report.

Examples:
    python simulate.py                 # 500 games -> report.html
    python simulate.py -n 1000 --seed 1
    python simulate.py -n 5000 --quiet -o out.html
"""

import argparse

from game import strategies
import game.strategy as random_strategy
from game.simulator import run_simulation
from game.report import write_report


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
    p.add_argument("--strategy", default="greedy", choices=list(strategies.PROFILES),
                   help="which smart-strategy profile to evaluate (default: greedy)")
    p.add_argument("--seed", type=int, default=None,
                   help="random seed for reproducible runs")
    p.add_argument("--quiet", action="store_true",
                   help="suppress the per-game log; show progress only")
    p.add_argument("--max-turns", type=int, default=1000,
                   help="safety cap on turns per game (default: 1000)")
    args = p.parse_args(argv)

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

    profile = strategies.PROFILES[args.strategy]
    smart = strategies.SmartStrategy(profile)

    seed_note = f", seed={args.seed}" if args.seed is not None else ""
    print(f"Simulating {args.games} games ({profile.name} vs Random){seed_note} …")
    records, timing = run_simulation(
        args.games, smart=smart, opponent=random_strategy,
        seed=args.seed, max_turns=args.max_turns, on_game=on_game)
    if args.quiet:
        print()

    config = {
        "seed": args.seed,
        "max_turns": args.max_turns,
        "strategy_name": profile.name,
        "strategy_key": profile.key,
        "strategy_rules": profile.rules,
    }
    stats = write_report(records, timing, config, args.output)
    print(f"\n  Strategy: {profile.name} ({profile.key})")
    _print_summary(stats, args.output)


if __name__ == "__main__":
    main()
