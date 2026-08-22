"""t_hat -> (a, b). The multipliers are THE tunable surface of the pipeline.

Hot-reloadable: data/policy.json overrides the env defaults and is re-read
before every game, so the dashboard can adjust the live pipeline between
rounds without a restart. calibrate.py fits the values on proven t-bands.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from .config import DATA

POLICY_FILE = DATA / "policy.json"

# Calibrated on the 41 played games (backend/app/calibrate.py):
#  - strict issuer income peaks at A~0.85 (466 ensemble items vs proven bands)
#  - reviewer cost: B=1.0 wins the backtest, but the ensemble underestimates t
#    on 44% of items (median x1.67), and rejecting fair costs 1.5a — B=1.5 buys
#    that robustness for ~1.6k/game in the backtest.
DEFAULTS = {
    "a_mult": float(os.environ.get("C2F_A_MULT", "0.85")),
    "b_mult": float(os.environ.get("C2F_B_MULT", "1.5")),
    "min_a": 1.0,
    # When the ensemble says t=0: as ISSUER, charging above t costs nothing
    # (rejected-fraud pays no penalty to the issuer) — so a small positive a
    # dominates a=0 whenever the model might be wrong about coverage.
    # p25 of proven t_lo across 41 games is 78; stay under it.
    "zero_floor_a": 69.0,
    # Retrieval anchors (proven t-bands from played games in the prompt).
    # Backtested leave-one-game-out on 198 two-sided-band items: +17% expected
    # issuer income, -14% expected reviewer cost vs the plain prompt.
    "anchors": True,
    "models": os.environ.get("C2F_MODELS", "gpt-4.1-mini,gpt-5.4-mini,gpt-5.6-terra"),
    "note": "",
}


def load_policy() -> dict:
    p = dict(DEFAULTS)
    try:
        override = json.loads(POLICY_FILE.read_text())
        for k in p:
            if k in override and override[k] is not None:
                p[k] = override[k]
        p["a_mult"] = float(p["a_mult"])
        p["b_mult"] = float(p["b_mult"])
        p["min_a"] = float(p["min_a"])
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return p


def save_policy(policy: dict) -> dict:
    """Persist an override; unknown keys are dropped, missing keys keep defaults."""
    clean = {k: policy[k] for k in DEFAULTS if k in policy}
    POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = POLICY_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(clean, indent=2))
    tmp.replace(POLICY_FILE)
    return load_policy()


@dataclass(frozen=True)
class Bid:
    index: int
    charge_price: float
    acceptance_limit: float


def decide(t_hat: dict[int, float], policy: dict | None = None) -> list[Bid]:
    p = policy or load_policy()
    bids = []
    zero_floor = float(p.get("zero_floor_a", 0.0))
    for idx in sorted(t_hat):
        t = max(t_hat[idx], 0.0)
        a = round(max(p["a_mult"] * t, p["min_a"]), 2)
        b = round(max(p["b_mult"] * t, a), 2)
        if t < 1.0 and zero_floor > 0:
            a = zero_floor          # free upside if the model is wrong about t=0
            b = 0.0                 # but as reviewer, keep rejecting these
        bids.append(Bid(index=idx, charge_price=a, acceptance_limit=b))
    return bids
