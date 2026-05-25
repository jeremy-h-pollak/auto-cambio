#!/usr/bin/env bash
# Run a round-robin tournament across every strategy; writes an HTML report
# (default tournament.html) with rankings + a head-to-head matrix, plus a
# console summary. All arguments are forwarded to tournament.py, e.g.:
#   ./run-tournament.sh -k 400 --seed 1 --quiet
set -euo pipefail
cd "$(dirname "$0")"
exec python tournament.py "$@"
