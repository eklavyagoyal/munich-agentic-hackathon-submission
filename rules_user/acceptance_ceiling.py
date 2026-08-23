"""A global ceiling on the acceptance limit. Ported from Luis's pipeline, re-measured here.

His v2 runner drove fraud purchases from 32k to 14.7k to 1,054 EUR with a global
b_max plus an anchor-floor override (docs/HANDOVER.md in his repo, 23:25 UTC). We had
no equivalent: `worthless_accept_guard` caps `b` only on items the ensemble prices at
zero, which is the cheap tail. Everything above that was uncapped.

MEASURED ON OUR OWN DATA, over the 30 games our event log covers, by capping the `b`
we actually submitted and rescoring against the real transactions:

    b_max      delta        (+ anchor override, not shippable -- see below)
      200    +31,007                +55,322
      300    +23,215                +35,769
      450    +20,898                +22,668
      600    +26,712                +29,909
      900    +26,851                +34,226
     1500    +19,123                +19,951

Positive at every level across a 7.5x range, which says the MECHANISM is sound while
the exact value is not well determined -- the curve is non-monotonic, so 200 being the
argmax is probably noise. Default is therefore 450, Luis's independently-tuned value
and mid-range here, rather than our own noisy best. Override with C2F_BMAX.

WHY THIS ONE IS EXACT AND NOT AN UPPER BOUND

Every other candidate tonight foundered on the same rock: raising `b` starts paying
rejected-fraud charges whose amounts the server never revealed (1,079+ such rows), so
any gain is an upper bound. LOWERING `b` cannot do that. It only converts an
acceptance into a rejection, and both sides of that trade are visible -- a fair
charge's amount is known because rejected-yet-paid reveals it. So the figure above is
exact, in the same way `worthless_accept_guard`'s +22,715 is exact.

The cost side is real and is counted in those numbers: capping `b` turns some fair
charges we accepted (cost `a`) into rejections (cost 1.5a). At 574.60 per wrong
rejection against 202.70 per fraud purchase that trade is unfavourable per event, and
it still nets positive -- because the fraud we stop buying is far more numerous at
these amounts than the fair charges we start rejecting.

WHAT IS DELIBERATELY NOT HERE

Luis pairs the cap with an ANCHOR-FLOOR OVERRIDE: keep the original `b` when a proven
t-band puts the item above the cap. That column above is much stronger (+55,322 at 200)
and it is NOT implementable as measured, because it reads `t_lo` -- a label we only have
for games already played. Doing it live needs retrieval over proven bands from prior
games, which is his `anchors.py` and a separate piece of work. Without it this rule is
blunt: it caps expensive items too, and expensive items are exactly where wrong
rejections cost us 3,200 each. That is why the shippable number is +31,007 rather than
+55,322, and why the override is the obvious next build.

GUARD, not PRIOR: it runs after the belief is fixed and touches only the limit, via
Verdict.accept_ceiling. It never changes the charge, so the issuer side is untouched.
"""
from __future__ import annotations

import os

from c2f.core.models import Context, Stage, Verdict
from c2f.rules.protocol import BaseRule

DEFAULT_BMAX = 450.0


def bmax() -> float:
    """Read at apply() time, not import, so the value is tunable without a restart."""
    raw = os.environ.get("C2F_BMAX", "").strip()
    if not raw:
        return DEFAULT_BMAX
    try:
        v = float(raw)
    except ValueError:
        return DEFAULT_BMAX
    # A zero or negative cap would reject everything and pay 1.5a to the entire field.
    # That is the game-1 failure mode, so it is refused rather than honoured.
    return v if v > 0 else DEFAULT_BMAX


class AcceptanceCeiling(BaseRule):
    name = "acceptance_ceiling"
    stage = Stage.GUARD
    priority = 10
    author = "core"

    def apply(self, ctx: Context) -> Verdict | None:
        cap = bmax()
        # No opinion unless we would actually exceed the cap. Returning a ceiling
        # equal to or above the current limit would be a no-op that still shows up
        # in the trace as if the rule had done something.
        est = ctx.prefetch.get(ctx.item.idx)
        median = getattr(getattr(est, "belief", None), "median", None)
        if median is not None and median <= cap:
            return None
        return Verdict(
            accept_ceiling=cap,
            note=f"global acceptance ceiling {cap:.0f}",
        )


RULES = [AcceptanceCeiling()]
