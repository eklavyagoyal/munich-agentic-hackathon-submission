#!/usr/bin/env python3
"""Walk-forward fit of compact price-book rate corrections to proven brackets.

This is a read-only research tool.  Threshold labels are obtained only by invoking
``tools/thresholds.py --jsonl``; the harvested dataset supplies item features only.
For every held-out game, a one-parameter multiplicative correction is fit for each
eligible (production trade match, normalised unit) cohort using games strictly before
the held-out game.  Thin or unidentified cohorts abstain to the unchanged production
price book.

The fit is an interval-censored log-likelihood.  It uses both lower/right-censored and
upper/left-censored evidence and retains the production price book's per-item sigma.
The headline metric is deliberately not tournament P&L: it is the fixed-denominator
PROVEN INCOME metric specified for this research track.

    PYTHONPATH=. .venv/bin/python tools/fit_rates.py
    PYTHONPATH=. .venv/bin/python tools/fit_rates.py --json > /tmp/track-a.json
    PYTHONPATH=. .venv/bin/python tools/fit_rates.py --self-test

No claim text, policy text, damage text, or descriptions are emitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from c2f.core.models import Belief, LineItem  # noqa: E402
from c2f.decision.quantile import decide  # noqa: E402
from c2f.estimate.pricebook import GENERIC, lookup, match_rate, unit_class  # noqa: E402
from tools.score import score as tournament_score  # noqa: E402


DEFAULT_DATASET = ROOT / "data" / "harvest" / "line_items.jsonl"
DEFAULT_DB = ROOT / "data" / "c2f.sqlite"
DEFAULT_THRESHOLD_TOOL = ROOT / "tools" / "thresholds.py"
DEFAULT_START_GAME = 20
DEFAULT_END_GAME = 43

MAX_DATASET_BYTES = 128 * 1024 * 1024
MAX_DATASET_ROWS = 10_000
MAX_DATASET_LINE_CHARS = 4 * 1024 * 1024
MAX_DESCRIPTION_CHARS = 100_000
MAX_UNIT_CHARS = 128
MAX_THRESHOLD_BYTES = 16 * 1024 * 1024
THRESHOLD_TIMEOUT_SECONDS = 30

# Capacity and identification gates are fixed before held-out evaluation.
MIN_INFORMATIVE_ROWS = 6
MIN_GAMES = 3
MIN_SCALE = 1.0 / 8.0
MAX_SCALE = 8.0
LOG_SCALE_PRIOR_SD = math.log(2.0)
RIDGE_STRENGTH = 2.0
GOLDEN_ITERATIONS = 120

SQRT_TWO = math.sqrt(2.0)
LOG_SQRT_TWO_PI = 0.5 * math.log(2.0 * math.pi)


class FitRatesError(RuntimeError):
    """Actionable failure that never includes untrusted claim content."""


@dataclass(frozen=True)
class Threshold:
    game: int
    item: int
    lo: float
    hi: float | None

    @property
    def informative(self) -> bool:
        return self.lo > 0 or self.hi is not None


@dataclass(frozen=True)
class FeatureRow:
    game: int
    item: int
    line_item: LineItem


@dataclass(frozen=True)
class Observation:
    threshold: Threshold
    feature: FeatureRow
    baseline: Belief
    group: str


@dataclass(frozen=True)
class ScaleFit:
    group: str
    scale: float
    informative_rows: int
    games: int
    lower_rows: int
    upper_rows: int
    penalized_log_likelihood: float


@dataclass
class Metric:
    items: int = 0
    proven_income: float = 0.0
    best_possible: float = 0.0
    under: int = 0
    over: int = 0
    excluded: int = 0

    @property
    def score(self) -> float:
        if self.best_possible <= 0:
            raise FitRatesError("BEST POSSIBLE is zero; SCORE is undefined")
        return self.proven_income / self.best_possible

    @property
    def foregone(self) -> float:
        return self.best_possible - self.proven_income

    def as_json(self) -> dict[str, Any]:
        return {
            "items": self.items,
            "proven_income": round(self.proven_income, 6),
            "best_possible": round(self.best_possible, 6),
            "score": round(self.score, 12),
            "under": self.under,
            "over": self.over,
            "excluded_unprovable": self.excluded,
            "foregone_on_proven_income_denominator": round(self.foregone, 6),
        }


def _finite_number(value: Any, field: str, *, positive: bool = False) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise FitRatesError(f"{field} is not numeric") from exc
    if not math.isfinite(number) or (number <= 0 if positive else number < 0):
        condition = "positive and finite" if positive else "finite and nonnegative"
        raise FitRatesError(f"{field} must be {condition}")
    return number


def ensure_readonly_guard(root: Path = ROOT) -> None:
    """Fail closed unless the repository's explicit read-only guard remains set."""

    path = root / ".env"
    try:
        if path.stat().st_size > 64 * 1024:
            raise FitRatesError(".env is unexpectedly large")
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise FitRatesError("cannot verify C2F_READONLY in .env") from exc
    values = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "C2F_READONLY":
            values.append(value.strip().strip("\"'"))
    if values != ["1"]:
        raise FitRatesError(".env must contain exactly one C2F_READONLY=1 assignment")


def load_thresholds(tool: Path, db: Path) -> list[Threshold]:
    """Load labels only from the sanctioned thresholds CLI, never from dataset labels."""

    if not tool.is_file():
        raise FitRatesError(f"sanctioned threshold tool not found: {tool}")
    if not db.is_file():
        raise FitRatesError(f"transaction cache not found: {db}")
    try:
        result = subprocess.run(
            [sys.executable, str(tool), "--db", str(db), "--jsonl"],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=THRESHOLD_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FitRatesError(
            f"sanctioned threshold command failed: {type(exc).__name__}"
        ) from exc
    if result.returncode != 0:
        raise FitRatesError(
            f"sanctioned threshold command exited {result.returncode}; "
            "run tools/thresholds.py directly for diagnostics"
        )
    if len(result.stdout.encode("utf-8")) > MAX_THRESHOLD_BYTES:
        raise FitRatesError("sanctioned threshold output exceeds safety limit")
    if result.stderr.strip():
        raise FitRatesError("sanctioned threshold command emitted unexpected stderr")

    rows: list[Threshold] = []
    seen: set[tuple[int, int]] = set()
    for line_number, line in enumerate(result.stdout.splitlines(), start=1):
        if not line.strip():
            continue
        if len(rows) >= MAX_DATASET_ROWS:
            raise FitRatesError("sanctioned threshold row count exceeds safety limit")
        try:
            raw = json.loads(line)
            game = int(raw["game"])
            item = int(raw["item"])
            lo = _finite_number(raw["t_lo"], "threshold lower bound")
            raw_hi = raw["t_hi"]
            hi = None if raw_hi is None else _finite_number(
                raw_hi, "threshold upper bound", positive=True
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise FitRatesError(
                f"sanctioned threshold output line {line_number} is malformed"
            ) from exc
        if game <= 0 or item <= 0:
            raise FitRatesError("threshold identities must be positive integers")
        if hi is not None and hi <= lo:
            raise FitRatesError("threshold upper bound must be strictly above lower bound")
        key = (game, item)
        if key in seen:
            raise FitRatesError("sanctioned threshold output contains a duplicate identity")
        seen.add(key)
        rows.append(Threshold(game, item, lo, hi))
    if not rows:
        raise FitRatesError("sanctioned threshold tool returned no labels")
    return rows


def load_features(path: Path) -> tuple[dict[tuple[int, int], FeatureRow], dict[str, Any]]:
    """Read only item features; the harvested row's derived ``label`` is never touched."""

    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise FitRatesError(f"cannot read feature dataset: {type(exc).__name__}") from exc
    if not raw or len(raw) > MAX_DATASET_BYTES:
        raise FitRatesError("feature dataset size is outside the supported range")
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise FitRatesError("feature dataset is not UTF-8") from exc

    out: dict[tuple[int, int], FeatureRow] = {}
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        if len(line) > MAX_DATASET_LINE_CHARS:
            raise FitRatesError(f"feature dataset line {line_number} exceeds safety limit")
        if len(out) >= MAX_DATASET_ROWS:
            raise FitRatesError("feature dataset row count exceeds safety limit")
        try:
            row = json.loads(line)
            game = int(row["game_id"])
            item = int(row["line_item_index"])
            features = row["features"]
            description = features["description"]
            unit = features["unit"]
            quantity = _finite_number(features["quantity"], "feature quantity", positive=True)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise FitRatesError(f"feature dataset line {line_number} is malformed") from exc
        if game <= 0 or item <= 0:
            raise FitRatesError("feature identities must be positive integers")
        if not isinstance(description, str) or len(description) > MAX_DESCRIPTION_CHARS:
            raise FitRatesError("feature description has an invalid type or size")
        if not isinstance(unit, str) or len(unit) > MAX_UNIT_CHARS:
            raise FitRatesError("feature unit has an invalid type or size")
        key = (game, item)
        if key in out:
            raise FitRatesError("feature dataset contains a duplicate identity")
        out[key] = FeatureRow(
            game=game,
            item=item,
            line_item=LineItem(
                idx=item,
                description=description,
                qty=quantity,
                unit=unit,
            ),
        )
    if not out:
        raise FitRatesError("feature dataset has no rows")
    games = {row.game for row in out.values()}
    return out, {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "rows": len(out),
        "games": len(games),
        "min_game": min(games),
        "max_game": max(games),
    }


def cohort(item: LineItem) -> str:
    """Return only a non-sensitive production-match category, never matched text."""

    matched = match_rate(item)
    trade = "unknown" if matched is GENERIC else matched.trade
    unit = unit_class(item.unit) or "other"
    return f"{trade}:{unit}"


def join_observations(
    thresholds: Iterable[Threshold], features: dict[tuple[int, int], FeatureRow]
) -> list[Observation]:
    out: list[Observation] = []
    for threshold in thresholds:
        feature = features.get((threshold.game, threshold.item))
        if feature is None:
            raise FitRatesError(
                f"no feature row for game {threshold.game} item {threshold.item}"
            )
        baseline = lookup(feature.line_item)
        if baseline.median <= 0:
            raise FitRatesError("production price book returned a nonpositive median")
        out.append(Observation(threshold, feature, baseline, cohort(feature.line_item)))
    return out


def _log_normal_cdf(z: float) -> float:
    """Stable log Phi(z), including the far negative tail."""

    if z > -8.0:
        value = 0.5 * math.erfc(-z / SQRT_TWO)
        if value <= 0:
            raise FitRatesError("normal CDF underflowed unexpectedly")
        return math.log(value)
    inv2 = 1.0 / (z * z)
    correction = 1.0 - inv2 + 3.0 * inv2**2 - 15.0 * inv2**3
    if correction <= 0:
        raise FitRatesError("normal tail approximation became nonpositive")
    return -0.5 * z * z - math.log(-z) - LOG_SQRT_TWO_PI + math.log(correction)


def _log_diff_exp(log_a: float, log_b: float) -> float:
    """log(exp(a)-exp(b)) for a>b without catastrophic cancellation."""

    if not log_a > log_b:
        raise FitRatesError("invalid interval probability ordering")
    return log_a + math.log(-math.expm1(log_b - log_a))


def _log_interval_probability(observation: Observation, log_scale: float) -> float:
    threshold = observation.threshold
    mu = math.log(observation.baseline.median) + log_scale
    sigma = observation.baseline.sigma
    if threshold.lo <= 0:
        if threshold.hi is None:
            return 0.0
        z_hi = (math.log(threshold.hi) - mu) / sigma
        return _log_normal_cdf(z_hi)
    z_lo = (math.log(threshold.lo) - mu) / sigma
    if threshold.hi is None:
        return _log_normal_cdf(-z_lo)
    z_hi = (math.log(threshold.hi) - mu) / sigma
    if z_lo >= 0:
        return _log_diff_exp(_log_normal_cdf(-z_lo), _log_normal_cdf(-z_hi))
    return _log_diff_exp(_log_normal_cdf(z_hi), _log_normal_cdf(z_lo))


def _penalized_log_likelihood(rows: list[Observation], log_scale: float) -> float:
    likelihood = sum(_log_interval_probability(row, log_scale) for row in rows)
    ridge = 0.5 * RIDGE_STRENGTH * (log_scale / LOG_SCALE_PRIOR_SD) ** 2
    return likelihood - ridge


def _fit_one(group: str, rows: list[Observation]) -> ScaleFit | None:
    informative = [row for row in rows if row.threshold.informative]
    games = {row.threshold.game for row in informative}
    lower_rows = sum(row.threshold.lo > 0 for row in informative)
    upper_rows = sum(row.threshold.hi is not None for row in informative)
    if (
        len(informative) < MIN_INFORMATIVE_ROWS
        or len(games) < MIN_GAMES
        or not lower_rows
        or not upper_rows
    ):
        return None

    left, right = math.log(MIN_SCALE), math.log(MAX_SCALE)
    ratio = (math.sqrt(5.0) - 1.0) / 2.0
    x1 = right - ratio * (right - left)
    x2 = left + ratio * (right - left)
    f1 = _penalized_log_likelihood(informative, x1)
    f2 = _penalized_log_likelihood(informative, x2)
    for _ in range(GOLDEN_ITERATIONS):
        if f1 < f2:
            left, x1, f1 = x1, x2, f2
            x2 = left + ratio * (right - left)
            f2 = _penalized_log_likelihood(informative, x2)
        else:
            right, x2, f2 = x2, x1, f1
            x1 = right - ratio * (right - left)
            f1 = _penalized_log_likelihood(informative, x1)

    candidates = [
        (x1, f1),
        (x2, f2),
        (math.log(MIN_SCALE), _penalized_log_likelihood(informative, math.log(MIN_SCALE))),
        (math.log(MAX_SCALE), _penalized_log_likelihood(informative, math.log(MAX_SCALE))),
        (0.0, _penalized_log_likelihood(informative, 0.0)),
    ]
    # A deterministic tie break favours the unchanged book, then the lower scale.
    best_log_scale, best_likelihood = max(
        candidates, key=lambda pair: (pair[1], -abs(pair[0]), -pair[0])
    )
    scale = math.exp(best_log_scale)
    if not math.isfinite(scale) or not MIN_SCALE <= scale <= MAX_SCALE:
        raise FitRatesError("fitted scale violates configured bounds")
    return ScaleFit(
        group=group,
        scale=scale,
        informative_rows=len(informative),
        games=len(games),
        lower_rows=lower_rows,
        upper_rows=upper_rows,
        penalized_log_likelihood=best_likelihood,
    )


def fit_scales(training: Iterable[Observation]) -> dict[str, ScaleFit]:
    grouped: dict[str, list[Observation]] = defaultdict(list)
    for row in training:
        grouped[row.group].append(row)
    fitted: dict[str, ScaleFit] = {}
    for group, rows in sorted(grouped.items()):
        result = _fit_one(group, rows)
        if result is not None:
            fitted[group] = result
    return fitted


def scaled_belief(observation: Observation, fit: ScaleFit | None) -> Belief:
    if fit is None:
        return observation.baseline
    return Belief(
        median=observation.baseline.median * fit.scale,
        sigma=observation.baseline.sigma,
        source=f"fitted-rate:{observation.group}",
    )


def classify(charge: float, threshold: Threshold) -> str:
    if charge <= threshold.lo:
        return "under"
    if threshold.hi is not None and charge > threshold.hi:
        return "over"
    return "excluded_unprovable"


def add_metric(metric: Metric, charge: float, threshold: Threshold) -> str:
    if not math.isfinite(charge) or charge < 0:
        raise FitRatesError("decision layer returned an invalid charge")
    classification = classify(charge, threshold)
    metric.items += 1
    metric.best_possible += 16.0 * threshold.lo
    if classification == "under":
        metric.under += 1
        metric.proven_income += 16.0 * charge
    elif classification == "over":
        metric.over += 1
    else:
        metric.excluded += 1
    return classification


def _decision(belief: Belief) -> tuple[float, float]:
    # This exact call is the production charge derivation required by the track.
    return decide(belief, covered=True, clamp=None)


def _reviewer_unpriced(
    db: Path,
    baseline_decisions: dict[tuple[int, int], tuple[float, float]],
    candidate_decisions: dict[tuple[int, int], tuple[float, float]],
    start_game: int,
    end_game: int,
) -> dict[str, Any]:
    """Use tools.score's sanctioned API only for reviewer-side hidden-amount counts."""

    try:
        uri = f"file:{db.resolve()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=2.0) as connection:
            connection.execute("PRAGMA query_only=ON")
            baseline = tournament_score(connection, baseline_decisions)
            candidate = tournament_score(connection, candidate_decisions)
    except sqlite3.Error as exc:
        raise FitRatesError(f"tools.score API failed: {type(exc).__name__}") from exc

    games = range(start_game, end_game + 1)
    return {
        "method": "tools.score.score API",
        "games": [start_game, end_game],
        "baseline_unpriced": sum(
            int(baseline.get(game, {}).get("unpriced_risk", 0)) for game in games
        ),
        "candidate_unpriced": sum(
            int(candidate.get(game, {}).get("unpriced_risk", 0)) for game in games
        ),
        "note": "Hidden rejected-fraud amounts prevent an exact reviewer-side euro delta.",
    }


def evaluate(
    observations: list[Observation],
    all_features: dict[tuple[int, int], FeatureRow],
    db: Path,
    start_game: int,
    end_game: int,
) -> dict[str, Any]:
    if start_game <= 1 or end_game < start_game:
        raise FitRatesError("evaluation games must satisfy 1 < start <= end")
    available_games = {row.threshold.game for row in observations}
    missing_games = [
        game for game in range(start_game, end_game + 1) if game not in available_games
    ]
    if missing_games:
        raise FitRatesError("one or more requested held-out games has no threshold rows")

    baseline_metric = Metric()
    candidate_metric = Metric()
    per_item: list[dict[str, Any]] = []
    folds: list[dict[str, Any]] = []
    baseline_decisions: dict[tuple[int, int], tuple[float, float]] = {}
    candidate_decisions: dict[tuple[int, int], tuple[float, float]] = {}
    limit_moves = Counter()

    observations_by_key = {
        (row.threshold.game, row.threshold.item): row for row in observations
    }
    feature_games: dict[int, list[FeatureRow]] = defaultdict(list)
    for feature in all_features.values():
        feature_games[feature.game].append(feature)

    for test_game in range(start_game, end_game + 1):
        training = [row for row in observations if row.threshold.game < test_game]
        if not training or max(row.threshold.game for row in training) >= test_game:
            raise FitRatesError("strict temporal training invariant failed")
        test_rows = [row for row in observations if row.threshold.game == test_game]
        fits = fit_scales(training)
        informative_training = sum(row.threshold.informative for row in training)
        fitted_training = sum(fit.informative_rows for fit in fits.values())
        parameters = len(fits)  # exactly one learned scale per eligible cohort
        folds.append(
            {
                "test_game": test_game,
                "training_game_max": max(row.threshold.game for row in training),
                "training_threshold_rows": len(training),
                "training_informative_rows": informative_training,
                "fitted_cohort_rows": fitted_training,
                "parameters": parameters,
                "raw_rows_per_parameter": (
                    round(len(training) / parameters, 6) if parameters else None
                ),
                "informative_rows_per_parameter": (
                    round(informative_training / parameters, 6) if parameters else None
                ),
                "test_threshold_rows": len(test_rows),
                "candidate_fitted": sum(row.group in fits for row in test_rows),
                "candidate_pricebook_fallback": sum(row.group not in fits for row in test_rows),
            }
        )

        for row in test_rows:
            base_a, base_b = _decision(row.baseline)
            fit = fits.get(row.group)
            belief = scaled_belief(row, fit)
            candidate_a, candidate_b = _decision(belief)
            base_class = add_metric(baseline_metric, base_a, row.threshold)
            candidate_class = add_metric(candidate_metric, candidate_a, row.threshold)
            per_item.append(
                {
                    "game": row.threshold.game,
                    "item": row.threshold.item,
                    "group": row.group,
                    "source": "fitted_rate" if fit is not None else "pricebook_fallback",
                    "scale": round(fit.scale, 12) if fit is not None else 1.0,
                    "t_lo": row.threshold.lo,
                    "t_hi": row.threshold.hi,
                    "baseline_charge": round(base_a, 12),
                    "baseline_limit": round(base_b, 12),
                    "baseline_class": base_class,
                    "candidate_charge": round(candidate_a, 12),
                    "candidate_limit": round(candidate_b, 12),
                    "candidate_class": candidate_class,
                }
            )

        # Reviewer-side score coverage includes every parsed item, not only labelled ones.
        for feature in feature_games[test_game]:
            key = (test_game, feature.item)
            labelled = observations_by_key.get(key)
            if labelled is None:
                base = lookup(feature.line_item)
                pseudo = Observation(
                    threshold=Threshold(test_game, feature.item, 0.0, None),
                    feature=feature,
                    baseline=base,
                    group=cohort(feature.line_item),
                )
            else:
                pseudo = labelled
            base_ab = _decision(pseudo.baseline)
            candidate_ab = _decision(scaled_belief(pseudo, fits.get(pseudo.group)))
            baseline_decisions[key] = base_ab
            candidate_decisions[key] = candidate_ab
            if candidate_ab[1] > base_ab[1] + 1e-9:
                limit_moves["raised"] += 1
            elif candidate_ab[1] < base_ab[1] - 1e-9:
                limit_moves["lowered"] += 1
            else:
                limit_moves["unchanged"] += 1

    # A full-data fit is descriptive capacity for the next unseen game.  It never
    # contributes to any held-out metric above.
    full_fit = fit_scales(observations)
    full_informative = sum(row.threshold.informative for row in observations)
    reviewer = _reviewer_unpriced(
        db, baseline_decisions, candidate_decisions, start_game, end_game
    )
    reviewer["limits_raised"] = limit_moves["raised"]
    reviewer["limits_lowered"] = limit_moves["lowered"]
    reviewer["limits_unchanged"] = limit_moves["unchanged"]

    return {
        "schema_version": 1,
        "evaluation": {
            "held_out_games": [start_game, end_game],
            "split": "expanding_by_game_strictly_before_test_game",
            "threshold_rows": len(per_item),
        },
        "config": {
            "learned_parameter": "one multiplicative scale per eligible trade:unit cohort",
            "min_informative_rows": MIN_INFORMATIVE_ROWS,
            "min_games": MIN_GAMES,
            "requires_lower_and_upper_evidence": True,
            "scale_bounds": [MIN_SCALE, MAX_SCALE],
            "ridge_strength": RIDGE_STRENGTH,
            "log_scale_prior_sd": LOG_SCALE_PRIOR_SD,
            "sigma": "unchanged production pricebook sigma",
            "candidate_fallback": "unchanged production pricebook belief",
        },
        "baseline": baseline_metric.as_json(),
        "candidate": candidate_metric.as_json(),
        "score_delta": round(candidate_metric.score - baseline_metric.score, 12),
        "proven_income_delta": round(
            candidate_metric.proven_income - baseline_metric.proven_income, 6
        ),
        "folds": folds,
        "capacity": {
            "fold_parameter_min": min(fold["parameters"] for fold in folds),
            "fold_parameter_max": max(fold["parameters"] for fold in folds),
            "first_fold_raw_rows_per_parameter": folds[0]["raw_rows_per_parameter"],
            "last_fold_raw_rows_per_parameter": folds[-1]["raw_rows_per_parameter"],
            "full_fit_parameters": len(full_fit),
            "full_fit_threshold_rows": len(observations),
            "full_fit_informative_rows": full_informative,
            "full_fit_raw_rows_per_parameter": round(
                len(observations) / len(full_fit), 6
            ) if full_fit else None,
            "full_fit_informative_rows_per_parameter": round(
                full_informative / len(full_fit), 6
            ) if full_fit else None,
            "full_fit_cohorts": [
                {
                    "group": fit.group,
                    "scale": round(fit.scale, 12),
                    "informative_rows": fit.informative_rows,
                    "games": fit.games,
                    "lower_rows": fit.lower_rows,
                    "upper_rows": fit.upper_rows,
                }
                for fit in full_fit.values()
            ],
        },
        "reviewer_side": reviewer,
        "per_item": per_item,
    }


def self_test() -> None:
    threshold_rows = [
        Threshold(1, 1, 80.0, 120.0),
        Threshold(1, 2, 90.0, None),
        Threshold(2, 1, 0.0, 110.0),
        Threshold(2, 2, 85.0, 130.0),
        Threshold(3, 1, 95.0, None),
        Threshold(3, 2, 0.0, 125.0),
    ]
    feature_rows = [
        FeatureRow(t.game, t.item, LineItem(t.item, "synthetic repair", 1.0, "h"))
        for t in threshold_rows
    ]
    observations = [
        Observation(t, f, Belief(100.0, 0.35, "synthetic"), "synthetic:h")
        for t, f in zip(threshold_rows, feature_rows)
    ]
    fitted = fit_scales(observations)
    assert set(fitted) == {"synthetic:h"}
    assert MIN_SCALE <= fitted["synthetic:h"].scale <= MAX_SCALE

    metric = Metric()
    assert add_metric(metric, 50.0, Threshold(4, 1, 60.0, 80.0)) == "under"
    assert add_metric(metric, 90.0, Threshold(4, 2, 60.0, 80.0)) == "over"
    assert add_metric(metric, 70.0, Threshold(4, 3, 60.0, 80.0)) == "excluded_unprovable"
    assert (metric.under, metric.over, metric.excluded) == (1, 1, 1)
    assert metric.proven_income == 800.0
    assert metric.best_possible == 2880.0

    for test_game in (2, 3, 4):
        training = [row for row in observations if row.threshold.game < test_game]
        assert all(row.threshold.game < test_game for row in training)
    assert classify(80.0, Threshold(1, 1, 80.0, 100.0)) == "under"
    assert classify(100.0, Threshold(1, 1, 80.0, 100.0)) == "excluded_unprovable"
    assert classify(100.01, Threshold(1, 1, 80.0, 100.0)) == "over"


def _human_summary(result: dict[str, Any], identity: dict[str, Any], labels: int) -> str:
    baseline = result["baseline"]
    candidate = result["candidate"]
    capacity = result["capacity"]
    reviewer = result["reviewer_side"]
    lines = [
        "Track A fitted-rate walk-forward benchmark",
        f"features: {identity['rows']} rows, sha256={identity['sha256']}",
        f"sanctioned threshold rows: {labels}",
        f"held-out games: {result['evaluation']['held_out_games'][0]}-"
        f"{result['evaluation']['held_out_games'][1]}",
        (
            "baseline: SCORE={score:.6f}, PROVEN INCOME={income:.2f}, "
            "BEST POSSIBLE={best:.2f}, under={under}, over={over}, excluded={excluded}"
        ).format(
            score=baseline["score"], income=baseline["proven_income"],
            best=baseline["best_possible"], under=baseline["under"],
            over=baseline["over"], excluded=baseline["excluded_unprovable"],
        ),
        (
            "candidate: SCORE={score:.6f}, PROVEN INCOME={income:.2f}, "
            "BEST POSSIBLE={best:.2f}, under={under}, over={over}, excluded={excluded}"
        ).format(
            score=candidate["score"], income=candidate["proven_income"],
            best=candidate["best_possible"], under=candidate["under"],
            over=candidate["over"], excluded=candidate["excluded_unprovable"],
        ),
        f"delta: SCORE={result['score_delta']:+.6f}, "
        f"PROVEN INCOME={result['proven_income_delta']:+.2f}",
        (
            "capacity: fold parameters {lo}-{hi}; full fit {full} parameters, "
            "{ratio:.2f} raw rows/parameter"
        ).format(
            lo=capacity["fold_parameter_min"], hi=capacity["fold_parameter_max"],
            full=capacity["full_fit_parameters"],
            ratio=capacity["full_fit_raw_rows_per_parameter"],
        ),
        (
            "reviewer hidden-amount risk: baseline unpriced={base}, "
            "candidate unpriced={candidate} (tools.score.score API)"
        ).format(
            base=reviewer["baseline_unpriced"], candidate=reviewer["candidate_unpriced"]
        ),
    ]
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--threshold-tool", type=Path, default=DEFAULT_THRESHOLD_TOOL)
    parser.add_argument("--start-game", type=int, default=DEFAULT_START_GAME)
    parser.add_argument("--end-game", type=int, default=DEFAULT_END_GAME)
    parser.add_argument("--json", action="store_true", help="emit aggregate and per-item JSON")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        self_test()
        print("fit_rates self-test: ok")
        return 0
    try:
        ensure_readonly_guard()
        thresholds = load_thresholds(args.threshold_tool, args.db)
        features, identity = load_features(args.dataset)
        observations = join_observations(thresholds, features)
        result = evaluate(
            observations, features, args.db, args.start_game, args.end_game
        )
    except FitRatesError as exc:
        print(f"fit_rates: {exc}", file=sys.stderr)
        return 2

    output = {
        "read_only_guard": "C2F_READONLY=1",
        "threshold_source": "tools/thresholds.py --jsonl",
        "threshold_rows": len(thresholds),
        "feature_dataset": identity,
        **result,
    }
    if args.json:
        json.dump(output, sys.stdout, sort_keys=True, separators=(",", ":"))
        sys.stdout.write("\n")
    else:
        print(_human_summary(result, identity, len(thresholds)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
