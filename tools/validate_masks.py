#!/usr/bin/env python3
"""Validate a logged per-item mask against sanctioned threshold brackets.

The default command answers the current high-value question without model calls and
without touching the tournament API::

    PYTHONPATH=. .venv/bin/python tools/validate_masks.py
    PYTHONPATH=. .venv/bin/python tools/validate_masks.py --prediction raise
    PYTHONPATH=. .venv/bin/python tools/validate_masks.py --json

Labels come only from ``tools/thresholds.py --jsonl``. For the expensive-item
target, an item is certainly expensive when ``t_lo >= 1200`` and certainly below
that target when its finite ``t_hi <= 1200``. Everything else is unresolved and
is never silently labelled negative.

The default prediction is the actionable mask: a logged ``llm_prior`` shadow
candidate both raises ``b`` and lands at or above EUR 1,200. ``--prediction raise``
scores every b-raise, which is useful for auditing collateral damage but is not the
same claim as "this item is expensive". Missing rule events count as abstentions /
negative predictions over every game where ``prior.prefetched`` proves the model path
ran. This matters because ``rule.fired`` contains only shadow candidates that differ
from the active decision.

No invoice, policy, damage, prompt, response, or description text is loaded or
printed. Output is aggregate and numeric. This file contains no transaction SQL,
API client, decryption key, model provider, or submit path.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parent.parent
THRESHOLDS = ROOT / "tools" / "thresholds.py"
EVENTS = ROOT / "data" / "events" / "tournament.jsonl"
EXPENSIVE_FLOOR_EUR = 1_200.0
PRECISION_GATE = 0.90
MAX_THRESHOLD_OUTPUT_BYTES = 5_000_000
MAX_EVENT_BYTES = 100_000_000
MAX_EVENT_LINE_BYTES = 1_000_000


class ValidationError(RuntimeError):
    """A claim-safe, actionable validation failure."""


@dataclass(frozen=True)
class Bracket:
    game: int
    item: int
    t_lo: float
    t_hi: float | None


@dataclass(frozen=True)
class Candidate:
    from_b: float
    to_b: float


@dataclass(frozen=True)
class EventCandidates:
    candidates: Mapping[tuple[int, int], Candidate]
    evaluated_games: frozenset[int]
    fired_games: frozenset[int]


@dataclass(frozen=True)
class Metrics:
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    predicted_positive_unknown: int
    predicted_negative_unknown: int
    prediction_rows: int
    labelled_universe: int
    labelled_without_candidate: int
    candidate_without_label: int
    positive_truth: int
    negative_truth: int
    unknown_truth: int
    precision_proven: float | None
    precision_unknown_as_false: float | None
    precision_wilson_95_lower: float | None
    recall: float | None
    point_gate_pass: bool
    confidence_gate_pass: bool


def _number(value: object, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{context} is not numeric")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValidationError(f"{context} is not a finite non-negative number")
    return number


def _positive_int(value: object, context: str) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{context} is not a positive integer")
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{context} is not a positive integer") from exc
    if number < 1 or str(number) != str(value).strip():
        raise ValidationError(f"{context} is not a positive integer")
    return number


def parse_games(spec: str | None) -> set[int] | None:
    if spec is None:
        return None
    games: set[int] = set()
    for raw_part in spec.split(","):
        part = raw_part.strip()
        if not part:
            raise ValidationError("--games contains an empty component")
        if "-" in part:
            pieces = part.split("-", 1)
            lo = _positive_int(pieces[0], "--games range start")
            hi = _positive_int(pieces[1], "--games range end")
            if hi < lo:
                raise ValidationError("--games range end precedes its start")
            games.update(range(lo, hi + 1))
        else:
            games.add(_positive_int(part, "--games value"))
    if not games:
        raise ValidationError("--games selects no games")
    return games


def load_brackets(tool: Path = THRESHOLDS) -> dict[tuple[int, int], Bracket]:
    """Execute the sanctioned label tool; do not recreate its transaction join."""

    try:
        completed = subprocess.run(
            [sys.executable, str(tool), "--jsonl"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=20.0,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValidationError(
            f"sanctioned threshold command failed: {type(exc).__name__}"
        ) from exc
    if len(completed.stdout.encode("utf-8")) > MAX_THRESHOLD_OUTPUT_BYTES:
        raise ValidationError("sanctioned threshold output exceeds its size bound")

    brackets: dict[tuple[int, int], Bracket] = {}
    for line_number, raw in enumerate(completed.stdout.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
            game = _positive_int(row["game"], "threshold game")
            item = _positive_int(row["item"], "threshold item")
            t_lo = _number(row["t_lo"], "threshold t_lo")
            t_hi = None if row["t_hi"] is None else _number(row["t_hi"], "threshold t_hi")
        except (KeyError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise ValidationError(
                f"invalid sanctioned threshold row at output line {line_number}"
            ) from exc
        if t_hi is not None and t_hi <= t_lo:
            raise ValidationError(
                f"invalid sanctioned threshold bounds at output line {line_number}"
            )
        identity = (game, item)
        if identity in brackets:
            raise ValidationError("sanctioned thresholds contain a duplicate identity")
        brackets[identity] = Bracket(game, item, t_lo, t_hi)
    if not brackets:
        raise ValidationError("sanctioned threshold command returned no labels")
    return brackets


def _candidate(payload: Mapping[str, object], line_number: int) -> Candidate:
    try:
        before = payload["from"]
        after = payload["to"]
        if not isinstance(before, list) or not isinstance(after, list):
            raise ValidationError("from/to are not arrays")
        if len(before) != 2 or len(after) != 2:
            raise ValidationError("from/to arrays do not contain [a,b]")
        return Candidate(
            from_b=_number(before[1], "from b"),
            to_b=_number(after[1], "to b"),
        )
    except (KeyError, ValidationError) as exc:
        raise ValidationError(
            f"invalid rule candidate at event line {line_number}"
        ) from exc


def load_event_candidates(
    path: Path,
    *,
    rule: str,
    explicit_games: set[int] | None = None,
) -> EventCandidates:
    if not path.is_file():
        raise ValidationError(f"event log does not exist: {path}")
    if path.stat().st_size > MAX_EVENT_BYTES:
        raise ValidationError("event log exceeds its size bound")

    candidates: dict[tuple[int, int], Candidate] = {}
    fired_games: set[int] = set()
    prefetched_games: set[int] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            if len(raw.encode("utf-8")) > MAX_EVENT_LINE_BYTES:
                raise ValidationError(f"event line {line_number} exceeds its size bound")
            try:
                event = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"invalid JSON at event line {line_number}") from exc
            if not isinstance(event, dict):
                raise ValidationError(f"event line {line_number} is not an object")
            event_type = event.get("type")
            if event_type == "prior.prefetched":
                prefetched_games.add(_positive_int(event.get("round"), "event round"))
                continue
            payload = event.get("payload")
            if event_type != "rule.fired" or not isinstance(payload, dict):
                continue
            if payload.get("rule") != rule:
                continue
            game = _positive_int(event.get("round"), "event round")
            item = _positive_int(payload.get("idx"), "event item")
            identity = (game, item)
            if identity in candidates:
                raise ValidationError(
                    "event log contains duplicate candidates for the same game/item; "
                    "select a single replay log instead of silently taking last-write-wins"
                )
            candidates[identity] = _candidate(payload, line_number)
            fired_games.add(game)

    if not candidates:
        raise ValidationError(f"event log contains no candidates for rule {rule!r}")
    if explicit_games is not None:
        evaluated_games = set(explicit_games)
    elif rule == "llm_prior" and prefetched_games:
        # A shadow diff exists only when the candidate changes the rounded decision.
        # The prefetch event is the proof that the LLM path actually ran in a game.
        evaluated_games = prefetched_games
    else:
        evaluated_games = fired_games
    candidates = {key: value for key, value in candidates.items() if key[0] in evaluated_games}
    if not candidates:
        raise ValidationError("selected games contain no candidate rows")
    return EventCandidates(
        candidates=candidates,
        evaluated_games=frozenset(evaluated_games),
        fired_games=frozenset(fired_games & evaluated_games),
    )


def expensive_truth(bracket: Bracket) -> str:
    if bracket.t_lo >= EXPENSIVE_FLOOR_EUR:
        return "positive"
    if bracket.t_hi is not None and bracket.t_hi <= EXPENSIVE_FLOOR_EUR:
        return "negative"
    return "unknown"


def predicts_expensive(candidate: Candidate | None, method: str) -> bool:
    if candidate is None:
        return False
    raised = candidate.to_b > candidate.from_b + 1e-9
    at_least = candidate.to_b >= EXPENSIVE_FLOOR_EUR
    if method == "raise-to-floor":
        return raised and at_least
    if method == "at-least":
        return at_least
    if method == "raise":
        return raised
    raise ValidationError(f"unknown prediction method {method!r}")


def wilson_lower(successes: int, trials: int, z: float = 1.959963984540054) -> float | None:
    """Two-sided 95% Wilson interval's lower endpoint for a binomial proportion."""
    if trials <= 0:
        return None
    p = successes / trials
    z2 = z * z
    centre = p + z2 / (2 * trials)
    radius = z * math.sqrt((p * (1 - p) + z2 / (4 * trials)) / trials)
    return max(0.0, (centre - radius) / (1 + z2 / trials))


def score(
    brackets: Mapping[tuple[int, int], Bracket],
    event_candidates: EventCandidates,
    *,
    prediction: str,
) -> Metrics:
    universe = {
        identity: bracket
        for identity, bracket in brackets.items()
        if identity[0] in event_candidates.evaluated_games
    }
    if not universe:
        raise ValidationError("selected evaluation games contain no threshold labels")

    tp = fp = tn = fn = predicted_unknown = negative_unknown = 0
    positives = negatives = unknowns = 0
    for identity, bracket in universe.items():
        truth = expensive_truth(bracket)
        predicted = predicts_expensive(event_candidates.candidates.get(identity), prediction)
        if truth == "positive":
            positives += 1
            if predicted:
                tp += 1
            else:
                fn += 1
        elif truth == "negative":
            negatives += 1
            if predicted:
                fp += 1
            else:
                tn += 1
        else:
            unknowns += 1
            if predicted:
                predicted_unknown += 1
            else:
                negative_unknown += 1

    prediction_rows = sum(
        identity[0] in event_candidates.evaluated_games
        for identity in event_candidates.candidates
    )
    without_label = sum(identity not in universe for identity in event_candidates.candidates)
    labelled_without_candidate = sum(identity not in event_candidates.candidates for identity in universe)
    adjudicated_predicted = tp + fp
    conservative_predicted = tp + fp + predicted_unknown
    precision = tp / adjudicated_predicted if adjudicated_predicted else None
    precision_conservative = (
        tp / conservative_predicted if conservative_predicted else None
    )
    lower = wilson_lower(tp, conservative_predicted)
    recall = tp / positives if positives else None
    point_pass = precision_conservative is not None and precision_conservative >= PRECISION_GATE
    confidence_pass = lower is not None and lower >= PRECISION_GATE
    return Metrics(
        true_positive=tp,
        false_positive=fp,
        true_negative=tn,
        false_negative=fn,
        predicted_positive_unknown=predicted_unknown,
        predicted_negative_unknown=negative_unknown,
        prediction_rows=prediction_rows,
        labelled_universe=len(universe),
        labelled_without_candidate=labelled_without_candidate,
        candidate_without_label=without_label,
        positive_truth=positives,
        negative_truth=negatives,
        unknown_truth=unknowns,
        precision_proven=precision,
        precision_unknown_as_false=precision_conservative,
        precision_wilson_95_lower=lower,
        recall=recall,
        point_gate_pass=point_pass,
        confidence_gate_pass=confidence_pass,
    )


def _rounded_metrics(metrics: Metrics) -> dict[str, object]:
    result: dict[str, object] = asdict(metrics)
    for key, value in list(result.items()):
        if isinstance(value, float):
            result[key] = round(value, 6)
    return result


def report_json(
    metrics: Metrics,
    events: EventCandidates,
    *,
    event_path: Path,
    rule: str,
    prediction: str,
) -> dict[str, object]:
    return {
        "target": {
            "name": "expensive_item",
            "positive": "t_lo >= 1200",
            "negative": "finite t_hi <= 1200",
            "unknown": "all other sanctioned brackets",
            "precision_gate": PRECISION_GATE,
            "symmetric_accuracy_reported": False,
            "reason": "reviewer error costs are asymmetric; precision is the registered gate",
        },
        "prediction": {
            "rule": rule,
            "method": prediction,
            "definition": {
                "raise-to-floor": "to_b > from_b and to_b >= 1200",
                "at-least": "to_b >= 1200",
                "raise": "to_b > from_b",
            }[prediction],
        },
        "source": {
            "labels": "tools/thresholds.py --jsonl",
            "candidates": str(event_path),
            "network_calls": 0,
            "transaction_sql": False,
            "evaluated_games": sorted(events.evaluated_games),
            "games_with_candidate_diffs": sorted(events.fired_games),
        },
        "metrics": _rounded_metrics(metrics),
        "verdict": (
            "PASS_WITH_95_PERCENT_BOUND"
            if metrics.confidence_gate_pass
            else "POINT_PASS_INSUFFICIENT_EVIDENCE"
            if metrics.point_gate_pass
            else "FAIL_PRECISION_GATE"
        ),
    }


def _pct(value: object) -> str:
    return "undefined" if value is None else f"{float(value):.3f}"


def print_human(payload: Mapping[str, object]) -> None:
    source = payload["source"]
    prediction = payload["prediction"]
    metrics = payload["metrics"]
    assert isinstance(source, dict) and isinstance(prediction, dict) and isinstance(metrics, dict)
    print("labels      : tools/thresholds.py --jsonl (no transaction SQL)")
    print(f"candidates  : {source['candidates']} · rule {prediction['rule']} · no network")
    print(f"prediction  : {prediction['definition']}")
    print(
        f"universe    : {metrics['labelled_universe']} labelled items over "
        f"{len(source['evaluated_games'])} evaluated games; "
        f"{metrics['prediction_rows']} logged candidate diffs"
    )
    print(
        f"truth       : positive {metrics['positive_truth']} · negative "
        f"{metrics['negative_truth']} · unresolved {metrics['unknown_truth']}"
    )
    print(
        f"confusion   : TP {metrics['true_positive']} · FP {metrics['false_positive']} · "
        f"TN {metrics['true_negative']} · FN {metrics['false_negative']} · "
        f"predicted/unresolved {metrics['predicted_positive_unknown']}"
    )
    print(
        "precision   : proven "
        f"{_pct(metrics['precision_proven'])} · unresolved-as-false "
        f"{_pct(metrics['precision_unknown_as_false'])} · 95% Wilson lower "
        f"{_pct(metrics['precision_wilson_95_lower'])}"
    )
    print(f"recall      : {_pct(metrics['recall'])}")
    print(f"gate        : precision >= {PRECISION_GATE:.2f} · {payload['verdict']}")
    print("accuracy    : intentionally omitted; the two reviewer errors do not have equal cost")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--events", type=Path, default=EVENTS)
    parser.add_argument("--rule", default="llm_prior")
    parser.add_argument(
        "--prediction",
        choices=("raise-to-floor", "at-least", "raise"),
        default="raise-to-floor",
        help="registered expensive-mask definition; 'raise' is a collateral-damage audit",
    )
    parser.add_argument(
        "--games",
        default=None,
        help="comma/range selection; default llm_prior games proven by prior.prefetched",
    )
    parser.add_argument("--json", action="store_true", help="emit aggregate JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        games = parse_games(args.games)
        brackets = load_brackets()
        events = load_event_candidates(
            args.events.expanduser(), rule=args.rule, explicit_games=games
        )
        metrics = score(brackets, events, prediction=args.prediction)
        payload = report_json(
            metrics,
            events,
            event_path=args.events.expanduser(),
            rule=args.rule,
            prediction=args.prediction,
        )
    except ValidationError as exc:
        print(f"cannot validate mask: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        print_human(payload)
    # A failed research gate is a valid measurement, not a tool failure. Only
    # malformed/missing evidence exits non-zero.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
