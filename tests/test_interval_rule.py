from __future__ import annotations

from dataclasses import dataclass

from c2f.core.models import Belief, Case, Context, LineItem
from c2f.estimate.interval_model import Posterior, Prediction
from c2f.estimate.pricebook import fallback
from c2f.rules.engine import RuleEngine
from c2f.rules.loader import load_rules
from c2f.rules.protocol import RuleState
import rules_user.interval_valuation_prior as module


def context(unit="pcs", quantity=1.0):
    item = LineItem(1, "synthetic work", quantity, unit)
    case = Case("synthetic", "synthetic policy", "synthetic damage", (item,))
    return Context(case=case, item=item)


@dataclass
class FakeModel:
    prediction: Prediction

    def predict(self, item):
        return self.prediction


def test_rule_returns_conditional_belief(monkeypatch):
    posterior = Posterior((0, 10, 20), (0.2, 0.4, 0.4), "synthetic")
    belief = Belief(20, 0.8, "synthetic")
    monkeypatch.setattr(
        module, "MODEL", FakeModel(Prediction(posterior, belief, "ok_conditional_on_coverage"))
    )
    verdict = module.IntervalValuationPrior().apply(context())
    assert verdict is not None and verdict.belief == belief
    assert "posterior_zero_mass=0.200" in verdict.note


def test_rule_abstains_when_model_abstains(monkeypatch):
    monkeypatch.setattr(module, "MODEL", FakeModel(Prediction(None, None, "unseen_unit")))
    assert module.IntervalValuationPrior().apply(context("hrs")) is None


def test_missing_artifact_abstains(monkeypatch):
    monkeypatch.setattr(module, "MODEL", None)
    assert module.IntervalValuationPrior().apply(context()) is None


def test_loader_keeps_new_rule_shadow(tmp_path):
    # Use the real rules directory: a missing local artifact is also a valid,
    # abstaining smoke path.  Loader state must remain SHADOW either way.
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    engine = RuleEngine(fallback)
    report = load_rules(engine, root / "rules_user")
    assert report.ok(), report.rejected
    registered = next(r for r in engine.rules if r.name == "interval_valuation_prior")
    assert registered.state is RuleState.SHADOW
