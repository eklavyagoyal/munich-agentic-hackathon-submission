"""PRIOR + COVERAGE from the LLM ensemble (build order step 4).

These rules are PURE: the estimates were fetched concurrently before the round's
engine loop and handed in via `ctx.prefetch` (see c2f/estimate/ensemble.py). A rule
here does a dict lookup, so it is replayable offline and safe in the hot path.

They abstain whenever the ensemble has no opinion — no key configured, the call
failed, or the item was skipped — and the deterministic price book takes over.

Priorities follow the existing convention:
  COVERAGE  policy_exclusion (5) beats llm_coverage (0). A stated exclusion is a hard
            fact; the LLM's job here is RELATEDNESS, which no keyword table can judge.
  PRIOR     pricebook_prior (10) beats llm_prior (0), per that rule's own comment.
            Worth revisiting once we have round data: the LLM sees the policy, the
            damage scope, the quantity and the photos, so it should beat a keyword
            table even where the table matches. That is a one-line priority change,
            deliberately not made unilaterally.
"""
from c2f.core.models import Context, Stage, Verdict
from c2f.rules.protocol import BaseRule


class LlmPrior(BaseRule):
    name = "llm_prior"
    stage = Stage.PRIOR
    priority = 0
    author = "prediction"

    def apply(self, ctx: Context) -> Verdict | None:
        est = ctx.prefetch.get(ctx.item.idx)
        if est is None or est.belief is None:
            return None
        return Verdict(belief=est.belief, note=f"{est.note[:90]} {est.flag}".strip())


class LlmCoverage(BaseRule):
    """Covers the RELATEDNESS half of `t = 0` that policy_exclusion explicitly leaves
    open: an item can be a covered peril at a fair rate and still be fraudulent because
    its scope exceeds the reported damage (46 m2 of repainting for one 18 m2 room)."""

    name = "llm_coverage"
    stage = Stage.COVERAGE
    priority = 0
    author = "prediction"

    def apply(self, ctx: Context) -> Verdict | None:
        est = ctx.prefetch.get(ctx.item.idx)
        if est is None or (est.covered is None and est.related is None):
            return None
        # Either gate failing means t = 0, so a=b=0. Unknown is not treated as failure.
        covered = est.covered is not False and est.related is not False
        if covered:
            return None  # nothing to say; let a cheaper rule or the default stand
        which = "not covered" if est.covered is False else "unrelated to the damage"
        return Verdict(covered=False, note=f"{which}: {est.note[:90]}")


RULES = [LlmPrior(), LlmCoverage()]
