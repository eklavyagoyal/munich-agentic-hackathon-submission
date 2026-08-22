from __future__ import annotations

import inspect

import pytest

from tools import valuation_backtest as backtest


def transaction(issuer, reviewer, accepted, amount, index=1):
    return {
        "issuer": issuer,
        "reviewer": reviewer,
        "line_item_index": index,
        "accepted": accepted,
        "amount": amount,
    }


def synthetic_matrix():
    # Three teams, two issuer offers on one item:
    # fair charges 40; fraud charges 80 and is accepted by R1 only.
    return [
        transaction("fair", "R1", True, 40),
        transaction("fair", "R2", False, 40),
        transaction("fraud", "R1", True, 80),
        transaction("fraud", "R2", False, 0),
    ]


def test_offer_classifier_uses_rejections_only():
    offers = {offer.issuer: offer for offer in backtest.classify_offers(synthetic_matrix(), 1)}
    assert offers["fair"].label == "fair" and offers["fair"].payment == 40
    assert offers["fraud"].label == "fraud" and offers["fraud"].payment == 80


def test_fair_counterfactual_income_is_exact_regardless_of_acceptance():
    result = backtest.handyman_income_bounds(
        synthetic_matrix(), 1, charge=30, threshold_lower=40, threshold_upper=80,
        team="Oasis",
    )
    assert result.income == backtest.Bounds(60, 60)
    assert result.threshold_state == "fair"


def test_fraud_income_uses_identified_acceptance_curve():
    result = backtest.handyman_income_bounds(
        synthetic_matrix(), 1, charge=80, threshold_lower=40, threshold_upper=80,
        team="Oasis",
    )
    assert result.acceptance_lower == result.acceptance_upper == 1
    assert result.income == backtest.Bounds(80, 80)
    assert result.threshold_state == "fraud"


def test_insurer_cost_is_exact_for_classified_exact_offers():
    rows = synthetic_matrix()
    # Add Oasis as reviewer so both opponent offers are in its counterfactual book.
    rows += [
        transaction("fair", "Oasis", True, 40),
        transaction("fraud", "Oasis", False, 0),
    ]
    assert backtest.insurer_cost_bounds(rows, 1, 50, team="Oasis") == backtest.Bounds(40, 40)


def test_unknown_all_accepted_offer_stays_bounded_not_guessed():
    rows = [transaction("unknown", "R1", True, 20),
            transaction("unknown", "Oasis", True, 20)]
    assert backtest.insurer_cost_bounds(rows, 1, 10, team="Oasis") == backtest.Bounds(0, 30)


def test_bootstrap_is_deterministic():
    first = backtest.bootstrap_lower_bound([1, 2, 3], samples=1000)
    second = backtest.bootstrap_lower_bound([1, 2, 3], samples=1000)
    assert first == second
    assert first is not None and first > 0


def test_score_formatter_has_no_hidden_context_dependency():
    score = backtest.ScoreBounds(backtest.Bounds(10, 12), backtest.Bounds(3, 5))
    assert backtest._rounded_score(score)["net"] == {"lower": 5, "upper": 9}


def test_backtest_has_no_network_or_submission_path():
    source = inspect.getsource(backtest)
    assert "requests" not in source
    assert "urllib" not in source
    assert ".submit(" not in source
    assert "LiveApi" not in source
