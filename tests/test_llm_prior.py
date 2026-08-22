"""The LLM prior must plug into the engine without ever costing us a round."""
import pytest

from c2f.core.models import (
    Belief, Case, Context, LineItem, PriorEstimate, Stage,
)
from c2f.estimate import ensemble, llm
from c2f.estimate.pricebook import fallback
from c2f.rules.engine import RuleEngine
from rules_user.llm_prior import LlmCoverage, LlmPrior

ITEM = LineItem(idx=2, description="Laminat neu verlegen", qty=18, unit="m2")
CASE = Case("c1", "policy: Leitungswasser covered", "living room flooded", (ITEM,))


def ctx(prefetch=None):
    return Context(case=CASE, item=ITEM, prefetch=prefetch or {})


# -- abstention: the whole point is that a missing estimate is harmless ------

def test_prior_abstains_without_a_prefetch():
    assert LlmPrior().apply(ctx()) is None
    assert LlmCoverage().apply(ctx()) is None


def test_prior_abstains_when_the_estimator_had_no_opinion():
    est = PriorEstimate()  # all fields None
    assert LlmPrior().apply(ctx({2: est})) is None
    assert LlmCoverage().apply(ctx({2: est})) is None


def test_prefetch_returns_empty_without_a_backend(monkeypatch):
    monkeypatch.setenv("C2F_BACKEND", "none")
    llm.reset()
    try:
        assert ensemble.prefetch_sync(CASE) == {}
    finally:
        llm.reset()


def test_engine_falls_back_to_the_pricebook_when_the_prior_abstains():
    """No key, no LLM -- we must still produce a real belief, never a zero."""
    engine = RuleEngine(fallback)
    engine.register(LlmPrior(), state=__import__(
        "c2f.rules.protocol", fromlist=["RuleState"]).RuleState.ACTIVE)
    d = engine.evaluate(ctx()).decision
    assert d.belief is not None and d.belief.median > 0
    assert d.a > 0 and d.b > d.a


# -- the coverage half ------------------------------------------------------

def test_unrelated_item_is_zeroed():
    est = PriorEstimate(belief=Belief(500, 0.2), covered=True, related=False,
                        note="46 m2 exceeds the 18 m2 room")
    v = LlmCoverage().apply(ctx({2: est}))
    assert v is not None and v.covered is False and "unrelated" in v.note


def test_uncovered_item_is_zeroed():
    est = PriorEstimate(belief=Belief(500, 0.2), covered=False, related=True)
    v = LlmCoverage().apply(ctx({2: est}))
    assert v is not None and v.covered is False and "not covered" in v.note


def test_covered_and_related_says_nothing():
    est = PriorEstimate(belief=Belief(500, 0.2), covered=True, related=True)
    assert LlmCoverage().apply(ctx({2: est})) is None


def test_partial_knowledge_is_not_treated_as_failure():
    """related=None must not zero an item the model said was covered."""
    est = PriorEstimate(belief=Belief(500, 0.2), covered=True, related=None)
    assert LlmCoverage().apply(ctx({2: est})) is None


# -- sigma: the ensemble spread is the point --------------------------------

def _s(p10, p50, p90, covered=True, related=True):
    return ensemble._Sample(covered, related, p10, p50, p90, "why", "")


def test_disagreeing_samples_widen_sigma_beyond_their_declared_bands():
    tight = [_s(34, 35, 36), _s(34, 35, 36), _s(34, 35, 36)]
    split = [_s(20, 21, 22), _s(34, 35, 36), _s(58, 60, 62)]
    assert (ensemble._combine(ITEM, split, "x").belief.sigma
            > ensemble._combine(ITEM, tight, "x").belief.sigma)


def test_agreement_does_not_make_a_vague_item_precise():
    """Three samples agreeing on p50 while each declares +/-60% is NOT certainty."""
    vague = [_s(15, 35, 80), _s(15, 35, 80), _s(15, 35, 80)]
    b = ensemble._combine(ITEM, vague, "x").belief
    assert b.sigma > 0.5, b.sigma


def test_lone_confident_sample_uses_its_declared_band():
    """A single sample has no ensemble spread; its own band must be used rather
    than a blanket constant."""
    b = ensemble._combine(ITEM, [_s(33, 35, 37)], "x").belief
    assert 0.04 < b.sigma < 0.25, b.sigma


def test_combine_applies_vat_and_quantity():
    from c2f.estimate.pricebook import gross
    b = ensemble._combine(ITEM, [_s(34, 35, 36)], "x").belief
    assert b.median == pytest.approx(gross(35 * 18), rel=1e-6)


def test_majority_vote_and_split_flag():
    samples = [_s(30, 35, 40, covered=True), _s(30, 35, 40, covered=True),
               _s(30, 35, 40, covered=False)]
    est = ensemble._combine(ITEM, samples, "x")
    assert est.covered is True
    assert "covered split 2/3" in est.flag


def test_swapped_quantiles_cannot_invert_sigma():
    """`_sample` clamps the ordering when parsing, but `_combine` must not depend on
    that: an inverted band has to degrade to "we know nothing", never to a negative
    sigma (which Belief would reject) or a fake-narrow one."""
    inverted = _s(90, 35, 10)
    assert ensemble._declared_sigma(inverted) == 0.0
    b = ensemble._combine(ITEM, [inverted], "x").belief
    assert b.sigma > 0 and b.median > 0
