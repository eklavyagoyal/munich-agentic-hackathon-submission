"""ADJUST: apply the multiplicative correction learned from past rounds.

This is the step that makes calibration actually change a submission. `c2f.calibrate`
fits it from interval-censored bounds (ARCHITECTURE §8); this rule multiplies the
belief by it.

ADJUST is commutative, so this composes with any other team member's scale rule
without ordering arguments. It abstains when there is no history, which is every
round before the first outcome lands.
"""
from c2f.core.models import Context, Stage, Verdict
from c2f.estimate.pricebook import match_rate
from c2f.rules.protocol import BaseRule

# Below this the correction is noise; not worth perturbing a submission for.
DEADBAND = 0.02


class CalibrationBias(BaseRule):
    name = "calibration_bias"
    stage = Stage.ADJUST
    priority = 0
    author = "prediction"

    def apply(self, ctx: Context) -> Verdict | None:
        bias = ctx.history.trade_bias
        if not bias:
            return None
        trade = match_rate(ctx.item).trade
        k = bias.get(trade, bias.get("*"))
        if k is None or abs(k - 1.0) < DEADBAND:
            return None
        which = trade if trade in bias else "global"
        return Verdict(scale=k, note=f"calibration {which} x{k:.3f}")


RULES = [CalibrationBias()]
