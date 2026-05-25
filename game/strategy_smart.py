"""
Default "smart" computer strategy — the Greedy Minimizer profile.

Thin module-level facade over `strategies.SmartStrategy` so the engine and web
app can keep importing this as a module (`choose_move`, `should_snap`,
`apply_computer_special`). For the simulator and strategy comparisons, build a
`SmartStrategy` from any profile in `strategies.PROFILES`.
"""

from .strategies import get

_baseline = get("greedy")

choose_move = _baseline.choose_move
should_snap = _baseline.should_snap
apply_special = _baseline.apply_special
apply_computer_special = _baseline.apply_computer_special

SMART_AI_DESCRIPTION = _baseline.profile.rules
