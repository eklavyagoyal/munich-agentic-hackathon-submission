"""Offline interval-censored posterior for per-line-item fair thresholds.

The tournament never reveals ``t``.  ``tools/harvest.py`` supplies one interval
``[lower, upper)`` per line item.  This module fits a discrete non-parametric
maximum-likelihood distribution over the per-unit rate using an EM update.  It
has no third-party numerical dependency and performs no network I/O.

The rich posterior may contain a point mass at zero.  The existing rule engine
accepts a log-normal-ish ``Belief``, so prediction projects the posterior's
median and one-third quantile into that shape.  If the projection is impossible
or sensitive to the unidentified zero-mass prior, prediction abstains.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Any, Iterable

from c2f.core.models import Belief, LineItem
from c2f.estimate.pricebook import unit_class


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "data" / "harvest" / "line_items.jsonl"
DEFAULT_ARTIFACT = ROOT / "data" / "valuation_model.json"
MAX_DATASET_BYTES = 128 * 1024 * 1024
ARTIFACT_VERSION = 2
MIN_INFORMATIVE_ROWS = 6
MIN_GAMES = 3
GRID_POINTS = 96
EM_ITERATIONS = 500
EM_TOLERANCE = 1e-10
PRIOR_STRENGTH = 2.0
ZERO_PRIORS = (0.05, 0.20, 0.50)
CENTRAL_ZERO_PRIOR = 0.20

_NORMAL = NormalDist()


class ModelError(RuntimeError):
    pass


@dataclass(frozen=True)
class Interval:
    game_id: int
    quantity: float
    lower_rate: float
    upper_rate: float | None

    @property
    def informative(self) -> bool:
        return self.lower_rate > 0 or self.upper_rate is not None


@dataclass(frozen=True)
class Posterior:
    """A discrete posterior over the gross total threshold in EUR."""

    support: tuple[float, ...]
    probabilities: tuple[float, ...]
    source: str

    def __post_init__(self) -> None:
        if not self.support or len(self.support) != len(self.probabilities):
            raise ValueError("posterior support/probability shape mismatch")
        if any(not math.isfinite(value) or value < 0 for value in self.support):
            raise ValueError("posterior support must be finite and nonnegative")
        if any(not math.isfinite(value) or value < 0 for value in self.probabilities):
            raise ValueError("posterior probabilities must be finite and nonnegative")
        if not math.isclose(sum(self.probabilities), 1.0, abs_tol=1e-7):
            raise ValueError("posterior probabilities must sum to one")

    @property
    def zero_mass(self) -> float:
        return sum(
            probability
            for value, probability in zip(self.support, self.probabilities)
            if value == 0
        )

    def quantile(self, q: float) -> float:
        if not 0 < q < 1:
            raise ValueError("posterior quantile must be in (0,1)")
        cumulative = 0.0
        for value, probability in zip(self.support, self.probabilities):
            cumulative += probability
            if cumulative + 1e-15 >= q:
                return value
        return self.support[-1]


@dataclass(frozen=True)
class Prediction:
    posterior: Posterior | None
    belief: Belief | None
    reason: str

    @property
    def abstained(self) -> bool:
        return self.belief is None


def _parse_rows_text(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ModelError(f"dataset line {line_no} is invalid JSON") from exc
        if not isinstance(row, dict):
            raise ModelError(f"dataset line {line_no} is not an object")
        rows.append(row)
    if not rows:
        raise ModelError("dataset is empty")
    return rows


def load_rows(path: Path = DEFAULT_DATASET) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ModelError(f"dataset not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ModelError(f"cannot read dataset: {type(exc).__name__}") from exc
    return _parse_rows_text(text)


def dataset_identity(path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return non-sensitive identity metadata for a parsed training snapshot."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ModelError(f"cannot read dataset for identity: {type(exc).__name__}") from exc
    size = len(raw)
    if size <= 0 or size > MAX_DATASET_BYTES:
        raise ModelError("dataset size is outside the supported range")
    try:
        current_rows = _parse_rows_text(raw.decode("utf-8"))
        games = [int(row["game_id"]) for row in rows]
    except (UnicodeError, KeyError, TypeError, ValueError) as exc:
        raise ModelError(f"cannot identify dataset: {type(exc).__name__}") from exc
    if current_rows != rows:
        raise ModelError("dataset changed after it was loaded")
    if not games:
        raise ModelError("cannot identify an empty dataset")
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": size,
        "rows": len(rows),
        "games": len(set(games)),
        "max_game": max(games),
    }


def _row_interval(row: dict[str, Any]) -> tuple[str | None, Interval]:
    try:
        features, label = row["features"], row["label"]
        unit = str(features["unit_class"])
        quantity = float(features["quantity"])
        lower = float(label["lower"])
        raw_upper = label["upper"]
        upper = None if raw_upper is None else float(raw_upper)
        game_id = int(row["game_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ModelError("dataset row has an invalid feature/label shape") from exc
    if not math.isfinite(quantity) or quantity <= 0:
        raise ModelError("dataset quantity must be finite and positive")
    if not math.isfinite(lower) or lower < 0:
        raise ModelError("dataset lower bound must be finite and nonnegative")
    if upper is not None and (not math.isfinite(upper) or upper <= lower):
        raise ModelError("dataset upper bound must be finite and above lower")
    return unit or None, Interval(
        game_id=game_id,
        quantity=quantity,
        lower_rate=lower / quantity,
        upper_rate=None if upper is None else upper / quantity,
    )


def _log_grid(intervals: list[Interval]) -> list[float]:
    endpoints = [
        value
        for interval in intervals
        for value in (interval.lower_rate, interval.upper_rate)
        if value is not None and value > 0
    ]
    if not endpoints:
        raise ModelError("cannot build a rate grid without a positive endpoint")
    low = max(min(endpoints) / 2.0, 0.01)
    high = max(max(endpoints) * 2.0, low * 10.0)
    log_low, log_high = math.log(low), math.log(high)
    support = {0.0}
    for index in range(GRID_POINTS):
        fraction = index / (GRID_POINTS - 1)
        support.add(math.exp(log_low + fraction * (log_high - log_low)))
    for interval in intervals:
        if interval.lower_rate > 0:
            support.add(interval.lower_rate)
        if interval.upper_rate is not None:
            just_below = math.nextafter(interval.upper_rate, 0.0)
            if just_below > interval.lower_rate:
                support.add(just_below)
            midpoint = (
                interval.upper_rate / 2.0
                if interval.lower_rate == 0
                else math.sqrt(interval.lower_rate * interval.upper_rate)
            )
            if interval.lower_rate <= midpoint < interval.upper_rate:
                support.add(midpoint)
    return sorted(support)


def _prior_probabilities(grid: list[float], zero_mass: float) -> list[float]:
    positive = grid[1:]
    if not positive or grid[0] != 0:
        raise ModelError("rate grid must start with zero and contain positive support")
    logs = [math.log(value) for value in positive]
    widths: list[float] = []
    for index, value in enumerate(logs):
        left = logs[index - 1] if index else value - (logs[1] - value if len(logs) > 1 else 1)
        right = logs[index + 1] if index + 1 < len(logs) else value + (value - left)
        widths.append(max((right - left) / 2.0, 1e-12))
    scale = (1.0 - zero_mass) / sum(widths)
    return [zero_mass] + [width * scale for width in widths]


def _compatible(value: float, interval: Interval) -> bool:
    return value >= interval.lower_rate and (
        interval.upper_rate is None or value < interval.upper_rate
    )


def _fit_em(
    grid: list[float], intervals: list[Interval], zero_prior: float
) -> tuple[list[float], float, int]:
    observations = [interval for interval in intervals if interval.informative]
    if not observations:
        raise ModelError("cohort has no informative intervals")
    prior = _prior_probabilities(grid, zero_prior)
    probabilities = list(prior)
    last_likelihood = -math.inf
    per_game = Counter(interval.game_id for interval in observations)
    weights = [1.0 / per_game[interval.game_id] for interval in observations]
    total_weight = sum(weights)
    for iteration in range(1, EM_ITERATIONS + 1):
        expected = [0.0] * len(grid)
        likelihood = 0.0
        for interval, weight in zip(observations, weights):
            indices = [
                index for index, value in enumerate(grid)
                if _compatible(value, interval)
            ]
            denominator = sum(probabilities[index] for index in indices)
            if not indices or denominator <= 0:
                raise ModelError("rate grid has no probability inside an observed interval")
            likelihood += weight * math.log(denominator)
            for index in indices:
                expected[index] += weight * probabilities[index] / denominator
        denominator = total_weight + PRIOR_STRENGTH
        updated = [
            (count + PRIOR_STRENGTH * base) / denominator
            for count, base in zip(expected, prior)
        ]
        movement = max(abs(new - old) for new, old in zip(updated, probabilities))
        probabilities = updated
        if movement < EM_TOLERANCE:
            return probabilities, likelihood, iteration
        last_likelihood = likelihood
    return probabilities, last_likelihood, EM_ITERATIONS


def _lognormal_likelihood(intervals: list[Interval], mu: float, sigma: float) -> float:
    observations = [interval for interval in intervals if interval.informative]
    per_game = Counter(interval.game_id for interval in observations)
    likelihood = 0.0
    for interval in observations:
        weight = 1.0 / per_game[interval.game_id]
        lower_cdf = (
            0.0
            if interval.lower_rate <= 0
            else _NORMAL.cdf((math.log(interval.lower_rate) - mu) / sigma)
        )
        upper_cdf = (
            1.0
            if interval.upper_rate is None
            else _NORMAL.cdf((math.log(interval.upper_rate) - mu) / sigma)
        )
        probability = upper_cdf - lower_cdf
        if probability <= 0 or not math.isfinite(probability):
            return -math.inf
        likelihood += weight * math.log(probability)
    return likelihood


def _fit_positive_lognormal(intervals: list[Interval]) -> tuple[float, float, float]:
    """Fit ``log(rate) ~ Normal(mu, sigma)`` conditional on ``rate > 0``.

    A deterministic coarse-to-fine grid keeps the offline model dependency-free.
    Each game receives total weight one, regardless of its invoice item count.
    """

    observations = [interval for interval in intervals if interval.informative]
    endpoints = [
        value
        for interval in observations
        for value in (interval.lower_rate, interval.upper_rate)
        if value is not None and value > 0
    ]
    if not endpoints:
        raise ModelError("cannot fit a positive distribution without endpoints")
    mu_low = math.log(min(endpoints)) - math.log(4.0)
    mu_high = math.log(max(endpoints)) + math.log(4.0)
    best_mu = (mu_low + mu_high) / 2.0
    best_sigma = 1.0
    best_likelihood = -math.inf
    previous_sigma_step = (3.0 - 0.10) / 30.0

    # Broad first pass, then deterministic local refinement.  Sigma respects the
    # Belief contract by construction instead of clipping an incompatible fit.
    for refinement in range(6):
        mu_step = (mu_high - mu_low) / 40.0
        sigma_low = 0.10 if refinement == 0 else max(
            0.10, best_sigma - previous_sigma_step * 4
        )
        sigma_high = 3.0 if refinement == 0 else min(
            3.0, best_sigma + previous_sigma_step * 4
        )
        sigma_step = max((sigma_high - sigma_low) / 30.0, 1e-5)
        for mu_index in range(41):
            mu = mu_low + mu_index * mu_step
            for sigma_index in range(31):
                sigma = min(sigma_high, sigma_low + sigma_index * sigma_step)
                likelihood = _lognormal_likelihood(observations, mu, sigma)
                if likelihood > best_likelihood:
                    best_mu, best_sigma, best_likelihood = mu, sigma, likelihood
        mu_low, mu_high = best_mu - mu_step * 4, best_mu + mu_step * 4
        previous_sigma_step = sigma_step
    return best_mu, best_sigma, best_likelihood


def _posterior_from(cohort: dict[str, Any], quantity: float, variant: str) -> Posterior:
    support = tuple(float(rate) * quantity for rate in cohort["support_rates"])
    probabilities = tuple(float(value) for value in cohort["variants"][variant]["probabilities"])
    return Posterior(support=support, probabilities=probabilities,
                     source=f"interval:{cohort['unit']}")


class IntervalValuationModel:
    def __init__(self, artifact: dict[str, Any]) -> None:
        self.artifact = self._validate_artifact(artifact)

    @classmethod
    def fit(cls, rows: Iterable[dict[str, Any]]) -> "IntervalValuationModel":
        grouped: dict[str, list[Interval]] = {}
        total_rows = 0
        excluded_rows: Counter[str] = Counter()
        for row in rows:
            unit, interval = _row_interval(row)
            total_rows += 1
            if unit is None:
                excluded_rows["unrecognised_unit"] += 1
                continue
            grouped.setdefault(unit, []).append(interval)

        cohorts: dict[str, dict[str, Any]] = {}
        skipped: dict[str, str] = {}
        for unit, all_intervals in sorted(grouped.items()):
            informative = [interval for interval in all_intervals if interval.informative]
            games = sorted({interval.game_id for interval in informative})
            if len(informative) < MIN_INFORMATIVE_ROWS:
                skipped[unit] = f"informative_rows<{MIN_INFORMATIVE_ROWS}"
                continue
            if len(games) < MIN_GAMES:
                skipped[unit] = f"games<{MIN_GAMES}"
                continue
            grid = _log_grid(informative)
            positive_mu, positive_sigma, positive_likelihood = _fit_positive_lognormal(
                informative
            )
            variants: dict[str, dict[str, Any]] = {}
            for zero_prior in ZERO_PRIORS:
                probabilities, likelihood, iterations = _fit_em(
                    grid, informative, zero_prior
                )
                variants[f"{zero_prior:.2f}"] = {
                    "probabilities": probabilities,
                    "log_likelihood": likelihood,
                    "iterations": iterations,
                }
            cohorts[unit] = {
                "unit": unit,
                "rows": len(all_intervals),
                "informative_rows": len(informative),
                "games": games,
                "quantity_min": min(interval.quantity for interval in informative),
                "quantity_max": max(interval.quantity for interval in informative),
                "support_rates": grid,
                "variants": variants,
                "positive_lognormal": {
                    "mu": positive_mu,
                    "sigma": positive_sigma,
                    "log_likelihood": positive_likelihood,
                },
            }
        artifact = {
            "artifact_version": ARTIFACT_VERSION,
            "training_rows": total_rows,
            "eligible_unit_rows": total_rows - sum(excluded_rows.values()),
            "excluded_rows_by_reason": dict(sorted(excluded_rows.items())),
            "config": {
                "min_informative_rows": MIN_INFORMATIVE_ROWS,
                "min_games": MIN_GAMES,
                "prior_strength": PRIOR_STRENGTH,
                "zero_priors": list(ZERO_PRIORS),
                "central_zero_prior": CENTRAL_ZERO_PRIOR,
            },
            "cohorts": cohorts,
            "skipped_cohorts": skipped,
        }
        return cls(artifact)

    @staticmethod
    def _validate_artifact(raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict) or raw.get("artifact_version") != ARTIFACT_VERSION:
            raise ModelError("unsupported valuation-model artifact")
        cohorts = raw.get("cohorts")
        if not isinstance(cohorts, dict):
            raise ModelError("valuation-model artifact has no cohorts object")
        central = f"{CENTRAL_ZERO_PRIOR:.2f}"
        for name, cohort in cohorts.items():
            if not isinstance(name, str) or not isinstance(cohort, dict):
                raise ModelError("invalid cohort entry")
            try:
                support = [float(value) for value in cohort["support_rates"]]
                variants = cohort["variants"]
                quantity_min = float(cohort["quantity_min"])
                quantity_max = float(cohort["quantity_max"])
                positive = cohort["positive_lognormal"]
                positive_mu = float(positive["mu"])
                positive_sigma = float(positive["sigma"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ModelError(f"cohort {name!r} has invalid fields") from exc
            if not support or support != sorted(support) or support[0] != 0:
                raise ModelError(f"cohort {name!r} has invalid support")
            if not 0 < quantity_min <= quantity_max:
                raise ModelError(f"cohort {name!r} has invalid quantity range")
            if not math.isfinite(positive_mu) or not (0.10 <= positive_sigma <= 3.0001):
                raise ModelError(f"cohort {name!r} has invalid positive lognormal")
            if not isinstance(variants, dict) or central not in variants:
                raise ModelError(f"cohort {name!r} lacks central sensitivity variant")
            for variant in variants.values():
                probabilities = variant.get("probabilities") if isinstance(variant, dict) else None
                if not isinstance(probabilities, list) or len(probabilities) != len(support):
                    raise ModelError(f"cohort {name!r} probability shape mismatch")
                if any(not math.isfinite(float(value)) or float(value) < 0
                       for value in probabilities):
                    raise ModelError(f"cohort {name!r} has invalid probabilities")
                if not math.isclose(sum(float(value) for value in probabilities),
                                    1.0, abs_tol=1e-7):
                    raise ModelError(f"cohort {name!r} probabilities do not sum to one")
        return raw

    def predict(self, item: LineItem) -> Prediction:
        unit = unit_class(item.unit)
        if not unit:
            return Prediction(None, None, "unrecognised_unit")
        cohort = self.artifact["cohorts"].get(unit)
        if cohort is None:
            reason = self.artifact.get("skipped_cohorts", {}).get(unit, "unseen_unit")
            return Prediction(None, None, reason)
        quantity = float(item.qty)
        if not math.isfinite(quantity) or quantity <= 0:
            return Prediction(None, None, "invalid_quantity")
        if not cohort["quantity_min"] <= quantity <= cohort["quantity_max"]:
            return Prediction(None, None, "quantity_out_of_distribution")

        central_key = f"{CENTRAL_ZERO_PRIOR:.2f}"
        central = _posterior_from(cohort, quantity, central_key)
        positive = cohort["positive_lognormal"]
        sigma = float(positive["sigma"])
        median = math.exp(float(positive["mu"])) * quantity
        belief = Belief(
            median=median,
            sigma=sigma,
            source=f"interval-positive:{unit}:n={cohort['informative_rows']}",
        )
        return Prediction(central, belief, "ok_conditional_on_coverage")

    def save(self, path: Path = DEFAULT_ARTIFACT) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temp = Path(raw_tmp)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self.artifact, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            temp.replace(path)
        except BaseException:
            temp.unlink(missing_ok=True)
            raise

    @classmethod
    def load(cls, path: Path = DEFAULT_ARTIFACT) -> "IntervalValuationModel":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelError(f"cannot load model artifact: {type(exc).__name__}: {exc}") from exc
        return cls(raw)


def load_optional(
    path: Path = DEFAULT_ARTIFACT,
) -> tuple[IntervalValuationModel | None, str | None]:
    """Cold-path loader that preserves the reason for an unavailable model."""

    try:
        return IntervalValuationModel.load(path), None
    except ModelError as exc:
        return None, str(exc)
