"""Rule isolation. A teammate's bad rule must not cost us a round.

Guards, in order:
  1. hard timeout  -- a hung rule is abandoned, the round continues
  2. exception     -- any raise disables the rule for the round
  3. output range  -- out-of-range contributions are discarded, never silently
                      clamped (a silent clamp hides the bug)
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass

from c2f.core.models import Context, Verdict

RULE_TIMEOUT_S = 0.05      # pure functions have no excuse
SCALE_BOUNDS = (0.1, 10.0)

_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="rule")


@dataclass
class RuleOutcome:
    verdict: Verdict | None
    error: str | None = None
    elapsed_ms: float = 0.0

    @property
    def ok(self) -> bool:
        return self.error is None


def _validate(v: Verdict) -> Verdict:
    if v.scale is not None:
        lo, hi = SCALE_BOUNDS
        if not (lo <= v.scale <= hi):
            raise ValueError(f"scale {v.scale} outside {SCALE_BOUNDS}")
    if v.clamp is not None:
        lo, hi = v.clamp
        if not (lo >= 0 and hi > lo):
            raise ValueError(f"clamp {v.clamp} is not a valid ordered interval")
    return v


def run_rule(rule, ctx: Context) -> RuleOutcome:
    """Execute one rule under all three guards. Never raises."""
    start = time.perf_counter()
    try:
        fut = _POOL.submit(rule.apply, ctx)
        v = fut.result(timeout=RULE_TIMEOUT_S)
    except FutureTimeout:
        # The thread is abandoned, not killed. Leaking a thread is cheaper than
        # losing the round.
        return RuleOutcome(None, f"timeout after {RULE_TIMEOUT_S*1000:.0f}ms",
                           (time.perf_counter() - start) * 1000)
    except Exception as e:  # noqa: BLE001 -- untrusted code, catch everything
        return RuleOutcome(None, f"{type(e).__name__}: {e}",
                           (time.perf_counter() - start) * 1000)

    elapsed = (time.perf_counter() - start) * 1000
    if v is None:
        return RuleOutcome(None, None, elapsed)
    if not isinstance(v, Verdict):
        return RuleOutcome(None, f"returned {type(v).__name__}, expected Verdict", elapsed)
    try:
        return RuleOutcome(_validate(v), None, elapsed)
    except ValueError as e:
        return RuleOutcome(None, str(e), elapsed)
