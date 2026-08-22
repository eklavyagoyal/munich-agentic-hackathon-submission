"""Deterministic price book -- the emergency rung of the fallback ladder and
the baseline PRIOR until the LLM ensemble lands.

VAT IS EXPLICIT AND SEPARATE. Submissions must be the GROSS TOTAL for the whole
line item (GAME_DESCRIPTION), never net and never per-unit. Getting this wrong
is a flat 19% systematic error -- larger than the entire margin between our `a`
and our `b`, so it is handled in exactly one place and asserted at the boundary.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from c2f.core.models import Belief, Context, LineItem

VAT_RATE = 0.19


@dataclass(frozen=True)
class Rate:
    trade: str
    unit: str
    low: float       # net EUR per unit
    high: float
    keywords: tuple[str, ...]


# Net German trade rates. Keywords cover DE and EN -- the sample invoice is
# English but the policy text may not be.
RATES: tuple[Rate, ...] = (
    Rate("flooring", "m2", 8, 18, ("laminat entfern", "remove laminate", "ausbau laminat",
                                   "demontage bodenbelag", "remove water-damaged laminate")),
    Rate("flooring", "m2", 25, 45, ("laminat verleg", "laminat neu", "install laminate",
                                    "new installation of laminate", "bodenbelag verleg")),
    Rate("flooring", "lm", 8, 18, ("sockelleiste", "skirting", "fussleiste", "fußleiste")),
    Rate("drying",   "stk", 60, 180, ("trocknung", "drying", "bautrockner", "dehumidif")),
    Rate("painting", "m2", 8, 20, ("malerarbeit", "streichen", "paint", "anstrich")),
    Rate("plumbing", "h", 60, 110, ("sanitaer", "sanitär", "klempner", "plumb", "rohr")),
    Rate("electric", "h", 65, 120, ("elektro", "electric")),
    Rate("generic",  "h", 45, 95, ("stunde", "hour", "arbeitszeit", "labour", "labor")),
)

GENERIC = Rate("unknown", "", 20, 120, ())


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().strip())


def match_rate(item: LineItem) -> Rate:
    text = _norm(item.description)
    best: tuple[int, Rate] | None = None
    for rate in RATES:
        for kw in rate.keywords:
            if kw in text and (best is None or len(kw) > best[0]):
                best = (len(kw), rate)
    return best[1] if best else GENERIC


def gross(net: float) -> float:
    return net * (1.0 + VAT_RATE)


def lookup(item: LineItem) -> Belief:
    """Gross-total belief for one line item."""
    rate = match_rate(item)
    qty = max(item.qty, 0.0)
    lo, hi = gross(rate.low * qty), gross(rate.high * qty)
    if lo <= 0 or hi <= lo:
        return Belief(median=max(gross(GENERIC.low * max(qty, 1.0)), 1.0),
                      sigma=0.6, source="pricebook:degenerate")
    median = math.sqrt(lo * hi)
    # Treat [lo, hi] as a ~90% interval: +/-1.645 sigma in log space.
    sigma = min(max((math.log(hi) - math.log(lo)) / (2 * 1.645), 0.12), 1.0)
    return Belief(median=median, sigma=sigma, source=f"pricebook:{rate.trade}")


def fallback(ctx: Context) -> Belief:
    return lookup(ctx.item)
