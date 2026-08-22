"""SHADOW PRIOR backed by the offline interval-censored valuation model.

The artifact is loaded once on the cold import path. ``apply`` is a pure lookup
and numeric transform; it performs no file or network I/O.  Missing, thin, or
out-of-distribution cohorts abstain and therefore fall through to the existing
price-book fallback.

The belief is conditional on the COVERAGE stage having passed.  The model also
tracks a zero-threshold mass, but a single lognormal ``Belief`` cannot represent
that mixture; the zero mass is retained for analysis and never hidden in a fake
median.
"""
from c2f.core.models import Context, Stage, Verdict
from c2f.estimate.interval_model import load_optional
from c2f.rules.protocol import BaseRule


MODEL, MODEL_LOAD_ERROR = load_optional()


class IntervalValuationPrior(BaseRule):
    name = "interval_valuation_prior"
    stage = Stage.PRIOR
    priority = 20
    author = "valuation"

    def apply(self, ctx: Context) -> Verdict | None:
        if MODEL is None:
            return None
        prediction = MODEL.predict(ctx.item)
        if prediction.belief is None:
            return None
        zero_mass = prediction.posterior.zero_mass if prediction.posterior else 0.0
        return Verdict(
            belief=prediction.belief,
            note=(
                f"{prediction.reason}; posterior_zero_mass={zero_mass:.3f}; "
                "magnitude conditional on coverage"
            ),
        )


RULES = [IntervalValuationPrior()]
