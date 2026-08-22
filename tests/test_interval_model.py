from __future__ import annotations

import json

import pytest

from c2f.core.models import LineItem
from c2f.estimate.interval_model import (
    IntervalValuationModel,
    ModelError,
    Posterior,
)


def training_row(game, lower, upper, *, unit="stk", quantity=1.0):
    return {
        "game_id": game,
        "features": {"unit_class": unit, "quantity": quantity},
        "label": {"lower": lower, "upper": upper},
    }


def enough_rows():
    return [
        training_row(1, 10, 30),
        training_row(1, 15, 35),
        training_row(2, 12, 32),
        training_row(2, 18, 38),
        training_row(3, 14, 34),
        training_row(3, 20, 40),
    ]


def test_fits_full_posterior_and_positive_conditional_belief():
    model = IntervalValuationModel.fit(enough_rows())
    prediction = model.predict(LineItem(1, "synthetic", 1, "pcs"))
    assert not prediction.abstained, prediction.reason
    assert prediction.posterior is not None and prediction.belief is not None
    assert 10 <= prediction.posterior.quantile(1 / 3) < 40
    assert prediction.belief.quantile(1 / 3) > 0
    assert prediction.belief.source.startswith("interval-positive:stk")
    assert prediction.reason == "ok_conditional_on_coverage"


def test_posterior_preserves_zero_mass():
    posterior = Posterior((0, 10, 20), (0.4, 0.3, 0.3), "test")
    assert posterior.zero_mass == pytest.approx(0.4)
    assert posterior.quantile(1 / 3) == 0
    assert posterior.quantile(1 / 2) == 10


def test_abstains_for_thin_unit_cohort():
    model = IntervalValuationModel.fit(enough_rows() + [training_row(1, 1, 2, unit="h")])
    prediction = model.predict(LineItem(1, "synthetic", 1, "hrs"))
    assert prediction.abstained
    assert "informative_rows" in prediction.reason


def test_abstains_for_quantity_out_of_distribution():
    model = IntervalValuationModel.fit(enough_rows())
    prediction = model.predict(LineItem(1, "synthetic", 99, "pcs"))
    assert prediction.abstained
    assert prediction.reason == "quantity_out_of_distribution"


def test_uninformative_rows_do_not_fake_a_trainable_cohort():
    rows = [training_row(game, 0, None) for game in (1, 1, 2, 2, 3, 3)]
    model = IntervalValuationModel.fit(rows)
    assert not model.artifact["cohorts"]
    assert model.artifact["skipped_cohorts"]["stk"].startswith("informative_rows")


def test_artifact_round_trip(tmp_path):
    original = IntervalValuationModel.fit(enough_rows())
    path = tmp_path / "model.json"
    original.save(path)
    loaded = IntervalValuationModel.load(path)
    assert loaded.artifact == original.artifact


def test_corrupt_artifact_fails_explicitly(tmp_path):
    path = tmp_path / "model.json"
    path.write_text(json.dumps({"artifact_version": 999}))
    with pytest.raises(ModelError, match="unsupported"):
        IntervalValuationModel.load(path)
