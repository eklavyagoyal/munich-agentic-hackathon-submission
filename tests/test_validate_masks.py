from __future__ import annotations

import json

import pytest

from tools import validate_masks as vm


def test_expensive_truth_uses_only_proven_bracket_sides() -> None:
    assert vm.expensive_truth(vm.Bracket(1, 1, 1200.0, None)) == "positive"
    assert vm.expensive_truth(vm.Bracket(1, 2, 10.0, 1200.0)) == "negative"
    assert vm.expensive_truth(vm.Bracket(1, 3, 1199.0, None)) == "unknown"
    assert vm.expensive_truth(vm.Bracket(1, 4, 10.0, 1200.01)) == "unknown"


def test_score_counts_missing_candidate_as_negative_and_unknown_separately() -> None:
    brackets = {
        (1, 1): vm.Bracket(1, 1, 1200.0, None),
        (1, 2): vm.Bracket(1, 2, 100.0, 500.0),
        (1, 3): vm.Bracket(1, 3, 500.0, None),
        (1, 4): vm.Bracket(1, 4, 1500.0, None),
    }
    events = vm.EventCandidates(
        candidates={
            (1, 1): vm.Candidate(500.0, 1300.0),
            (1, 3): vm.Candidate(500.0, 1500.0),
        },
        evaluated_games=frozenset({1}),
        fired_games=frozenset({1}),
    )

    got = vm.score(brackets, events, prediction="raise-to-floor")

    assert (got.true_positive, got.false_positive) == (1, 0)
    assert (got.true_negative, got.false_negative) == (1, 1)
    assert got.predicted_positive_unknown == 1
    assert got.labelled_without_candidate == 2
    assert got.precision_proven == 1.0
    assert got.precision_unknown_as_false == 0.5
    assert got.recall == 0.5
    assert got.point_gate_pass is False


def test_load_events_uses_prefetch_as_evaluated_game_proof(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    rows = [
        {"round": 1, "type": "prior.prefetched", "payload": {"n": 1}},
        {"round": 2, "type": "prior.prefetched", "payload": {"n": 1}},
        {
            "round": 1,
            "type": "rule.fired",
            "payload": {
                "rule": "llm_prior",
                "idx": 1,
                "from": [400.0, 500.0],
                "to": [900.0, 1300.0],
            },
        },
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    got = vm.load_event_candidates(path, rule="llm_prior")

    assert got.evaluated_games == frozenset({1, 2})
    assert got.fired_games == frozenset({1})
    assert set(got.candidates) == {(1, 1)}


def test_duplicate_candidate_fails_loudly(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    event = {
        "round": 1,
        "type": "rule.fired",
        "payload": {
            "rule": "llm_prior",
            "idx": 1,
            "from": [400.0, 500.0],
            "to": [900.0, 1300.0],
        },
    }
    path.write_text(json.dumps(event) + "\n" + json.dumps(event) + "\n", encoding="utf-8")

    with pytest.raises(vm.ValidationError, match="duplicate candidates"):
        vm.load_event_candidates(path, rule="llm_prior")


def test_game_parser_rejects_ambiguous_input() -> None:
    assert vm.parse_games("1-3,7") == {1, 2, 3, 7}
    with pytest.raises(vm.ValidationError):
        vm.parse_games("3-1")
    with pytest.raises(vm.ValidationError):
        vm.parse_games("1,,2")


def test_validator_has_no_live_or_transaction_path() -> None:
    source = vm.Path(vm.__file__).read_text(encoding="utf-8")
    assert "LiveApi" not in source
    assert "sqlite3" not in source
    assert ".submit(" not in source
