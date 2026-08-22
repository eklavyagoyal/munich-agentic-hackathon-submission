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

# Raised from 1/3 to 1/2. Annie's PR #1 spotted the asymmetry: our empirical
# wrongful-reject to wrong-accept ratio ran far above the 2:1 the payoff matrix
# implies, which means b was too low -- not because the 2/3 rule is wrong, but
# because it is optimal only for a CALIBRATED belief and ours is systematically low
# on the items that matter.
#
# Her value was 3/4. Measured, that overshoots: the upper bound is +38,567 but 143
# invisible-amount fraud rows flip to accepted, and the worst case across a plausible
# range for their size is -26,590. At 1/2 the upper bound is +22,792, only 43 rows
# flip, and the worst case stays POSITIVE at +2,616 even assuming those charges run
# 3x the mean of the fraud we can observe. See docs/CLAIM_PIPELINE_PLAN.md 4.6.
#
# This is the first b-raising change with a provably positive worst case; every
# earlier one was an upper bound with an unbounded downside.
ACCEPT_QUANTILE = 1.0 / 2.0


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


def _z_cap() -> float:
    """Freeze the shading exponent at its sigma=0.5 value. See charge()."""
    return optimal_charge_z(0.5)


def charge(belief: Belief) -> float:
    """The Mills optimum, but the exponent never rises above its sigma=0.5 value.

    `a * P(a <= t)` is a SMOOTH objective; the real payoff is a CLIFF at t. Past
    sigma ~0.52 the unconstrained optimum notices that a lognormal has unbounded
    upper tail and starts betting on it: at sigma=1.0 it wants 1.35x our own median
    with only a 38% chance of being fair, 2.0x at sigma=1.2, and 23x at sigma=2.0
    (which Belief permits). Beyond t
    we are paid only by opponents who wrongly accept, so that bet earns ~nothing
    while forfeiting the income a fair charge collects from *everyone*.

    Capping at the sigma=0.5 exponent leaves every tested sigma <= 0.5 bit-identical
    (the Mills z is still the binding one there) and makes the charge decay as the
    estimate degrades: 0.77x median at sigma=0.5, 0.66x at 0.8, 0.54x at 1.2.

    This also restores `charge < accept_limit` structurally, because the capped
    exponent (-0.518) is below the 1/3-quantile exponent (-0.431). Previously that
    invariant was only rescued after the fact by decide()'s repair clause, which
    hid the tail-betting instead of preventing it.
    """
    z = min(optimal_charge_z(belief.sigma), _z_cap())
    return belief.median * math.exp(z * belief.sigma)


def accept_limit(belief: Belief) -> float:
    return belief.quantile(ACCEPT_QUANTILE)


def decide(
    belief: Belief | None,
    covered: bool,
    clamp: tuple[float, float] | None = None,
    vetoed: bool = False,
    accept_ceiling: float | None = None,
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

    if accept_ceiling is not None:
        # Deliberate asymmetry: cap the limit and LEAVE THE CHARGE ALONE. Applied
        # after the clamp so a guard ceiling still binds, and it returns before the
        # repair below -- collapsing the pair is the intent here, not an accident.
        return a, min(b, max(accept_ceiling, 0.0))

    if b <= a:
        # Clamping can collapse the pair. Repair by LOWERING the charge, never
        # by raising the limit: pushing b above a guard ceiling accepts more
        # than the guard allows, which is the exploitable direction. Lowering
        # `a` only costs us revenue.
        a = max(b * 0.999 - 0.01, 0.0)
    return a, b
