"""A row we could not read is not a cheap row.

When the regex fails on a line item, parse.py fills the gap with a placeholder so
the round still submits a number for every printed position -- omitting it would
score charge 0 / limit 0, which rejects every fair claim AND pays 1.5a on each.
That floor is what saved games 4 and 5 from game 1's fate.

But the placeholder carries `qty=1, unit="pauschal"`, and the price book prices
that at the cheapest band it has: median 50.49, so a = 38.30. That is an assertion
that an unreadable row is worth almost nothing, and the evidence says otherwise.
Game 5 item 15 was a placeholder; its threshold is proven `t >= 300.00`
(tools/thresholds.py --game 5). We charged 38.30. A fair charge is paid by all 16
opponents, so that single row left roughly 4,187 EUR on the table.

The honest prior for "a line on this invoice that we could not read" is the other
lines on the same invoice. A surge claim's unreadable row is probably worth about
what its readable rows are worth; a small plumbing job's is not. So this takes the
geometric median of the sibling items' own book beliefs -- geometric because the
beliefs are lognormal and the decision layer consumes log-space.

Sigma is widened, not inherited. We know less about this row than about any
sibling, and the decision layer prices uncertainty: a wider sigma pulls b (the
1/3-quantile) down relative to the median while leaving a near the Mills optimum.
That is the correct shape for "probably worth something, but we genuinely cannot
read it" -- charge for it, stay cautious about accepting it.

Abstains when there is no sibling to learn from, which falls through to the price
book exactly as before.
"""
from __future__ import annotations

import math

from c2f.core.models import Belief, Context, Stage, Verdict
from c2f.estimate.pricebook import lookup
from c2f.rules.protocol import BaseRule

# parse.py writes exactly this description for a row it could not read.
PLACEHOLDER = "(row not parsed)"

# Floor on the widened sigma. The sibling spread understates our ignorance about a
# row nobody could read, so we never end up more confident than this.
MIN_SIGMA = 0.85


class UnparsedRowPrior(BaseRule):
    name = "unparsed_row_prior"
    stage = Stage.PRIOR
    # Above pricebook_prior (10): for this one description the siblings are a
    # better prior than the cheapest band in the book.
    priority = 15
    author = "core"

    def apply(self, ctx: Context) -> Verdict | None:
        if ctx.item.description != PLACEHOLDER:
            return None

        medians = []
        for sib in ctx.case.items:
            if sib.idx == ctx.item.idx or sib.description == PLACEHOLDER:
                continue
            belief = lookup(sib)
            if belief is not None and belief.median > 0:
                medians.append(belief.median)
        if not medians:
            return None      # nothing to learn from; the book keeps it

        log_median = sum(math.log(m) for m in medians) / len(medians)
        median = math.exp(log_median)

        # Spread of the siblings in log space, floored: our uncertainty about an
        # unreadable row is at least as large as the invoice's own variation.
        if len(medians) > 1:
            var = sum((math.log(m) - log_median) ** 2 for m in medians) / (len(medians) - 1)
            sigma = max(math.sqrt(var), MIN_SIGMA)
        else:
            sigma = MIN_SIGMA

        return Verdict(
            belief=Belief(median=median, sigma=min(sigma, 1.5),
                          source="siblings:unparsed_row"),
            note=(f"unreadable row priced from {len(medians)} sibling item(s), "
                  f"geometric median {median:.2f}, sigma {min(sigma, 1.5):.2f}"),
        )


RULES = [UnparsedRowPrior()]
