"""When the price book matched NOTHING, stop rejecting confidently.

THE FAILURE THIS FIXES, observed live. Round 53, item 1: the book matched no rate and
returned median 291.49 with sigma 0.966 -- the book's way of saying it has no idea. We
set `b` to the median quantile anyway, and twelve opponents charged 2,945 to 8,626,
every one of them FAIR. We rejected all twelve and paid 1.5x on each: 84,404 EUR from a
single line item, in a round that scored -81,576.

THE MEASUREMENT, over the 30 games our event log covers. Grouping every reviewer
decision by the source of the belief behind it:

  source                     wrong-rejections  their cost   fraud bought  its cost
  UNKNOWN (no rate matched)               472     394,433            482    61,072
  matched rate                            242      85,423            181    62,805
  generic                                  21      15,293             34    14,252

237 of 338 items -- 70% -- get no matched rate, and they carry 80% of all our
wrong-rejection cost. On them, wrong rejections cost 394,433 against 61,072 of fraud
bought: a 6.5:1 ratio against us. On matched-rate items the same ratio is 1.4:1. The
problem is specific to items we could not price at all.

WHY THE DETECTOR IS FREE, which is what makes this different from five dead candidates

Every previous attempt needed to PREDICT something -- which items are expensive, which
are worthless, which descriptions match the damage. Each died on detector precision: a
+14,575 oracle measured -75.00, a ~63,000 oracle delivered +2,539, and an
expensive-item mask scored 0.000 precision on a fresh window.

This needs no prediction. The book either matched a rate or it did not, and it already
records which in the belief `source`. Precision is 1.0 by construction.

WHY RAISING b IS THE RIGHT DIRECTION HERE, despite the standing rule against it

Raising `b` is normally maximin-negative: 1,196 rejected-fraud charges record amount 0,
so their size is invisible and any gain is an upper bound. That argument still applies
-- this rule IS a b-raise, so its measurement MUST report the `unpriced` count.

What differs is the ratio. A wrong rejection costs 1.5a where accepting the same fair
charge costs a, so the avoidable excess is a third of 394,433 = 131,478. Against that we
start buying some of the fraud we currently reject for free. The observed 6.5:1 ratio is
a reason to expect that trade to pay, not proof that it does. tools/bench_all.py decides,
and the sweep over the multiple below is part of the answer.

THE FLOOR IS NOT AN ESTIMATE OF THE PRICE. It is a statement that we are not entitled
to reject. It is deliberately generous rather than accurate, because on these items we
have no basis for accuracy -- and the payoff punishes false confidence asymmetrically:
undershooting `t` as an issuer costs the shortfall, while rejecting a fair charge as a
reviewer costs 1.5x for nothing.

Applied BEFORE accept_ceiling, so worthless_accept_guard (precision 0.91, +22,715 exact)
still wins on items it recognises. Ignorance must never override knowledge.

SHADOW until measured.
"""
from __future__ import annotations

import os

from c2f.core.models import Context, Stage, Verdict
from c2f.estimate.pricebook import lookup
from c2f.rules.protocol import BaseRule

# Multiple of the belief median. 1.0 would merely undo the quantile shading; the point
# is to be generous where we are blind. Swept in the measurement.
DEFAULT_MULTIPLE = 6.0


def multiple() -> float:
    raw = os.environ.get("C2F_UNKNOWN_FLOOR_X", "").strip()
    if not raw:
        return DEFAULT_MULTIPLE
    try:
        v = float(raw)
    except ValueError:
        return DEFAULT_MULTIPLE
    return v if v > 0 else DEFAULT_MULTIPLE


class UnknownItemFloor(BaseRule):
    name = "unknown_item_floor"
    stage = Stage.GUARD
    priority = 30          # after the precise guards; the ceiling still overrides
    author = "core"

    def apply(self, ctx: Context) -> Verdict | None:
        # Ask the PRICE BOOK directly whether it recognised this item. An earlier
        # version read ctx.prefetch, which holds the LLM's estimates -- with llm_prior
        # shadow that dict is empty, so the rule silently never fired and swept
        # identically at every multiple from 2x to 60x. The book's own verdict is the
        # signal, and it is available with no model and no network.
        try:
            book = lookup(ctx.item)
        except Exception:                                    # noqa: BLE001
            return None
        source = (book.source or "").lower()
        if "unknown" not in source:
            return None            # the book had an opinion; leave it alone
        if book.median <= 0:
            return None
        floor = book.median * multiple()
        return Verdict(
            accept_floor=floor,
            note=f"no rate matched ({book.source}); refusing to reject below {floor:.0f}",
        )


RULES = [UnknownItemFloor()]


def demo() -> None:
    """Self-check against the exact round-53 numbers that motivated this."""
    from c2f.core.models import Belief
    from c2f.decision.quantile import decide

    b = Belief(median=291.49, sigma=0.966, source="pricebook:unknown:stk")
    a0, b0 = decide(b, True, None)
    a1, b1 = decide(b, True, None, accept_floor=291.49 * DEFAULT_MULTIPLE)

    assert abs(a0 - a1) < 1e-9, "the floor must never move the charge"
    assert b1 > b0, "the floor must raise the limit"
    # The twelve fair charges we rejected in round 53 ran 2,945 to 8,626.
    assert b1 >= 1748.0, b1

    # A precise ceiling must still beat a floor set out of ignorance.
    _, b2 = decide(b, True, None, accept_ceiling=0.0,
                   accept_floor=291.49 * DEFAULT_MULTIPLE)
    assert b2 == 0.0, ("worthless_accept_guard must override the floor", b2)

    print("demo ok")


if __name__ == "__main__":
    demo()
