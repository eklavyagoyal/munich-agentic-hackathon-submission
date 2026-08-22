"""Turning a belief about `t` into (a, b). Derived in ARCHITECTURE.md §1.

Insurer:  accept iff P(a <= t) > 2/3  =>  b = the 1/3-quantile of the belief.
          Wrongly accepting fraud costs the full `a`; wrongly rejecting a fair
          claim costs only the extra 0.5a. Fraud is exactly 2x worse.

Issuer:   in the fair zone the issuer is paid `a` whether or not the opponent
          accepts, and overcharging carries no penalty. So maximise
          a * P(a <= t), giving h(z*) = sigma with h = phi/(1-Phi).
"""
from __future__ import annotations

import math
from functools import lru_cache
from statistics import NormalDist

from c2f.core.models import Belief

_N = NormalDist()

ACCEPT_QUANTILE = 1.0 / 3.0   # the 2/3 rule, not a tuning knob


def _hazard(z: float) -> float:
    return _N.pdf(z) / (1.0 - _N.cdf(z))


@lru_cache(maxsize=256)
def optimal_charge_z(sigma: float) -> float:
    """Solve h(z) = sigma by bisection. h is strictly increasing in z."""
    lo, hi = -8.0, 8.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if _hazard(mid) < sigma:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def charge(belief: Belief) -> float:
    return belief.median * math.exp(optimal_charge_z(belief.sigma) * belief.sigma)


def accept_limit(belief: Belief) -> float:
    return belief.quantile(ACCEPT_QUANTILE)


def decide(
    belief: Belief | None,
    covered: bool,
    clamp: tuple[float, float] | None = None,
    vetoed: bool = False,
) -> tuple[float, float]:
    """Final (a, b). Never returns b=0 on a covered item."""
    if not covered:
        return 0.0, 0.0
    if belief is None:
        raise ValueError("covered item without a belief -- caller must supply a fallback")

    if vetoed:
        # We do not trust our own estimate enough to charge on it, but an
        # anchored limit is still far better than b=0 (which pays 1.5a to
        # everyone) or a generous b (exploitable up to the cap c >= 4t).
        a, b = 0.0, belief.median
    else:
        a, b = charge(belief), accept_limit(belief)

    if clamp is not None:
        lo, hi = clamp
        a = min(max(a, lo if a > 0 else 0.0), hi)
        b = min(max(b, lo), hi)

    if b <= a:
        # Clamping can collapse the pair. Repair by LOWERING the charge, never
        # by raising the limit: pushing b above a guard ceiling accepts more
        # than the guard allows, which is the exploitable direction. Lowering
        # `a` only costs us revenue.
        a = max(b * 0.999 - 0.01, 0.0)
    return a, b
