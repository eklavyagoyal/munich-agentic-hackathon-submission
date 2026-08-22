"""Turn a price belief into the two numbers we submit. Derivation: GAMEPLAN.md §2.

Two independent problems, neither of which depends on what opponents do:

  a (charge)  maximise  a · P(t ≥ a)          ->  inverse Mills ratio = sigma
  b (limit)   accept iff P(fair) > 2/3        ->  b = 1/3-quantile of t

Run `python -m c2f.decide` for the self-check.
"""

from math import exp, log
from statistics import NormalDist

_N = NormalDist()

# P(t >= b) must exceed this for accepting to beat rejecting.
# Wrongful accept costs a, wrongful reject costs 0.5a  ->  1 < 1.5q  ->  q > 2/3.
_ACCEPT_BAR = 2 / 3


def sigma_from_quantiles(p10: float, p90: float) -> float:
    """Log-scale of a lognormal belief, from the estimator's own 10/90 spread."""
    if p10 <= 0 or p90 <= p10:
        return 0.35  # ponytail: a plausible default when the estimator gave us nothing usable
    return (log(p90) - log(p10)) / (_N.inv_cdf(0.9) - _N.inv_cdf(0.1))


def _charge_z(sigma: float) -> float:
    """Solve phi(z) / Phi(-z) = sigma. The inverse Mills ratio is increasing in z."""
    lo, hi = -8.0, 8.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if _N.pdf(mid) / _N.cdf(-mid) < sigma:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def charge(median: float, sigma: float) -> float:
    """`a`: the price we bill every opponent. ~0.75-0.80 x median, flat in sigma."""
    if median <= 0:
        return 0.0
    return median * exp(_charge_z(max(sigma, 1e-6)) * sigma)


def limit(median: float, sigma: float, boldness: float = 1.0) -> float:
    """`b`: the most we will pay. The 1/3-quantile of our belief about t.

    boldness scales the result once round data is in: the derivation assumes an
    arbitrary incoming charge, but opponents shade downward too (they are solving
    charge() as well), so an observed charge is likelier fair than the prior says.
    Raise toward 1.15 once the field is seen to charge fairly. See GAMEPLAN §2.2.
    """
    if median <= 0:
        return 0.0
    return median * exp(_N.inv_cdf(1 - _ACCEPT_BAR) * max(sigma, 1e-6)) * boldness


def submission(
    median: float,
    sigma: float,
    covered: bool = True,
    related: bool = True,
    boldness: float = 1.0,
) -> tuple[float, float]:
    """(a, b) for one line item, gross total. Rule C: uncovered or unrelated -> t = 0."""
    if not (covered and related):
        return 0.0, 0.0
    return round(charge(median, sigma), 2), round(limit(median, sigma, boldness), 2)


def demo() -> None:
    # The charge factor is ~0.75-0.80 across any plausible uncertainty. This flatness
    # is the whole reason we can shade with one constant under time pressure.
    for s in (0.15, 0.25, 0.35, 0.50):
        f = charge(100.0, s) / 100.0
        assert 0.73 < f < 0.82, (s, f)

    # b sits at the 1/3-quantile: below the median, above the charge.
    for s in (0.15, 0.25, 0.35, 0.50):
        a, b = submission(100.0, s)
        assert a < b < 100.0, (s, a, b)

    # Rule C dominates everything: no coverage, no money either way.
    assert submission(500.0, 0.3, covered=False) == (0.0, 0.0)
    assert submission(500.0, 0.3, related=False) == (0.0, 0.0)
    assert submission(0.0, 0.3) == (0.0, 0.0)

    # Scale-free: doubling the estimate doubles both numbers.
    a1, b1 = submission(100.0, 0.3)
    a2, b2 = submission(200.0, 0.3)
    assert abs(a2 - 2 * a1) < 0.02 and abs(b2 - 2 * b1) < 0.02

    # boldness only moves b, never a.
    a3, b3 = submission(100.0, 0.3, boldness=1.15)
    assert a3 == a1 and b3 > b1

    # sigma recovered from a 10/90 spread round-trips.
    assert abs(sigma_from_quantiles(70, 130) - 0.2414) < 0.01
    assert sigma_from_quantiles(0, 0) == 0.35  # garbage in -> default, not a crash

    print("decide.py self-check ok")
    print(f"{'sigma':>6} {'a/m':>7} {'b/m':>7}  P(a<=t)")
    for s in (0.15, 0.25, 0.35, 0.50):
        a, b = submission(1.0, s)
        print(f"{s:>6} {a:>7.3f} {b:>7.3f}  {_N.cdf(-_charge_z(s)):.2f}")


if __name__ == "__main__":
    demo()
