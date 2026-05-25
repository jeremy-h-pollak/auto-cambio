#!/usr/bin/env bash
# Run a self-play simulation; writes an HTML report (default report.html) plus a
# console summary. All arguments are forwarded to simulate.py, e.g.:
#   ./run-sim.sh --strategy greedy -n 2000 --seed 1
set -euo pipefail
cd "$(dirname "$0")"
exec python simulate.py "$@"
