"""The stage algebra is the whole design (PIPELINE.md §4.1).

ADJUST composes by multiplication and GUARD by interval intersection -- both
commutative -- so the two stages contributors add to in bulk are
order-independent BY CONSTRUCTION. These tests are what that claim rests on.
"""
import itertools

import pytest

from c2f.core.models import Belief, Case, Context, LineItem, Stage, Verdict
from c2f.estimate.pricebook import fallback
from c2f.rules.engine import RuleEngine
from c2f.rules.protocol import RuleState

CASE = Case("c", "policy text", "damage desc", (LineItem(1, "generic work", 3.0, "h"),))


def ctx() -> Context:
    return Context(case=CASE, item=CASE.items[0])


def mk(name, stage, fn, priority=0):
    return type(name, (), {"name": name, "stage": stage, "priority": priority,
                           "author": "t", "apply": lambda self, c, _f=fn: _f(c)})()


def engine_with(*rules) -> RuleEngine:
    e = RuleEngine(fallback)
    for r in rules:
        e.register(r, state=RuleState.ACTIVE)
    e.begin_round()
    return e


PRIOR = mk("prior", Stage.PRIOR, lambda c: Verdict(belief=Belief(median=1000, sigma=0.25)), 10)


@pytest.mark.parametrize("order", list(itertools.permutations(range(3))))
def test_adjust_stage_is_commutative(order):
    scales = [0.9, 1.2, 0.75]
    rules = [mk(f"adj{i}", Stage.ADJUST, lambda c, s=scales[i]: Verdict(scale=s))
             for i in range(3)]
    e = engine_with(PRIOR, *[rules[i] for i in order])
    d = e.evaluate(ctx()).decision
    assert d.belief.median == pytest.approx(1000 * 0.9 * 1.2 * 0.75)


@pytest.mark.parametrize("order", list(itertools.permutations(range(3))))
def test_guard_stage_is_commutative(order):
    clamps = [(100.0, 900.0), (200.0, 5000.0), (50.0, 700.0)]
    rules = [mk(f"g{i}", Stage.GUARD, lambda c, k=clamps[i]: Verdict(clamp=k))
             for i in range(3)]
    e = engine_with(PRIOR, *[rules[i] for i in order])
    d = e.evaluate(ctx()).decision
    # intersection is [200, 700]; a and b both land inside it
    assert 200.0 <= d.a <= 700.0 and 200.0 <= d.b <= 700.0
    assert d.a < d.b


def test_prior_highest_priority_wins():
    lo = mk("lo", Stage.PRIOR, lambda c: Verdict(belief=Belief(median=100, sigma=0.2)), 1)
    hi = mk("hi", Stage.PRIOR, lambda c: Verdict(belief=Belief(median=900, sigma=0.2)), 99)
    assert engine_with(lo, hi).evaluate(ctx()).decision.belief.median == pytest.approx(900)


def test_abstaining_prior_falls_through_to_next():
    quiet = mk("quiet", Stage.PRIOR, lambda c: None, 99)
    loud = mk("loud", Stage.PRIOR, lambda c: Verdict(belief=Belief(median=42, sigma=0.2)), 1)
    assert engine_with(quiet, loud).evaluate(ctx()).decision.belief.median == pytest.approx(42)


def test_no_prior_at_all_falls_back_to_pricebook():
    e = engine_with()
    res = e.evaluate(ctx())
    assert res.decision.belief is not None
    assert res.decision.a < res.decision.b
    assert any("no PRIOR" in a["error"] for a in res.alerts)


def test_uncovered_item_submits_zero_zero():
    cov = mk("cov", Stage.COVERAGE, lambda c: Verdict(covered=False), 5)
    d = engine_with(cov, PRIOR).evaluate(ctx()).decision
    assert (d.a, d.b, d.covered) == (0.0, 0.0, False)


def test_a_broken_rule_cannot_break_the_round():
    boom = mk("boom", Stage.ADJUST, lambda c: (_ for _ in ()).throw(RuntimeError("x")))
    res = engine_with(PRIOR, boom).evaluate(ctx())
    assert res.decision.a < res.decision.b       # round survives
    assert any(a["rule"] == "boom" for a in res.alerts)


def test_broken_rule_is_disabled_for_the_rest_of_the_round():
    calls = []

    def boom(c):
        calls.append(1)
        raise RuntimeError("x")

    e = engine_with(PRIOR, mk("boom", Stage.ADJUST, boom))
    for _ in range(5):
        e.evaluate(ctx())
    assert len(calls) == 1        # tried once, then skipped


def test_shadow_rule_does_not_affect_the_decision():
    e = RuleEngine(fallback)
    e.register(PRIOR, state=RuleState.ACTIVE)
    e.register(mk("shadow_adj", Stage.ADJUST, lambda c: Verdict(scale=0.5)),
               state=RuleState.SHADOW)
    e.begin_round()
    res = e.evaluate(ctx())
    assert res.decision.belief.median == pytest.approx(1000)   # unchanged
    assert res.shadow_diffs and res.shadow_diffs[0]["rule"] == "shadow_adj"
    assert res.shadow_diffs[0]["to"][0] < res.shadow_diffs[0]["from"][0]


def test_contradictory_guards_are_dropped_not_obeyed():
    g1 = mk("g1", Stage.GUARD, lambda c: Verdict(clamp=(10.0, 20.0)))
    g2 = mk("g2", Stage.GUARD, lambda c: Verdict(clamp=(500.0, 900.0)))
    res = engine_with(PRIOR, g1, g2).evaluate(ctx())
    assert res.decision.a < res.decision.b
    assert any("contradictory" in a["error"] for a in res.alerts)
