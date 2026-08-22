#!/usr/bin/env python3
"""Evaluate a leakage-free router for unreliable price-book valuations.

This is an offline, read-only research tool.  Threshold labels come exclusively
from :mod:`tools.thresholds`; the harvested row ``label`` field is never read.
The router is evaluated walk-forward: for test game g, both its model and every
quantity reference statistic use games strictly below g.

By default the JSON output includes per-item route scores keyed only by game and
item so another offline analysis can compose the router with a candidate valuer.
Use ``--aggregate-only`` for a compact human-readable research run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from c2f.core.models import LineItem
from c2f.decision.quantile import decide
from c2f.estimate.pricebook import (
    GENERIC,
    GENERIC_BY_UNIT,
    RATES,
    lookup,
    match_rate,
    unit_class,
)
from tools.thresholds import Bracket, brackets


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = ROOT / "data" / "harvest" / "line_items.jsonl"
DEFAULT_DB = ROOT / "data" / "c2f.sqlite"
DEFAULT_TEST_START = 20
DEFAULT_TEST_END = 43
MAX_DATASET_BYTES = 128 * 1024 * 1024
MAX_ROWS = 100_000
MAX_DESCRIPTION_CHARS = 100_000
MAX_UNIT_CHARS = 128
FEATURE_NAMES = (
    "generic_fallback",
    "unit_unrecognized",
    "band_log_ratio",
    "keyword_coverage",
    "keyword_ambiguity",
    "keyword_margin",
    "log_quantity",
    "quantity_extremity",
    "log_book_total",
)
MODEL_PARAMETERS = len(FEATURE_NAMES) + 1  # coefficients plus intercept
MODEL_ITERATIONS = 1_200
MODEL_LEARNING_RATE = 0.05
MODEL_L2 = 0.10
ROUTE_THRESHOLD = 0.50
BOOTSTRAP_REPLICATES = 2_000
BOOTSTRAP_SEED = 20_260_823


class ConfidenceError(RuntimeError):
    """A safe, actionable failure that never embeds claim text."""


@dataclass(frozen=True)
class ItemInput:
    game: int
    item: int
    description: str
    quantity: float
    unit: str


@dataclass(frozen=True)
class StaticRow:
    game: int
    item: int
    quantity: float
    unit_group: str
    charge: float
    t_lo: float
    t_hi: float | None
    target: str
    generic_fallback: float
    unit_unrecognized: float
    band_log_ratio: float
    keyword_coverage: float
    keyword_ambiguity: float
    keyword_margin: float
    log_quantity: float
    log_book_total: float


@dataclass(frozen=True)
class ReferenceStats:
    global_center: float
    global_scale: float
    by_unit: dict[str, tuple[float, float]]


@dataclass(frozen=True)
class LogisticModel:
    means: tuple[float, ...]
    scales: tuple[float, ...]
    coefficients: tuple[float, ...]
    intercept: float

    def score(self, values: Sequence[float]) -> float:
        if len(values) != len(self.coefficients):
            raise ConfidenceError("model feature width changed at prediction time")
        z = self.intercept
        for value, mean, scale, coefficient in zip(
            values, self.means, self.scales, self.coefficients
        ):
            z += coefficient * ((value - mean) / scale)
        return _sigmoid(z)


def _verify_readonly(root: Path) -> None:
    env_path = root / ".env"
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ConfidenceError("cannot verify C2F_READONLY in .env") from exc
    assignments: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "C2F_READONLY":
            assignments.append(value.split("#", 1)[0].strip().strip("\"'"))
    if assignments != ["1"]:
        raise ConfidenceError("C2F_READONLY=1 is not set exactly once in .env")


def _require_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfidenceError(f"dataset {field} must be a positive integer")
    return value


def _require_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfidenceError(f"dataset {field} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ConfidenceError(f"dataset {field} must be finite and nonnegative")
    return result


def load_items(path: Path) -> tuple[dict[tuple[int, int], ItemInput], str]:
    try:
        size = path.stat().st_size
        if size <= 0 or size > MAX_DATASET_BYTES:
            raise ConfidenceError("dataset size is outside the allowed range")
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except ConfidenceError:
        raise
    except (OSError, UnicodeError) as exc:
        raise ConfidenceError("cannot read the harvested feature dataset") from exc

    result: dict[tuple[int, int], ItemInput] = {}
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        if len(result) >= MAX_ROWS:
            raise ConfidenceError("dataset row count exceeds the safety limit")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ConfidenceError(f"dataset line {line_number} is invalid JSON") from exc
        if not isinstance(row, dict) or not isinstance(row.get("features"), dict):
            raise ConfidenceError(f"dataset line {line_number} lacks features")
        game = _require_int(row.get("game_id"), "game_id")
        item = _require_int(row.get("line_item_index"), "line_item_index")
        features = row["features"]
        description = features.get("description")
        unit = features.get("unit")
        if not isinstance(description, str) or not description.strip():
            raise ConfidenceError(f"dataset game {game} item {item} lacks a description")
        if len(description) > MAX_DESCRIPTION_CHARS:
            raise ConfidenceError(f"dataset game {game} item {item} description is oversized")
        if not isinstance(unit, str) or len(unit) > MAX_UNIT_CHARS:
            raise ConfidenceError(f"dataset game {game} item {item} has an invalid unit")
        quantity = _require_number(features.get("quantity"), "quantity")
        key = (game, item)
        if key in result:
            raise ConfidenceError(f"duplicate dataset identity at game {game} item {item}")
        # Deliberately do not access row["label"].
        result[key] = ItemInput(game, item, description, quantity, unit)
    if not result:
        raise ConfidenceError("feature dataset is empty")
    return result, hashlib.sha256(raw).hexdigest()


def load_brackets(path: Path) -> tuple[list[Bracket], str]:
    if not path.is_file():
        raise ConfidenceError("threshold database is missing")
    try:
        uri = f"file:{path.resolve()}?mode=ro"
        con = sqlite3.connect(uri, uri=True, timeout=2.0)
        con.execute("PRAGMA query_only=ON")
        con.execute("BEGIN")
        values = brackets(con)
        con.rollback()
        con.close()
    except (OSError, sqlite3.Error) as exc:
        raise ConfidenceError("sanctioned threshold extraction failed") from exc
    if not values or len(values) > MAX_ROWS:
        raise ConfidenceError("sanctioned threshold row count is outside the allowed range")
    seen: set[tuple[int, int]] = set()
    canonical: list[dict[str, Any]] = []
    for bracket in values:
        key = (bracket.game, bracket.item)
        if key in seen:
            raise ConfidenceError("sanctioned thresholds returned a duplicate identity")
        seen.add(key)
        if (
            bracket.game <= 0
            or bracket.item <= 0
            or not math.isfinite(bracket.lo)
            or bracket.lo < 0
        ):
            raise ConfidenceError("sanctioned thresholds returned an invalid lower bound")
        hi: float | None = None if not bracket.bounded else bracket.hi
        if hi is not None and (not math.isfinite(hi) or hi <= bracket.lo):
            raise ConfidenceError("sanctioned thresholds returned contradictory bounds")
        canonical.append(
            {
                "game": bracket.game,
                "item": bracket.item,
                "t_lo": bracket.lo,
                "t_hi": hi,
                "n_fair": bracket.n_fair,
                "n_fraud": bracket.n_fraud,
            }
        )
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return values, hashlib.sha256(payload).hexdigest()


def classify_error(charge: float, t_lo: float, t_hi: float | None) -> str:
    """Return only conclusions proved by the threshold bracket.

    A positive is a charge proved more than 2x too low or more than 2x too high.
    A negative requires enough information to rule out *both* directions.  Every
    remaining bracket is ambiguous and is excluded from classification metrics.
    """
    if not all(math.isfinite(value) and value >= 0 for value in (charge, t_lo)):
        raise ConfidenceError("non-finite value reached the target classifier")
    if t_hi is not None and (not math.isfinite(t_hi) or t_hi <= t_lo):
        raise ConfidenceError("invalid upper bound reached the target classifier")
    severe_under = charge < t_lo / 2.0
    severe_over = t_hi is not None and charge > 2.0 * t_hi
    if severe_under and severe_over:
        raise ConfidenceError("threshold bracket implies contradictory severe errors")
    if severe_under:
        return "severe_under"
    if severe_over:
        return "severe_over"
    proven_not_severe = (
        t_hi is not None and charge >= t_hi / 2.0 and charge <= 2.0 * t_lo
    )
    return "negative" if proven_not_severe else "ambiguous"


def _normalise_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold().strip())


def _match_features(item: ItemInput) -> tuple[float, float, float]:
    text = _normalise_text(item.description)
    wanted_unit = unit_class(item.unit)
    per_rate: list[int] = []
    for rate in RATES:
        if wanted_unit and rate.unit and unit_class(rate.unit) != wanted_unit:
            continue
        longest = max((len(keyword) for keyword in rate.keywords if keyword in text), default=0)
        if longest:
            per_rate.append(longest)
    if not per_rate:
        return 0.0, 0.0, 0.0
    per_rate.sort(reverse=True)
    best = per_rate[0]
    second = per_rate[1] if len(per_rate) > 1 else 0
    coverage = best / max(len(text), 1)
    ambiguity = math.log1p(len(per_rate))
    margin = (best - second) / best
    return coverage, ambiguity, margin


def build_rows(
    items: dict[tuple[int, int], ItemInput], threshold_rows: Iterable[Bracket]
) -> list[StaticRow]:
    result: list[StaticRow] = []
    for bracket in threshold_rows:
        key = (bracket.game, bracket.item)
        source = items.get(key)
        if source is None:
            raise ConfidenceError(
                f"missing features for sanctioned game {bracket.game} item {bracket.item}"
            )
        item = LineItem(
            idx=source.item,
            description=source.description,
            qty=source.quantity,
            unit=source.unit,
        )
        matched = match_rate(item)
        effective = (
            GENERIC_BY_UNIT.get(unit_class(source.unit), GENERIC)
            if matched is GENERIC
            else matched
        )
        if effective.low <= 0 or effective.high <= effective.low:
            raise ConfidenceError("price-book rate has an invalid interval")
        belief = lookup(item)
        charge, _accept_limit = decide(belief, covered=True, clamp=None)
        if not math.isfinite(charge) or charge < 0:
            raise ConfidenceError("production decision emitted an invalid charge")
        coverage, ambiguity, margin = _match_features(source)
        hi = None if not bracket.bounded else bracket.hi
        result.append(
            StaticRow(
                game=source.game,
                item=source.item,
                quantity=source.quantity,
                unit_group=unit_class(source.unit) or "unknown",
                charge=charge,
                t_lo=bracket.lo,
                t_hi=hi,
                target=classify_error(charge, bracket.lo, hi),
                generic_fallback=float(matched is GENERIC),
                unit_unrecognized=float(not bool(unit_class(source.unit))),
                band_log_ratio=math.log(effective.high / effective.low),
                keyword_coverage=coverage,
                keyword_ambiguity=ambiguity,
                keyword_margin=margin,
                log_quantity=math.log1p(source.quantity),
                log_book_total=math.log1p(belief.median),
            )
        )
    result.sort(key=lambda row: (row.game, row.item))
    return result


def _robust_center_scale(values: Sequence[float]) -> tuple[float, float]:
    if not values:
        raise ConfidenceError("cannot calculate a reference statistic from no rows")
    center = median(values)
    mad = median([abs(value - center) for value in values])
    return center, max(1.4826 * mad, 0.25)


def reference_stats(rows: Sequence[StaticRow]) -> ReferenceStats:
    if not rows:
        raise ConfidenceError("temporal feature reference has no historical rows")
    all_values = [row.log_quantity for row in rows]
    global_center, global_scale = _robust_center_scale(all_values)
    groups: dict[str, list[float]] = {}
    for row in rows:
        groups.setdefault(row.unit_group, []).append(row.log_quantity)
    by_unit = {
        name: _robust_center_scale(values)
        for name, values in groups.items()
        if len(values) >= 5
    }
    return ReferenceStats(global_center, global_scale, by_unit)


def feature_vector(row: StaticRow, reference: ReferenceStats) -> tuple[float, ...]:
    center, scale = reference.by_unit.get(
        row.unit_group, (reference.global_center, reference.global_scale)
    )
    extremity = min(abs(row.log_quantity - center) / scale, 8.0)
    values = (
        row.generic_fallback,
        row.unit_unrecognized,
        row.band_log_ratio,
        row.keyword_coverage,
        row.keyword_ambiguity,
        row.keyword_margin,
        row.log_quantity,
        extremity,
        row.log_book_total,
    )
    if len(values) != len(FEATURE_NAMES) or not all(math.isfinite(v) for v in values):
        raise ConfidenceError("feature construction emitted an invalid vector")
    return values


def _sigmoid(value: float) -> float:
    if value >= 0:
        inverse = math.exp(-min(value, 700.0))
        return 1.0 / (1.0 + inverse)
    exponential = math.exp(max(value, -700.0))
    return exponential / (1.0 + exponential)


def fit_logistic(features: Sequence[Sequence[float]], labels: Sequence[int]) -> LogisticModel:
    if len(features) != len(labels) or len(features) < MODEL_PARAMETERS * 2:
        raise ConfidenceError("temporal training fold has too few adjudicated rows")
    if not features or any(len(row) != len(FEATURE_NAMES) for row in features):
        raise ConfidenceError("temporal training fold has an invalid feature width")
    positives = sum(labels)
    negatives = len(labels) - positives
    if positives < 5 or negatives < 5:
        raise ConfidenceError("temporal training fold lacks both target classes")
    means = tuple(sum(row[index] for row in features) / len(features) for index in range(len(FEATURE_NAMES)))
    scales_list: list[float] = []
    for index, mean in enumerate(means):
        variance = sum((row[index] - mean) ** 2 for row in features) / len(features)
        scales_list.append(max(math.sqrt(variance), 1e-6))
    scales = tuple(scales_list)
    standardised = [
        tuple((value - mean) / scale for value, mean, scale in zip(row, means, scales))
        for row in features
    ]
    positive_weight = len(labels) / (2.0 * positives)
    negative_weight = len(labels) / (2.0 * negatives)
    sample_weights = [positive_weight if label else negative_weight for label in labels]
    normaliser = sum(sample_weights)
    coefficients = [0.0] * len(FEATURE_NAMES)
    intercept = 0.0
    for _ in range(MODEL_ITERATIONS):
        gradient = [0.0] * len(FEATURE_NAMES)
        intercept_gradient = 0.0
        for row, label, sample_weight in zip(standardised, labels, sample_weights):
            prediction = _sigmoid(intercept + sum(c * x for c, x in zip(coefficients, row)))
            error = (prediction - label) * sample_weight
            intercept_gradient += error
            for index, value in enumerate(row):
                gradient[index] += error * value
        intercept -= MODEL_LEARNING_RATE * intercept_gradient / normaliser
        for index in range(len(coefficients)):
            regularised = gradient[index] / normaliser + MODEL_L2 * coefficients[index]
            coefficients[index] -= MODEL_LEARNING_RATE * regularised
        if not math.isfinite(intercept) or not all(math.isfinite(v) for v in coefficients):
            raise ConfidenceError("router optimisation did not remain finite")
    return LogisticModel(means, scales, tuple(coefficients), intercept)


def roc_auc(labels: Sequence[int], scores: Sequence[float]) -> float:
    if len(labels) != len(scores) or not labels:
        raise ConfidenceError("AUC inputs are empty or misaligned")
    positives = sum(labels)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        raise ConfidenceError("AUC requires both target classes")
    ordered = sorted(zip(scores, labels), key=lambda pair: pair[0])
    positive_rank_sum = 0.0
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        average_rank = ((index + 1) + end) / 2.0
        positive_rank_sum += average_rank * sum(label for _, label in ordered[index:end])
        index = end
    return (positive_rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def average_precision(labels: Sequence[int], scores: Sequence[float]) -> float:
    if len(labels) != len(scores) or not labels:
        raise ConfidenceError("average-precision inputs are empty or misaligned")
    positives = sum(labels)
    if positives == 0:
        raise ConfidenceError("average precision requires a positive class")
    ordered = sorted(zip(scores, labels), key=lambda pair: pair[0], reverse=True)
    true_positives = predicted = previous_true_positives = 0
    result = 0.0
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        predicted += end - index
        true_positives += sum(label for _, label in ordered[index:end])
        if true_positives > previous_true_positives:
            recall_increment = (true_positives - previous_true_positives) / positives
            result += recall_increment * (true_positives / predicted)
        previous_true_positives = true_positives
        index = end
    return result


def _safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    return None if denominator == 0 else numerator / denominator


def classification_metrics(
    labelled_predictions: Sequence[tuple[StaticRow, float, bool]]
) -> dict[str, Any]:
    tp = fp = tn = fn = 0
    under_total = under_flagged = over_total = over_flagged = 0
    labels: list[int] = []
    scores: list[float] = []
    for row, score, flagged in labelled_predictions:
        positive = row.target in {"severe_under", "severe_over"}
        if row.target == "severe_under":
            under_total += 1
            under_flagged += int(flagged)
        elif row.target == "severe_over":
            over_total += 1
            over_flagged += int(flagged)
        elif row.target != "negative":
            raise ConfidenceError("ambiguous row reached classification metrics")
        labels.append(int(positive))
        scores.append(score)
        if flagged and positive:
            tp += 1
        elif flagged:
            fp += 1
        elif positive:
            fn += 1
        else:
            tn += 1
    return {
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "precision": _safe_ratio(tp, tp + fp),
        "recall": _safe_ratio(tp, tp + fn),
        "specificity": _safe_ratio(tn, tn + fp),
        "positive_prevalence": _safe_ratio(tp + fn, tp + fp + tn + fn),
        "flag_rate_evaluable": _safe_ratio(tp + fp, tp + fp + tn + fn),
        "severe_under_recall": _safe_ratio(under_flagged, under_total),
        "severe_over_recall": _safe_ratio(over_flagged, over_total),
        "roc_auc": roc_auc(labels, scores),
        "average_precision": average_precision(labels, scores),
    }


def _percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ConfidenceError("cannot calculate an empty bootstrap interval")
    ordered = sorted(values)
    index = min(int(probability * len(ordered)), len(ordered) - 1)
    return ordered[index]


def game_block_bootstrap(
    predictions: Sequence[tuple[StaticRow, float, bool]], games: Sequence[int]
) -> dict[str, list[float]]:
    by_game: dict[int, list[tuple[StaticRow, float, bool]]] = {game: [] for game in games}
    for prediction in predictions:
        by_game[prediction[0].game].append(prediction)
    rng = random.Random(BOOTSTRAP_SEED)
    auc_values: list[float] = []
    ap_values: list[float] = []
    for _ in range(BOOTSTRAP_REPLICATES):
        sample: list[tuple[StaticRow, float, bool]] = []
        for _slot in games:
            sample.extend(by_game[rng.choice(games)])
        labels = [int(row.target != "negative") for row, _, _ in sample]
        scores = [score for _, score, _ in sample]
        if labels and 0 < sum(labels) < len(labels):
            auc_values.append(roc_auc(labels, scores))
            ap_values.append(average_precision(labels, scores))
    if len(auc_values) < BOOTSTRAP_REPLICATES * 0.9:
        raise ConfidenceError("too many game bootstrap samples lacked both classes")
    return {
        "roc_auc_95": [_percentile(auc_values, 0.025), _percentile(auc_values, 0.975)],
        "average_precision_95": [
            _percentile(ap_values, 0.025),
            _percentile(ap_values, 0.975),
        ],
        "valid_replicates": len(auc_values),
    }


def baseline_metric(rows: Sequence[StaticRow]) -> dict[str, Any]:
    proven_income = 0.0
    best_possible = 0.0
    under = over = excluded = 0
    for row in rows:
        best_possible += 16.0 * row.t_lo
        if row.charge <= row.t_lo:
            proven_income += 16.0 * row.charge
            under += 1
        elif row.t_hi is not None and row.charge > row.t_hi:
            over += 1
        else:
            excluded += 1
    if best_possible <= 0:
        raise ConfidenceError("held-out BEST POSSIBLE denominator is not positive")
    return {
        "items_with_t_lo": len(rows),
        "under_count": under,
        "over_count": over,
        "excluded_unprovable_count": excluded,
        "proven_income_eur": round(proven_income, 2),
        "best_possible_eur": round(best_possible, 2),
        "score": proven_income / best_possible,
    }


def evaluate(
    rows: Sequence[StaticRow], test_start: int, test_end: int, include_items: bool
) -> dict[str, Any]:
    if test_start <= 1 or test_end < test_start:
        raise ConfidenceError("test game range is invalid")
    expected_games = list(range(test_start, test_end + 1))
    available_games = {row.game for row in rows}
    missing = [game for game in expected_games if game not in available_games]
    if missing:
        raise ConfidenceError("one or more requested held-out games have no thresholds")

    predictions: list[tuple[StaticRow, float, bool]] = []
    prediction_features: dict[tuple[int, int], tuple[float, ...]] = {}
    folds: list[dict[str, Any]] = []
    last_model: LogisticModel | None = None
    for game in expected_games:
        historical = [row for row in rows if row.game < game]
        training = [row for row in historical if row.target != "ambiguous"]
        reference = reference_stats(historical)
        train_features = [feature_vector(row, reference) for row in training]
        train_labels = [int(row.target != "negative") for row in training]
        model = fit_logistic(train_features, train_labels)
        last_model = model
        folds.append(
            {
                "test_game": game,
                "max_train_game": max(row.game for row in historical),
                "train_evaluable_rows": len(training),
                "train_positive_rows": sum(train_labels),
                "rows_per_parameter": len(training) / MODEL_PARAMETERS,
            }
        )
        for row in (value for value in rows if value.game == game):
            features = feature_vector(row, reference)
            score = model.score(features)
            flagged = score >= ROUTE_THRESHOLD
            predictions.append((row, score, flagged))
            prediction_features[(row.game, row.item)] = features
    if last_model is None:
        raise ConfidenceError("no temporal folds were evaluated")

    heldout_rows = [row for row in rows if test_start <= row.game <= test_end]
    if len(predictions) != len(heldout_rows):
        raise ConfidenceError("held-out prediction coverage is incomplete")
    evaluable = [prediction for prediction in predictions if prediction[0].target != "ambiguous"]
    ambiguous = [prediction for prediction in predictions if prediction[0].target == "ambiguous"]
    metrics = classification_metrics(evaluable)
    metrics["game_block_bootstrap"] = game_block_bootstrap(evaluable, expected_games)
    metrics["heldout_items"] = len(predictions)
    metrics["evaluable_items"] = len(evaluable)
    metrics["ambiguous_excluded_items"] = len(ambiguous)
    metrics["target_counts"] = {
        target: sum(row.target == target for row, _, _ in predictions)
        for target in ("severe_under", "severe_over", "negative", "ambiguous")
    }
    metrics["evaluation_coverage"] = len(evaluable) / len(predictions)
    metrics["flagged_all_items"] = sum(flagged for _, _, flagged in predictions)
    metrics["flagged_ambiguous_items"] = sum(flagged for _, _, flagged in ambiguous)
    metrics["flag_rate_all_items"] = metrics["flagged_all_items"] / len(predictions)
    if metrics["precision"] is not None and metrics["positive_prevalence"]:
        metrics["precision_lift_absolute"] = (
            metrics["precision"] - metrics["positive_prevalence"]
        )
        metrics["precision_lift_relative"] = (
            metrics["precision"] / metrics["positive_prevalence"]
        )

    fixed_risk_features = {
        "generic_fallback": lambda values: values[0],
        "unit_unrecognized": lambda values: values[1],
        "wider_band": lambda values: values[2],
        "weak_keyword_coverage": lambda values: -values[3],
        "keyword_ambiguity": lambda values: values[4],
        "weak_keyword_margin": lambda values: -values[5],
        "quantity_extremity": lambda values: values[7],
    }
    labels = [int(row.target != "negative") for row, _, _ in evaluable]
    metrics["univariate_roc_auc_predeclared_direction"] = {
        name: roc_auc(
            labels,
            [transform(prediction_features[(row.game, row.item)]) for row, _, _ in evaluable],
        )
        for name, transform in fixed_risk_features.items()
    }

    coefficients = {
        name: value for name, value in zip(FEATURE_NAMES, last_model.coefficients)
    }
    result: dict[str, Any] = {
        "protocol": {
            "test_games": [test_start, test_end],
            "strictly_temporal": all(
                fold["max_train_game"] < fold["test_game"] for fold in folds
            ),
            "target": (
                "positive iff charge < t_lo/2 or finite t_hi and charge > 2*t_hi; "
                "negative iff both severe directions are ruled out; otherwise ambiguous"
            ),
            "route_threshold": ROUTE_THRESHOLD,
            "threshold_tuned_on_test": False,
            "feature_count": len(FEATURE_NAMES),
            "model_parameter_count": MODEL_PARAMETERS,
            "model": {
                "type": "class-balanced L2 logistic risk score",
                "iterations": MODEL_ITERATIONS,
                "learning_rate": MODEL_LEARNING_RATE,
                "l2": MODEL_L2,
            },
        },
        "folds": folds,
        "heldout_router": metrics,
        "heldout_pricebook_baseline": baseline_metric(heldout_rows),
        "last_fold_standardized_coefficients": coefficients,
    }
    if include_items:
        result["items"] = [
            {
                "game": row.game,
                "item": row.item,
                "route_score": round(score, 8),
                "route": flagged,
                "target": row.target,
            }
            for row, score, flagged in predictions
        ]
    return result


def _round_floats(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 8)
    if isinstance(value, dict):
        return {key: _round_floats(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_round_floats(inner) for inner in value]
    return value


def self_test() -> None:
    assert classify_error(40.0, 100.0, 150.0) == "severe_under"
    assert classify_error(310.0, 100.0, 150.0) == "severe_over"
    assert classify_error(100.0, 75.0, 150.0) == "negative"
    assert classify_error(100.0, 75.0, None) == "ambiguous"
    assert math.isclose(roc_auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]), 1.0)
    assert math.isclose(roc_auc([0, 1], [0.5, 0.5]), 0.5)
    synthetic_x = [
        (-2.0,) * len(FEATURE_NAMES),
        (-1.0,) * len(FEATURE_NAMES),
        (-0.5,) * len(FEATURE_NAMES),
        (-0.25,) * len(FEATURE_NAMES),
        (0.25,) * len(FEATURE_NAMES),
        (0.5,) * len(FEATURE_NAMES),
        (1.0,) * len(FEATURE_NAMES),
        (2.0,) * len(FEATURE_NAMES),
    ] * 3
    synthetic_y = [0, 0, 0, 0, 1, 1, 1, 1] * 3
    model = fit_logistic(synthetic_x, synthetic_y)
    assert model.score(synthetic_x[0]) < model.score(synthetic_x[7])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--test-start", type=int, default=DEFAULT_TEST_START)
    parser.add_argument("--test-end", type=int, default=DEFAULT_TEST_END)
    parser.add_argument(
        "--aggregate-only", action="store_true", help="omit per-item route scores"
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        if args.self_test:
            self_test()
            print(json.dumps({"self_test": "passed"}, sort_keys=True))
            return 0
        _verify_readonly(ROOT)
        items, dataset_hash = load_items(args.dataset)
        threshold_rows, threshold_hash = load_brackets(args.db)
        rows = build_rows(items, threshold_rows)
        result = evaluate(rows, args.test_start, args.test_end, not args.aggregate_only)
        result["evidence"] = {
            "dataset_sha256": dataset_hash,
            "sanctioned_thresholds_sha256": threshold_hash,
            "sanctioned_threshold_rows": len(threshold_rows),
            "feature_rows": len(items),
            "C2F_READONLY": 1,
        }
        print(json.dumps(_round_floats(result), sort_keys=True, indent=2))
        return 0
    except (ConfidenceError, OSError, ValueError) as exc:
        print(
            json.dumps(
                {"error_class": type(exc).__name__, "error": str(exc)}, sort_keys=True
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
