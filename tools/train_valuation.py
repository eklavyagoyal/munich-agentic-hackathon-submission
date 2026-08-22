#!/usr/bin/env python3
"""Fit the offline interval posterior and write only a gitignored artifact."""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from c2f.estimate.interval_model import (
    DEFAULT_ARTIFACT,
    DEFAULT_DATASET,
    IntervalValuationModel,
    ModelError,
    dataset_identity,
    load_rows,
)


def main() -> int:
    parser = argparse.ArgumentParser(prog="train_valuation")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_ARTIFACT)
    args = parser.parse_args()
    try:
        rows = load_rows(args.dataset)
        model = IntervalValuationModel.fit(rows)
        model.artifact["training_snapshot"] = dataset_identity(args.dataset, rows)
        model.save(args.output)
    except (ModelError, OSError, ValueError) as exc:
        print(f"training failed: {type(exc).__name__}: {exc}")
        return 1

    artifact = model.artifact
    print(f"training rows: {artifact['training_rows']}")
    print(f"eligible unit rows: {artifact.get('eligible_unit_rows', artifact['training_rows'])}")
    for reason, count in sorted(artifact.get("excluded_rows_by_reason", {}).items()):
        print(f"  excluded rows {reason}: {count}")
    print(f"trained cohorts: {len(artifact['cohorts'])}")
    for unit, cohort in sorted(artifact["cohorts"].items()):
        central = cohort["variants"]["0.20"]
        zero_mass = central["probabilities"][0]
        positive = cohort["positive_lognormal"]
        print(
            f"  {unit}: {cohort['informative_rows']} informative rows / "
            f"{len(cohort['games'])} games, zero_mass={zero_mass:.3f}, "
            f"positive_sigma={positive['sigma']:.3f}, "
            f"positive_median_rate={math.exp(positive['mu']):.2f}, "
            f"em_iterations={central['iterations']}"
        )
    for unit, reason in sorted(artifact["skipped_cohorts"].items()):
        print(f"  abstain {unit}: {reason}")
    print(f"artifact: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
