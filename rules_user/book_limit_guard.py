"""Take the CHARGE from the model and the LIMIT from the price book.

The two halves of our decision want different estimators, and the evidence for that is
now replicated from two independent runs.

THE ISSUER SIDE: the model wins, consistently. Across five historical draws and three
fresh ones -- eight of eight -- the invoice-level LLM valuation beat the price book on
issuer SCORE. That is not a single lucky run; run-to-run variance moved the magnitude
(0.317 to 0.428) but never the sign.

THE REVIEWER SIDE: the model loses, and we know exactly how. Of the ~116 items where
promoting llm_prior raised `b`, three reproductions put 73.7-76.8% of those raises BELOW
t_lo 400 -- the region where raising the acceptance limit is maximin-NEGATIVE. Bucketed
by proven floor, raising `b` only pays above t_lo 1200 (+63,122 even at 4x the observed
fraud mean); it breaks even around 2.1x in 400-1200 and is strongly negative below,
where 1,003 invisible rejected-fraud rows sit. The model raises `b` overwhelmingly in
the losing zone.

That explains a result that was otherwise puzzling: promoting llm_prior whole measured
only +2,539 over 18 games. The issuer gain was real and it was being cancelled by
reviewer-side losses. Separating them keeps one and drops the other.

WHY A CEILING IS EXACTLY THE RIGHT SHAPE, and not merely convenient

Verdict.accept_ceiling takes a MINIMUM against the limit the prior produced. So this
rule blocks the model from raising `b` above the book's value, while still allowing it
to LOWER `b` below it. That asymmetry is precisely what the measurements ask for:

  - a model b-RAISE is harmful (74-77% of them land in the maximin-negative zone)
  - a model b-LOWERING is safe by construction -- lowering `b` can only convert an
    acceptance into a rejection, so it never starts paying an invisible rejected-fraud
    charge. This is the same argument that makes worthless_accept_guard's +22,715 exact
    rather than an upper bound.

So the ceiling is not a blunt clamp. It filters by direction, keeping the model's
judgement where that judgement is provably safe.

WHAT THIS IS NOT

Not the global b_max ceiling. That one capped every limit at a constant and measured
-47,013: redundant with worthless_accept_guard on the cheap end, and actively harmful
above it because a wrong rejection on an expensive item costs ~3,200. This rule caps at
the BOOK's per-item limit, which is value-aware, rather than at a constant.

It also does not touch the charge. The whole point is that the charge keeps coming from
whichever prior is active.

DEPENDS ON A PRIOR THAT IS NOT THE BOOK. With pricebook_prior active this rule is
almost a no-op -- it would cap the book's limit at the book's own limit. It only earns
anything alongside an active llm_prior, so promote the pair or neither.

SHADOW until tools/bench_all.py says otherwise.
"""
from __future__ import annotations

from c2f.core.models import Context, Stage, Verdict
from c2f.decision.quantile import accept_limit
from c2f.estimate.pricebook import lookup
from c2f.rules.protocol import BaseRule


class BookLimitGuard(BaseRule):
    name = "book_limit_guard"
    stage = Stage.GUARD
    priority = 20          # after worthless_accept_guard, which is stricter still
    author = "core"

    def apply(self, ctx: Context) -> Verdict | None:
        # The book's own limit for this item, computed independently of whatever the
        # active prior believed. lookup() is a pure table read: no network, no model,
        # microseconds, so this is safe on the tier-1 path.
        try:
            book = lookup(ctx.item)
        except Exception:                                    # noqa: BLE001
            # Never take a round down over a guard. run_rule would contain a raise and
            # disable this rule for the round, but abstaining is cheaper and quieter.
            return None
        ceiling = accept_limit(book)
        if ceiling <= 0:
            # A zero ceiling would reject every charge and pay 1.5a to the whole field.
            # That is game 1's failure mode; refuse rather than honour it.
            return None
        return Verdict(
            accept_ceiling=ceiling,
            note=f"limit from the price book ({ceiling:.0f}), charge left to the prior",
        )


RULES = [BookLimitGuard()]


def demo() -> None:
    """Self-check: the guard must cap a raise and leave a lowering alone."""
    from c2f.core.models import Belief
    from c2f.decision.quantile import decide

    book = Belief(median=100.0, sigma=0.5)
    ceiling = accept_limit(book)

    # A prior that believes the item is worth far more: b must be capped to the book's.
    bold = Belief(median=1000.0, sigma=0.5)
    _, b_capped = decide(bold, True, None, accept_ceiling=ceiling)
    assert abs(b_capped - ceiling) < 1e-9, (b_capped, ceiling)

    # A prior that believes it is worth far less: the ceiling must NOT raise b.
    timid = Belief(median=10.0, sigma=0.5)
    _, b_timid_plain = decide(timid, True, None)
    _, b_timid = decide(timid, True, None, accept_ceiling=ceiling)
    assert abs(b_timid - b_timid_plain) < 1e-9, "a ceiling must never raise b"
    assert b_timid < ceiling

    print("demo ok")


if __name__ == "__main__":
    demo()
