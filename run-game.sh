#!/usr/bin/env bash
# Launch the Cambio web game (Flask) on http://localhost:5001.
# Same as `python app.py`; cd's to the repo root so templates/ and static/ resolve.
set -euo pipefail
cd "$(dirname "$0")"
exec python app.py
