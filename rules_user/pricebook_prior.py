"""Baseline PRIOR: deterministic price book. Beats the LLM where we have hard
data; the LLM (priority 0) covers the long tail.

Promote to ACTIVE via rules_state.json or the UI.
"""
from c2f.core.models import Belief, Context, Stage, Verdict
from c2f.estimate.pricebook import lookup, match_rate
from c2f.rules.protocol import BaseRule


class PricebookPrior(BaseRule):
    name = "pricebook_prior"
    stage = Stage.PRIOR
    priority = 10          # beats the LLM ensemble (priority 0)
    author = "core"

    def apply(self, ctx: Context) -> Verdict | None:
        rate = match_rate(ctx.item)
        if rate.trade == "unknown":
            return None    # abstain -- let the LLM handle the long tail
        return Verdict(belief=lookup(ctx.item), note=f"rate:{rate.trade}")


class SanityClamp(BaseRule):
    """GUARD: nothing may stray far from the book. Commutative with any other
    clamp, so this composes with teammates' guards without ordering concerns."""

    name = "sanity_clamp"
    stage = Stage.GUARD
    priority = 0
    author = "core"

    def apply(self, ctx: Context) -> Verdict | None:
        book = lookup(ctx.item)
        return Verdict(clamp=(book.median * 0.15, book.median * 4.0), note="0.15x-4x book")


RULES = [PricebookPrior(), SanityClamp()]
