"""The decision rules must reproduce the derivation in ARCHITECTURE.md §1."""
import pytest

from c2f.core.models import Belief
from c2f.decision.quantile import ACCEPT_QUANTILE, accept_limit, charge, decide


@pytest.mark.parametrize("sigma,exp_a,exp_b", [
    (0.15, 0.804, 0.937),
    (0.20, 0.777, 0.917),
    (0.25, 0.758, 0.898),
    (0.35, 0.745, 0.860),
    (0.50, 0.772, 0.806),
])
def test_matches_derivation(sigma, exp_a, exp_b):
    b = Belief(median=1.0, sigma=sigma)
    assert charge(b) == pytest.approx(exp_a, abs=0.002)
    assert accept_limit(b) == pytest.approx(exp_b, abs=0.002)


def test_b_is_the_one_third_quantile():
    """Accept iff P(a<=t) > 2/3. Not a tuning knob -- it falls out of the
    payoff matrix: wrongly accepting fraud costs `a`, wrongly rejecting a fair
    claim costs 0.5a, so fraud is exactly 2x worse."""
    assert ACCEPT_QUANTILE == pytest.approx(1 / 3)
    b = Belief(median=500, sigma=0.3)
    assert accept_limit(b) == pytest.approx(b.quantile(1 / 3))


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
