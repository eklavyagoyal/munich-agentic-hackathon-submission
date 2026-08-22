#!/usr/bin/env python3
"""Leakage-free, partially identified valuation backtest.

The script is structurally offline: it reads the gitignored harvested JSONL and
SQLite transaction cache and writes a gitignored JSON report.  It imports no API
client and has no network or tournament-write path.

Because the feed reports issuer receipts rather than every submitted charge,
counterfactual scores are intervals.  The implementation never turns an unknown
threshold, acceptance limit, charge, or cap into a guessed point value.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sqlite3
import statistics
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from c2f.core.models import Case, Context, LineItem, Stage, Verdict
from c2f.estimate.interval_model import (
    DEFAULT_DATASET,
    IntervalValuationModel,
    dataset_identity,
)
from c2f.estimate.pricebook import fallback
from c2f.rules.engine import RuleEngine
from c2f.rules.loader import load_rules
from c2f.rules.protocol import BaseRule, RuleState


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "c2f.sqlite"
DEFAULT_OUTPUT = ROOT / "data" / "valuation_backtest.json"
CURVE_PRICES = (5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0)
CHARGE_MULTIPLIERS = (0.75, 1.0, 1.25, 1.5, 2.0, 3.0)
FOLD_RULE_NAME = "backtest_interval_valuation_prior"


class BacktestError(RuntimeError):
    pass


def git_revision() -> str:
    """Resolve the code snapshot or fail instead of emitting an orphan report."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise BacktestError(f"cannot resolve git revision: {type(exc).__name__}") from exc
    revision = result.stdout.strip()
    if result.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise BacktestError("cannot resolve a valid git revision")
    return revision


@dataclass(frozen=True)
class Bounds:
    lower: float
    upper: float

    def __post_init__(self) -> None:
        if not all(math.isfinite(value) and value >= 0 for value in (self.lower, self.upper)):
            raise ValueError("score bounds must be finite and nonnegative")
        if self.upper + 1e-9 < self.lower:
            raise ValueError(f"reversed score bounds [{self.lower}, {self.upper}]")

    def __add__(self, other: "Bounds") -> "Bounds":
        return Bounds(self.lower + other.lower, self.upper + other.upper)


@dataclass(frozen=True)
class ScoreBounds:
    income: Bounds
    cost: Bounds

    @property
    def net_lower(self) -> float:
        return self.income.lower - self.cost.upper

    @property
    def net_upper(self) -> float:
        return self.income.upper - self.cost.lower


@dataclass(frozen=True)
class Offer:
    issuer: str
    label: str  # fair | fraud | unknown
    payment: float


@dataclass(frozen=True)
class ReviewerLimit:
    reviewer: str
    lower: float
    upper: float | None


@dataclass(frozen=True)
class HandymanBounds:
    income: Bounds
    acceptance_lower: int
    acceptance_upper: int
    reviewers: int
    threshold_state: str


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp = Path(raw_temp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp.replace(path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def load_dataset(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise BacktestError(f"dataset not found: {path}")
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        raise BacktestError(f"invalid dataset: {type(exc).__name__}: {exc}") from exc
    if not rows:
        raise BacktestError("dataset is empty")
    keys = [(int(row["game_id"]), int(row["line_item_index"])) for row in rows]
    if len(keys) != len(set(keys)):
        raise BacktestError("dataset has duplicate game/item rows")
    return sorted(rows, key=lambda row: (row["game_id"], row["line_item_index"]))


def load_transactions(path: Path, games: set[int]) -> dict[int, list[dict[str, Any]]]:
    if not path.is_file():
        raise BacktestError(f"transaction database not found: {path}")
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute(
            "SELECT game_id,issuer,reviewer,line_item,accepted,amount "
            "FROM transactions ORDER BY game_id,issuer,reviewer,line_item"
        ).fetchall()
    except sqlite3.Error as exc:
        raise BacktestError(f"cannot read transactions: {exc}") from exc
    finally:
        connection.close()
    out: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for game_id, issuer, reviewer, item, accepted, amount in rows:
        game_id = int(game_id)
        if game_id not in games:
            continue
        value = float(amount)
        if not math.isfinite(value) or value < 0:
            raise BacktestError(f"game {game_id}: invalid transaction amount")
        out[game_id].append({
            "issuer": str(issuer),
            "reviewer": str(reviewer),
            "line_item_index": int(item),
            "accepted": bool(accepted),
            "amount": value,
        })
    missing = sorted(games - out.keys())
    if missing:
        raise BacktestError(f"transaction database is missing games {missing}")
    return dict(out)


def _item_rows(rows: Iterable[dict[str, Any]], item_index: int) -> list[dict[str, Any]]:
    return [row for row in rows if row["line_item_index"] == item_index]


def classify_offers(rows: list[dict[str, Any]], item_index: int) -> list[Offer]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _item_rows(rows, item_index):
        grouped[row["issuer"]].append(row)
    offers: list[Offer] = []
    for issuer, issuer_rows in sorted(grouped.items()):
        rejected = [row for row in issuer_rows if not row["accepted"]]
        payment = max((row["amount"] for row in issuer_rows), default=0.0)
        if not rejected:
            label = "unknown"
        else:
            states = {row["amount"] > 0 for row in rejected}
            if len(states) != 1:
                raise BacktestError(
                    f"item {item_index}: one issuer has contradictory rejection payments"
                )
            label = "fair" if True in states else "fraud"
            if label == "fair":
                exact = {row["amount"] for row in rejected}
                if len(exact) != 1 or payment != next(iter(exact)):
                    raise BacktestError(
                        f"item {item_index}: fair issuer payments are inconsistent"
                    )
        offers.append(Offer(issuer, label, payment))
    return offers


def reviewer_limits(
    rows: list[dict[str, Any]], item_index: int, *, exclude: str
) -> list[ReviewerLimit]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _item_rows(rows, item_index):
        if row["reviewer"] != exclude:
            grouped[row["reviewer"]].append(row)
    out: list[ReviewerLimit] = []
    for reviewer, reviewer_rows in sorted(grouped.items()):
        lower = max(
            (row["amount"] for row in reviewer_rows if row["accepted"]),
            default=0.0,
        )
        # A paid rejection is fair, so amount is the exact submitted charge and
        # rejection proves b < amount.  Unpaid fraud hides the charge and cannot
        # supply a numeric upper limit.
        exact_rejections = [
            row["amount"]
            for row in reviewer_rows
            if not row["accepted"] and row["amount"] > 0
        ]
        upper = min(exact_rejections) if exact_rejections else None
        if upper is not None and upper <= lower:
            raise BacktestError(
                f"item {item_index}: reviewer acceptance bounds contradict"
            )
        out.append(ReviewerLimit(reviewer, lower, upper))
    return out


def handyman_income_bounds(
    rows: list[dict[str, Any]],
    item_index: int,
    charge: float,
    threshold_lower: float,
    threshold_upper: float | None,
    *,
    team: str,
) -> HandymanBounds:
    if not math.isfinite(charge) or charge < 0:
        raise BacktestError("counterfactual charge must be finite and nonnegative")
    limits = reviewer_limits(rows, item_index, exclude=team)
    definitely_accept = sum(limit.lower >= charge for limit in limits)
    definitely_reject = sum(
        limit.upper is not None and charge >= limit.upper for limit in limits
    )
    possibly_accept = len(limits) - definitely_reject
    if definitely_accept > possibly_accept:
        raise BacktestError(f"item {item_index}: invalid acceptance bounds")

    if charge <= threshold_lower:
        exact = len(limits) * charge
        return HandymanBounds(
            Bounds(exact, exact), definitely_accept, possibly_accept, len(limits), "fair"
        )

    offers = classify_offers(rows, item_index)
    observed_fraud_payment = max(
        (offer.payment for offer in offers if offer.label == "fraud"),
        default=0.0,
    )
    cap_lower = max(4.0 * threshold_lower, observed_fraud_payment)
    fraud_income = Bounds(
        definitely_accept * min(charge, cap_lower),
        possibly_accept * charge,
    )
    if threshold_upper is not None and charge >= threshold_upper:
        return HandymanBounds(
            fraud_income, definitely_accept, possibly_accept, len(limits), "fraud"
        )

    fair_income = len(limits) * charge
    return HandymanBounds(
        Bounds(min(fair_income, fraud_income.lower), max(fair_income, fraud_income.upper)),
        definitely_accept,
        possibly_accept,
        len(limits),
        "threshold_unidentified",
    )


def insurer_cost_bounds(
    rows: list[dict[str, Any]], item_index: int, acceptance_limit: float, *, team: str
) -> Bounds:
    if not math.isfinite(acceptance_limit) or acceptance_limit < 0:
        raise BacktestError("counterfactual acceptance limit must be finite and nonnegative")
    total = Bounds(0.0, 0.0)
    for offer in classify_offers(rows, item_index):
        if offer.issuer == team:
            continue
        payment = offer.payment
        if offer.label == "fair":
            # Rejected-and-paid reveals the exact charge.
            cost = payment if payment <= acceptance_limit else 1.5 * payment
            bounds = Bounds(cost, cost)
        elif offer.label == "fraud":
            if payment > 0 and acceptance_limit < payment:
                bounds = Bounds(0.0, 0.0)  # a >= payment > b: definitely rejected
            elif payment > 0:
                bounds = Bounds(0.0, payment)  # capped a may still sit above b
            else:
                # The hidden charge either exceeds b (zero) or is accepted; in
                # the latter branch its fraud payment cannot exceed a <= b.
                bounds = Bounds(0.0, acceptance_limit)
        else:
            if payment == 0:
                bounds = Bounds(0.0, 0.0)
            elif acceptance_limit < payment:
                # Definitely rejected. Fair would cost 1.5a with a=payment;
                # fraud would cost zero.
                bounds = Bounds(0.0, 1.5 * payment)
            else:
                # Fair is accepted for payment; capped fraud may be accepted for
                # the same payment or rejected if its hidden a exceeds b.
                bounds = Bounds(0.0, payment)
        total += bounds
    return total


def actual_score(rows: list[dict[str, Any]], team: str) -> dict[str, float]:
    income = sum(row["amount"] for row in rows if row["issuer"] == team)
    cost = sum(
        row["amount"] if row["accepted"] else 1.5 * row["amount"]
        for row in rows
        if row["reviewer"] == team
    )
    return {"income": income, "cost": cost, "net": income - cost}


def make_item(row: dict[str, Any]) -> LineItem:
    features = row["features"]
    return LineItem(
        idx=int(row["line_item_index"]),
        description=str(features["description"]),
        qty=float(features["quantity"]),
        unit=str(features["unit"]),
    )


def make_case(game_id: int, rows: list[dict[str, Any]]) -> Case:
    if not rows:
        raise BacktestError(f"game {game_id}: no item rows")
    first = rows[0]["features"]
    policy = str(first["policy_text"])
    damage = str(first["damage_description"])
    if any(
        str(row["features"]["policy_text"]) != policy
        or str(row["features"]["damage_description"]) != damage
        for row in rows
    ):
        raise BacktestError(f"game {game_id}: inconsistent case context")
    return Case(
        case_id=str(game_id),
        policy_text=policy,
        damage_description=damage,
        items=tuple(make_item(row) for row in rows),
    )


class FoldIntervalPrior(BaseRule):
    """Leakage-free PRIOR whose model was fitted only on earlier games."""

    name = FOLD_RULE_NAME
    stage = Stage.PRIOR
    priority = 20
    author = "valuation-backtest"

    def __init__(self, model: IntervalValuationModel) -> None:
        self.model = model

    def apply(self, ctx: Context) -> Verdict | None:
        prediction = self.model.predict(ctx.item)
        if prediction.belief is None:
            return None
        zero_mass = prediction.posterior.zero_mass if prediction.posterior else 0.0
        return Verdict(
            belief=prediction.belief,
            note=(
                f"{prediction.reason}; posterior_zero_mass={zero_mass:.3f}; "
                "magnitude conditional on coverage"
            ),
        )


def build_engine(
    model: IntervalValuationModel | None = None,
) -> tuple[RuleEngine, list[dict[str, str]]]:
    """Reconstruct the live cold-path rule stack without evaluating SHADOW rules."""

    engine = RuleEngine(fallback)
    report = load_rules(engine, ROOT / "rules_user")
    if report.rejected:
        details = "; ".join(
            f"{entry['source']}:{entry['rule']}:{entry['error']}"
            for entry in report.rejected
        )
        raise BacktestError(f"rule loader rejected current rules: {details}")
    interval_state = next(
        (registered.state for registered in engine.rules
         if registered.name == "interval_valuation_prior"),
        None,
    )
    if interval_state is RuleState.ACTIVE:
        raise BacktestError(
            "interval_valuation_prior is ACTIVE; the walk-forward backtest refuses "
            "to load the all-games artifact into its baseline"
        )
    if model is not None:
        engine.register(
            FoldIntervalPrior(model),
            state=RuleState.ACTIVE,
            source="strict_game_forward",
        )
    engine.begin_round()
    return engine, engine.snapshot()


def evaluate_case(
    engine: RuleEngine, case: Case
) -> tuple[dict[int, tuple[float, float]], int]:
    """Evaluate exactly the active rules; live SHADOW rules cannot affect scores."""

    decisions: dict[int, tuple[float, float]] = {}
    model_predictions = 0
    for item in case.items:
        result = engine.evaluate(Context(case=case, item=item), include_shadow=False)
        unexpected_alerts = [
            alert
            for alert in result.alerts
            if alert.get("error") != "no PRIOR rule produced a belief"
        ]
        if unexpected_alerts:
            raise BacktestError(
                f"case {case.case_id} item {item.idx}: active rule failure: "
                f"{unexpected_alerts}"
            )
        decision = result.decision
        decisions[item.idx] = (decision.a, decision.b)
        if any(entry.get("rule") == FOLD_RULE_NAME for entry in decision.trace):
            model_predictions += 1
    return decisions, model_predictions


def score_decisions(
    item_rows: list[dict[str, Any]],
    transactions: list[dict[str, Any]],
    decisions: dict[int, tuple[float, float]],
    *,
    team: str,
) -> ScoreBounds:
    income = Bounds(0.0, 0.0)
    cost = Bounds(0.0, 0.0)
    for row in item_rows:
        index = int(row["line_item_index"])
        charge, limit = decisions[index]
        label = row["label"]
        handyman = handyman_income_bounds(
            transactions,
            index,
            charge,
            float(label["lower"]),
            None if label["upper"] is None else float(label["upper"]),
            team=team,
        )
        income += handyman.income
        cost += insurer_cost_bounds(transactions, index, limit, team=team)
    return ScoreBounds(income, cost)


def _rounded_score(score: ScoreBounds) -> dict[str, Any]:
    return {
        "income": {"lower": round(score.income.lower, 2), "upper": round(score.income.upper, 2)},
        "cost": {"lower": round(score.cost.lower, 2), "upper": round(score.cost.upper, 2)},
        "net": {"lower": round(score.net_lower, 2), "upper": round(score.net_upper, 2)},
    }


def _sum_scores(scores: Iterable[ScoreBounds]) -> ScoreBounds:
    total = ScoreBounds(Bounds(0, 0), Bounds(0, 0))
    for score in scores:
        total = ScoreBounds(total.income + score.income, total.cost + score.cost)
    return total


def _percentile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("percentile of empty sequence")
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def bootstrap_lower_bound(
    differences: list[float], *, samples: int, seed: int = 20260822
) -> float | None:
    if not differences or samples < 1:
        return None
    rng = random.Random(seed)
    means = [
        sum(rng.choice(differences) for _ in differences) / len(differences)
        for _ in range(samples)
    ]
    return _percentile(means, 0.025)


def acceptance_curve(
    games: dict[int, list[dict[str, Any]]], item_rows: list[dict[str, Any]], *, team: str
) -> list[dict[str, float]]:
    by_game: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in item_rows:
        by_game[int(row["game_id"])].append(row)
    limits: list[ReviewerLimit] = []
    for game_id, rows in by_game.items():
        for row in rows:
            limits.extend(reviewer_limits(
                games[game_id], int(row["line_item_index"]), exclude=team
            ))
    denominator = len(limits)
    if not denominator:
        return []
    return [
        {
            "price": price,
            "acceptance_lower": sum(limit.lower >= price for limit in limits) / denominator,
            "acceptance_upper": sum(
                limit.upper is None or price < limit.upper for limit in limits
            ) / denominator,
            "reviewer_item_pairs": denominator,
        }
        for price in CURVE_PRICES
    ]


def charge_policy_sweep(
    games: dict[int, list[dict[str, Any]]],
    item_rows: list[dict[str, Any]],
    baseline_decisions: dict[tuple[int, int], tuple[float, float]],
    *,
    team: str,
    min_game: int,
) -> list[dict[str, Any]]:
    eligible = [row for row in item_rows if int(row["game_id"]) >= min_game]
    out: list[dict[str, Any]] = []
    for multiplier in CHARGE_MULTIPLIERS:
        income = Bounds(0, 0)
        by_game: dict[str, dict[str, float]] = {}
        for game_id in sorted({int(row["game_id"]) for row in eligible}):
            game_income = Bounds(0, 0)
            for row in (row for row in eligible if int(row["game_id"]) == game_id):
                item = make_item(row)
                try:
                    base_charge, _ = baseline_decisions[(game_id, item.idx)]
                except KeyError as exc:
                    raise BacktestError(
                        f"game {game_id} item {item.idx}: missing baseline decision"
                    ) from exc
                label = row["label"]
                result = handyman_income_bounds(
                    games[game_id],
                    item.idx,
                    base_charge * multiplier,
                    float(label["lower"]),
                    None if label["upper"] is None else float(label["upper"]),
                    team=team,
                )
                game_income += result.income
            income += game_income
            by_game[str(game_id)] = {
                "lower": round(game_income.lower, 2),
                "upper": round(game_income.upper, 2),
            }
        out.append({
            "multiplier": multiplier,
            "items": len(eligible),
            "income_lower": round(income.lower, 2),
            "income_upper": round(income.upper, 2),
            "by_game": by_game,
        })
    return out


def run_backtest(
    dataset: list[dict[str, Any]],
    transactions: dict[int, list[dict[str, Any]]],
    *,
    team: str,
    bootstrap_samples: int,
    charge_min_game: int,
) -> dict[str, Any]:
    games = sorted({int(row["game_id"]) for row in dataset})
    by_game = {
        game: [row for row in dataset if int(row["game_id"]) == game]
        for game in games
    }
    per_game: list[dict[str, Any]] = []
    book_scores: list[ScoreBounds] = []
    model_scores: list[ScoreBounds] = []
    actual_scores: list[dict[str, float]] = []
    heldout_differences: list[float] = []
    heldout_games = 0
    heldout_predictions = 0
    baseline_decisions: dict[tuple[int, int], tuple[float, float]] = {}
    baseline_snapshot: list[dict[str, str]] | None = None

    for game in games:
        test_rows = by_game[game]
        train_rows = [row for prior in games if prior < game for row in by_game[prior]]
        model = IntervalValuationModel.fit(train_rows) if train_rows else None
        case = make_case(game, test_rows)
        baseline_engine, snapshot = build_engine()
        candidate_engine, candidate_snapshot = build_engine(model)
        candidate_baseline_snapshot = [
            entry for entry in candidate_snapshot if entry["name"] != FOLD_RULE_NAME
        ]
        if candidate_baseline_snapshot != snapshot:
            raise BacktestError("active rule snapshot changed between candidates")
        if baseline_snapshot is None:
            baseline_snapshot = snapshot
        elif baseline_snapshot != snapshot:
            raise BacktestError("active rule snapshot changed during the backtest")
        book_decisions, _ = evaluate_case(baseline_engine, case)
        model_decisions, model_predictions = evaluate_case(candidate_engine, case)
        baseline_decisions.update(
            {(game, index): decision for index, decision in book_decisions.items()}
        )

        book = score_decisions(test_rows, transactions[game], book_decisions, team=team)
        learned = score_decisions(test_rows, transactions[game], model_decisions, team=team)
        actual = actual_score(transactions[game], team)
        book_scores.append(book)
        model_scores.append(learned)
        actual_scores.append(actual)
        if model_predictions:
            heldout_games += 1
            heldout_predictions += model_predictions
            heldout_differences.append(learned.net_lower - book.net_upper)
        per_game.append({
            "game_id": game,
            "items": len(test_rows),
            "training_games": sum(prior < game for prior in games),
            "model_predictions": model_predictions,
            "fallback_predictions": len(test_rows) - model_predictions,
            "actual": {key: round(value, 2) for key, value in actual.items()},
            "pricebook": _rounded_score(book),
            "model": _rounded_score(learned),
        })

    total_book = _sum_scores(book_scores)
    total_model = _sum_scores(model_scores)
    total_actual = {
        key: sum(score[key] for score in actual_scores) for key in ("income", "cost", "net")
    }
    bootstrap_lower = bootstrap_lower_bound(
        heldout_differences, samples=bootstrap_samples
    )
    enough_evidence = heldout_games >= 5 and heldout_predictions >= 30
    conservative_improvement = total_model.net_lower - total_book.net_upper
    insurer_safe = total_model.cost.upper <= total_book.cost.lower * 1.05
    failed_gates: list[str] = []
    if not enough_evidence:
        failed_gates.append("insufficient_holdout")
    if conservative_improvement <= 0:
        failed_gates.append("conservative_net_not_better")
    if bootstrap_lower is None or bootstrap_lower <= 0:
        failed_gates.append("bootstrap_lower_not_positive")
    if not insurer_safe:
        failed_gates.append("insurer_cost_gate_failed")
    promotion = {
        "eligible": bool(
            enough_evidence
            and conservative_improvement > 0
            and bootstrap_lower is not None
            and bootstrap_lower > 0
            and insurer_safe
        ),
        "heldout_games": heldout_games,
        "heldout_predictions": heldout_predictions,
        "minimum_heldout_games": 5,
        "minimum_heldout_predictions": 30,
        "conservative_total_net_improvement": round(conservative_improvement, 2),
        "paired_game_bootstrap_95_lower": (
            None if bootstrap_lower is None else round(bootstrap_lower, 2)
        ),
        "insurer_cost_gate": insurer_safe,
        "reason": "all_pre_registered_gates_pass" if not failed_gates else ",".join(failed_gates),
    }
    charge_sweep = charge_policy_sweep(
        transactions,
        dataset,
        baseline_decisions,
        team=team,
        min_game=charge_min_game,
    )
    baseline_charge = next(row for row in charge_sweep if row["multiplier"] == 1.0)
    maximin_charge = max(charge_sweep, key=lambda row: row["income_lower"])
    improved_games = sum(
        bounds["lower"] > baseline_charge["by_game"][game]["lower"]
        for game, bounds in maximin_charge["by_game"].items()
    )
    return {
        "method": {
            "split": "strict game-forward; train games < test game",
            "counterfactual": "partial-identification bounds; no point imputation",
            "bootstrap_samples": bootstrap_samples,
            "baseline": "active rules_user snapshot; empty History; SHADOW excluded",
            "baseline_rule_snapshot": baseline_snapshot or [],
        },
        "games": per_game,
        "totals": {
            "actual": {key: round(value, 2) for key, value in total_actual.items()},
            "pricebook": _rounded_score(total_book),
            "model": _rounded_score(total_model),
        },
        "variance_across_games": {
            "actual_net": statistics.variance([score["net"] for score in actual_scores])
            if len(actual_scores) > 1 else 0.0,
            "pricebook_net_lower": statistics.variance([score.net_lower for score in book_scores])
            if len(book_scores) > 1 else 0.0,
            "pricebook_net_upper": statistics.variance([score.net_upper for score in book_scores])
            if len(book_scores) > 1 else 0.0,
            "model_net_lower": statistics.variance([score.net_lower for score in model_scores])
            if len(model_scores) > 1 else 0.0,
            "model_net_upper": statistics.variance([score.net_upper for score in model_scores])
            if len(model_scores) > 1 else 0.0,
        },
        "promotion": promotion,
        "acceptance_curve": acceptance_curve(transactions, dataset, team=team),
        "charge_policy": {
            "minimum_game": charge_min_game,
            "sweep": charge_sweep,
            "maximin_multiplier": maximin_charge["multiplier"],
            "maximin_lower_gain_vs_current": round(
                maximin_charge["income_lower"] - baseline_charge["income_lower"], 2
            ),
            "games_with_higher_lower_bound": improved_games,
            "games_evaluated": len(maximin_charge["by_game"]),
            "interval_dominates_current": (
                maximin_charge["income_lower"] > baseline_charge["income_upper"]
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="valuation_backtest")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--team", default="Oasis")
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    parser.add_argument("--charge-min-game", type=int, default=3,
                        help="exclude broken-field games 1-2 from charge-policy sweep")
    args = parser.parse_args()
    if args.bootstrap_samples < 1 or not args.team.strip() or args.charge_min_game < 1:
        parser.error("invalid bootstrap/team/min-game argument")
    try:
        dataset = load_dataset(args.dataset)
        games = {int(row["game_id"]) for row in dataset}
        transactions = load_transactions(args.db, games)
        report = run_backtest(
            dataset,
            transactions,
            team=args.team.strip(),
            bootstrap_samples=args.bootstrap_samples,
            charge_min_game=args.charge_min_game,
        )
        report["snapshot"] = {
            **dataset_identity(args.dataset, dataset),
            "git_revision": git_revision(),
        }
        _atomic_json(args.output, report)
    except (BacktestError, OSError, ValueError, sqlite3.Error) as exc:
        print(f"backtest failed: {type(exc).__name__}: {exc}")
        return 1

    totals = report["totals"]
    promotion = report["promotion"]
    print(f"games: {len(report['games'])}")
    print(
        f"actual net: {totals['actual']['net']:.2f}; "
        f"pricebook net: [{totals['pricebook']['net']['lower']:.2f}, "
        f"{totals['pricebook']['net']['upper']:.2f}]; "
        f"model net: [{totals['model']['net']['lower']:.2f}, "
        f"{totals['model']['net']['upper']:.2f}]"
    )
    print(
        f"held out: {promotion['heldout_games']} games / "
        f"{promotion['heldout_predictions']} model predictions"
    )
    print(f"promotion eligible: {promotion['eligible']} ({promotion['reason']})")
    print(f"report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
