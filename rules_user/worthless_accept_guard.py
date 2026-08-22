"""Charge on a worthless line item, but accept nothing on it.

The two sides of a worthless item want opposite things, and until now our code
could not say so. Charging high earns real money even when the item is worth
nothing: roughly half the field accepts our over-charge, and 13,005.30 of our
income across games 1-7 came from charges proven fraudulent. Accepting on the same
item only buys their fraud back.

Measured oracle over games 1-15, from the transactions: 60 line items with a proven
ceiling under 100 and no fair charge ever observed. We bought 14,575.16 of fraud on
them, and earned 10,099.70 from them. Keeping the charge and zeroing the limit is
worth +14,575.16. Zeroing both -- the coverage verdict this replaces -- is worth
only +4,475.46, because it forfeits that income.

The figure is EXACT rather than an upper bound, which is rare here. Lowering b can
only turn an acceptance into a rejection, so it never runs into the 423 rejected-
fraud charges whose amounts are invisible (see tools/score.py).

THE SIGNAL

The LLM ensemble prices an item it believes worthless at zero. That used to be
discarded as a failed sample; it is now counted as `worthless_votes`. On game 8 it
separated the two groups cleanly: the four items priced at zero had proven
thresholds t < 84.33, t < 1.00, t < 1.00 and t < 1.00, while the four it priced were
all t >= 400.

Requires a MAJORITY of samples to say zero, so one erratic sample cannot zero a
limit on its own.

WHY GUARD AND NOT COVERAGE

A COVERAGE verdict short-circuits the engine to a=b=0 and forfeits the charge --
measured at -3,182.79 even on items proven worthless. GUARD runs after the belief
is fixed and can cap the limit alone, via Verdict.accept_ceiling.

SHADOW until tools/score.py says otherwise. The risk if the detector is wrong is
bounded but real: a covered item wrongly zeroed makes us reject every fair charge
on it and pay 1.5a on each, which is the game-1 failure mode in miniature.
"""
from __future__ import annotations

from c2f.core.models import Context, Stage, Verdict
from c2f.rules.protocol import BaseRule


class WorthlessAcceptGuard(BaseRule):
    name = "worthless_accept_guard"
    stage = Stage.GUARD
    priority = 0
    author = "core"

    def apply(self, ctx: Context) -> Verdict | None:
        est = ctx.prefetch.get(ctx.item.idx)
        if est is None:
            return None
        votes = getattr(est, "worthless_votes", 0)
        samples = getattr(est, "samples", 0)
        if not votes or votes * 2 <= samples:
            return None      # no opinion, or not a majority
        return Verdict(
            accept_ceiling=0.0,
            note=(f"{votes}/{samples} samples priced this at zero; charging anyway, "
                  "accepting nothing"),
        )


RULES = [WorthlessAcceptGuard()]
