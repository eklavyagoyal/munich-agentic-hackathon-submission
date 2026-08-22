"""The decision rules must reproduce the derivation in ARCHITECTURE.md §1."""
import math

import pytest

from c2f.core.models import Belief
from c2f.decision.quantile import (
    ACCEPT_QUANTILE,
    accept_limit,
    charge,
    decide,
    optimal_charge_z,
)


@pytest.mark.parametrize("sigma,exp_a,exp_b", [
    (0.15, 0.804, 1.107),
    (0.20, 0.777, 1.144),
    (0.25, 0.758, 1.184),
    (0.35, 0.745, 1.266),
    (0.50, 0.772, 1.401),
])
def test_matches_derivation(sigma, exp_a, exp_b):
    b = Belief(median=1.0, sigma=sigma)
    assert charge(b) == pytest.approx(exp_a, abs=0.002)
    assert accept_limit(b) == pytest.approx(exp_b, abs=0.002)


def test_b_is_the_three_quarter_quantile():
    """ACCEPT_QUANTILE raised from 1/3 to 3/4 while belief medians are
    systematically too low (LLM misconfigured in early rounds). The 2/3 rule
    is theoretically optimal when beliefs are calibrated; empirical wrongful-
    reject:wrong-accept was 8.7:1 vs the expected 2:1, so b was far too low.
    Revisit once calibration k stabilises."""
    assert ACCEPT_QUANTILE == pytest.approx(3 / 4)
    b = Belief(median=500, sigma=0.3)
    assert accept_limit(b) == pytest.approx(b.quantile(3 / 4))


@pytest.mark.parametrize("sigma", [0.1, 0.2, 0.3, 0.5, 0.8, 1.2])
def test_charge_always_below_limit(sigma):
    """We must always be willing to accept our own charge."""
    b = Belief(median=730, sigma=sigma)
    a, lim = decide(b, covered=True)
    assert 0 < a < lim


def test_uncovered_is_zero_zero():
    assert decide(Belief(median=100, sigma=0.2), covered=False) == (0.0, 0.0)


def test_veto_charges_nothing_but_keeps_an_anchored_limit():
    """b=0 pays 1.5a to everyone; a generous b is exploitable up to c>=4t.
    The safe position is a=0 with an anchored limit."""
    a, b = decide(Belief(median=400, sigma=0.3), covered=True, vetoed=True)
    assert a == 0.0
    assert b == pytest.approx(400)


def test_clamp_cannot_collapse_the_pair():
    a, b = decide(Belief(median=1000, sigma=0.4), covered=True, clamp=(50.0, 50.5))
    assert a < b


@pytest.mark.parametrize("sigma", [0.6, 0.8, 1.0, 1.2, 2.0, 3.0])
def test_charge_never_bets_on_the_tail(sigma):
    """Past sigma~0.52 the unconstrained Mills optimum exceeds our own median and
    keeps climbing (1.35x at sigma=1.0, 2.0x at 1.2, 23x at the sigma=3.0 Belief
    permits). Beyond t we are paid only by
    opponents who wrongly accept, so that trade forfeits guaranteed income for a
    lottery. The charge must stay a discount on the median, and shrink as the
    estimate degrades."""
    b = Belief(median=1000.0, sigma=sigma)
    assert charge(b) < b.median
    # Structurally below the limit, before decide()'s repair clause is consulted.
    assert charge(b) < accept_limit(b)


def test_charge_decays_as_the_estimate_degrades():
    """A vaguer belief must never produce a bolder charge (above the cap point)."""
    prev = float("inf")
    for sigma in (0.55, 0.7, 1.0, 1.5, 2.5):
        a = charge(Belief(median=1000.0, sigma=sigma))
        assert a < prev, f"sigma={sigma} charged more than the tighter belief"
        prev = a


def test_cap_leaves_the_derivation_range_untouched():
    """The cap must not perturb the tested sigma<=0.5 band at all."""
    for sigma in (0.15, 0.20, 0.25, 0.35, 0.50):
        b = Belief(median=1.0, sigma=sigma)
        unc = math.exp(optimal_charge_z(sigma) * sigma)
        assert charge(b) == pytest.approx(unc, abs=1e-12)


# -- price book unit compatibility -----------------------------------------

def test_a_rate_is_never_applied_across_incompatible_units():
    """A per-Stk part rate must not be multiplied by an hour count. This priced
    "Windschutzscheibe Einbau, 2.5 h" at ~5x the truth, which overcharges into the
    fraud zone AND accepts fraud as insurer."""
    from c2f.core.models import LineItem
    from c2f.estimate.pricebook import lookup, match_rate

    hourly = LineItem(1, "Windschutzscheibe Einbau", 2.5, "h")
    per_part = LineItem(2, "Windschutzscheibe", 1, "Stk")
    assert match_rate(hourly).trade == "unknown"   # abstain -> the LLM handles it
    assert match_rate(per_part).trade == "vehicle"
    assert lookup(hourly).median < lookup(per_part).median


def test_unit_synonyms_are_equivalent():
    from c2f.core.models import LineItem
    from c2f.estimate.pricebook import lookup, unit_class

    assert unit_class("m²") == unit_class("m2") == unit_class(" QM ") == "m2"
    assert unit_class("Std") == unit_class("hours") == "h"
    assert unit_class("Stück") == unit_class("pcs") == "stk"
    assert unit_class("furlong") == ""      # unknown units stay compatible with all
    a = lookup(LineItem(1, "Laminat neu verlegen", 18, "m2"))
    b = lookup(LineItem(1, "Laminat neu verlegen", 18, "m²"))
    assert a.median == b.median


def test_drying_prices_per_day_and_per_unit():
    """Water damage bills drying per day far more often than per unit."""
    from c2f.core.models import LineItem
    from c2f.estimate.pricebook import lookup, match_rate

    per_day = LineItem(1, "Estrich technisch trocknen", 14, "Tag")
    assert match_rate(per_day).trade == "drying"
    # 14 days at 15-32 EUR/day net, not 14 x a per-unit rate.
    assert 200 < lookup(per_day).median < 600, lookup(per_day).median
    assert match_rate(LineItem(2, "Trocknungsgeraet", 2, "Stk")).trade == "drying"
