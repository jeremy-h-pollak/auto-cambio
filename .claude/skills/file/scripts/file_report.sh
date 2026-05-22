#!/usr/bin/env bash
#
# file_report.sh <report-path>
#
# Archive a Cambio self-play HTML report into reports/<date>-<time>-<id>/report.html
# and print machine-readable metadata for the /file skill to consume.
#
# Primary input is a local file path. file:// is accepted (prefix stripped) and
# http(s):// URLs are fetched with curl as a bonus. Run from the repo/worktree root
# so that reports/ resolves to the repo root on the current branch.

set -euo pipefail

if [ "$#" -ne 1 ] || [ -z "${1:-}" ]; then
  echo "usage: file_report.sh <report-path>" >&2
  exit 2
fi

input="$1"

# Unique identifiers — built-ins only, no external tools (avoids permission prompts).
date="$(date +%F)"        # YYYY-MM-DD
time="$(date +%H%M%S)"    # HHMMSS
id="$(printf '%04x' "$RANDOM")"

dir="reports/${date}-${time}-${id}"
mkdir -p "$dir"
dest="$dir/report.html"

case "$input" in
  http://*|https://*)
    source="$input"
    if ! curl -fsSL "$input" -o "$dest"; then
      echo "error: failed to download report from $input" >&2
      rmdir "$dir" 2>/dev/null || true
      exit 1
    fi
    ;;
  *)
    # Strip a leading file:// if present, then treat as a local path.
    path="${input#file://}"
    if [ ! -f "$path" ]; then
      echo "error: report file not found: $path" >&2
      rmdir "$dir" 2>/dev/null || true
      exit 1
    fi
    # Absolute path for the metadata record.
    source="$(cd "$(dirname "$path")" && pwd)/$(basename "$path")"
    cp "$path" "$dest"
    ;;
esac

# Machine-readable metadata for the skill.
echo "DIR=$dir"
echo "ID=$id"
echo "DATE=$date"
echo "TIME=$time"
echo "SOURCE=$source"
