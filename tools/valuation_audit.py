#!/usr/bin/env python3
"""Aggregate-only evidence for the valuation report; never prints claim text."""
from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools.valuation_backtest import (
    BacktestError,
    DEFAULT_DB,
    DEFAULT_OUTPUT as DEFAULT_BACKTEST,
    _atomic_json,
    classify_offers,
    load_dataset,
    load_transactions,
)


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AUDIT = ROOT / "data" / "valuation_audit.json"

ENGLISH_MARKERS = {
    "remove", "replace", "repair", "install", "installation", "cleaning",
    "drying", "painting", "paint", "labour", "labor", "work", "rental",
    "disposal", "travel", "material", "ceiling", "floor", "wall", "door",
}
GERMAN_MARKERS = {
    "entfernen", "erneuern", "reparatur", "einbau", "montage", "reinigung",
    "trocknung", "maler", "arbeit", "miete", "entsorgung", "anfahrt",
    "material", "decke", "boden", "wand", "tür", "tuer",
}


def language_heuristic(text: str) -> str:
    words = set(re.findall(r"[a-zA-ZäöüÄÖÜß]+", text.lower()))
    english = len(words & ENGLISH_MARKERS)
    german = len(words & GERMAN_MARKERS)
    if english > german and english:
        return "english"
    if german > english and german:
        return "german"
    if english == german and english:
        return "mixed"
    return "unresolved"


def _median(values: list[float]) -> float | None:
    return None if not values else statistics.median(values)


def build_audit(
    dataset: list[dict[str, Any]],
    transactions: dict[int, list[dict[str, Any]]],
    backtest: dict[str, Any] | None,
) -> dict[str, Any]:
    games = sorted({int(row["game_id"]) for row in dataset})
    by_game: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in dataset:
        by_game[int(row["game_id"])].append(row)

    finite_widths: list[float] = []
    positive_widths: list[float] = []
    per_unit_widths: dict[str, list[float]] = defaultdict(list)
    for row in dataset:
        lower, upper = float(row["label"]["lower"]), row["label"]["upper"]
        if upper is None:
            continue
        width = float(upper) - lower
        finite_widths.append(width)
        if lower > 0:
            positive_widths.append(width)
        quantity = float(row["features"]["quantity"])
        per_unit_widths[str(row["features"]["unit_class"])].append(width / quantity)

    language_by_game = {
        str(game): dict(sorted(Counter(
            language_heuristic(str(row["features"]["description"]))
            for row in rows
        ).items()))
        for game, rows in sorted(by_game.items())
    }
    first_per_game = [by_game[game][0] for game in games]
    image_cases = sum(bool(row["features"]["image_metadata"]) for row in first_per_game)
    readable_images = sum(
        any(image.get("width") and image.get("height")
            for image in row["features"]["image_metadata"])
        for row in first_per_game
    )

    offers_above_four_upper = 0
    priced_fraud_offers = 0
    for row in dataset:
        upper = row["label"]["upper"]
        if upper is None:
            continue
        for offer in classify_offers(
            transactions[int(row["game_id"])], int(row["line_item_index"])
        ):
            if offer.label == "fraud" and offer.payment > 0:
                priced_fraud_offers += 1
                if offer.payment >= 4.0 * float(upper):
                    offers_above_four_upper += 1

    actual_periods: dict[str, Any] = {}
    if backtest:
        for name, selected in (
            ("games_1_2", [game for game in backtest["games"] if game["game_id"] <= 2]),
            ("games_3_onward", [game for game in backtest["games"] if game["game_id"] >= 3]),
        ):
            items = sum(game["items"] for game in selected)
            totals = {
                key: sum(float(game["actual"][key]) for game in selected)
                for key in ("income", "cost", "net")
            }
            actual_periods[name] = {
                "games": len(selected),
                "items": items,
                **{key: round(value, 2) for key, value in totals.items()},
                **{f"{key}_per_item": round(value / items, 2) if items else None
                   for key, value in totals.items()},
            }

    return {
        "games": len(games),
        "line_items": len(dataset),
        "units": dict(sorted(Counter(
            str(row["features"]["unit_class"]) for row in dataset
        ).items())),
        "pricebook": {
            "specific_matches": sum(
                row["features"]["trade"] != "unknown" for row in dataset
            ),
            "unknown": sum(row["features"]["trade"] == "unknown" for row in dataset),
            "by_game": {
                str(game): {
                    "items": len(rows),
                    "specific_matches": sum(
                        row["features"]["trade"] != "unknown" for row in rows
                    ),
                }
                for game, rows in sorted(by_game.items())
            },
        },
        "labels": {
            "finite_upper": sum(row["label"]["upper"] is not None for row in dataset),
            "right_censored": sum(row["label"]["upper"] is None for row in dataset),
            "positive_lower": sum(float(row["label"]["lower"]) > 0 for row in dataset),
            "fair_issuer_labels": sum(int(row["label"]["fair_issuers"]) for row in dataset),
            "fraud_issuer_labels": sum(int(row["label"]["fraud_issuers"]) for row in dataset),
            "fraud_without_numeric_price": sum(
                int(row["label"]["fraud_issuers_without_price"]) for row in dataset
            ),
            "zero_lower_finite_upper": sum(
                float(row["label"]["lower"]) == 0 and row["label"]["upper"] is not None
                for row in dataset
            ),
            "zero_lower_upper_at_most_10": sum(
                float(row["label"]["lower"]) == 0
                and row["label"]["upper"] is not None
                and float(row["label"]["upper"]) <= 10
                for row in dataset
            ),
        },
        "interval_width_eur": {
            "finite_count": len(finite_widths),
            "median_all": _median(finite_widths),
            "median_positive_lower": _median(positive_widths),
            "per_unit_median": {
                unit: _median(widths) for unit, widths in sorted(per_unit_widths.items())
            },
        },
        "language_heuristic": {
            "method": "fixed domain-marker counts; unresolved is not imputed",
            "totals": dict(sorted(Counter(
                language_heuristic(str(row["features"]["description"]))
                for row in dataset
            ).items())),
            "by_game": language_by_game,
        },
        "images": {
            "independent_cases": len(first_per_game),
            "cases_with_image": image_cases,
            "cases_with_readable_dimensions": readable_images,
        },
        "cap_observability": {
            "priced_fraud_offers": priced_fraud_offers,
            "payments_proving_charge_above_4x_item_upper_bound": offers_above_four_upper,
            "binding_cap_directly_identifiable": False,
        },
        "actual_periods": actual_periods,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="valuation_audit")
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/harvest/line_items.jsonl")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--backtest", type=Path, default=DEFAULT_BACKTEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()
    try:
        dataset = load_dataset(args.dataset)
        games = {int(row["game_id"]) for row in dataset}
        transactions = load_transactions(args.db, games)
        backtest = json.loads(args.backtest.read_text()) if args.backtest.is_file() else None
        audit = build_audit(dataset, transactions, backtest)
        _atomic_json(args.output, audit)
    except (OSError, ValueError, BacktestError) as exc:
        print(f"audit failed: {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(audit, indent=2, sort_keys=True))
    print(f"audit: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
