"""t_hat -> (a, b). The multipliers are THE tunable surface of the pipeline;
calibrate.py fits them on the proven t-bands of played games.

Issuer:   a = A_MULT * t_hat   (a <= t earns from every opponent; a > t earns ~0)
Reviewer: b = B_MULT * t_hat   (reject fair costs 1.5a; accept fraud costs min(a,c))
"""
from __future__ import annotations

import os
from dataclasses import dataclass

# Calibrated on the 41 played games (backend/app/calibrate.py):
#  - strict issuer income peaks at A~0.85 (466 ensemble items vs proven bands)
#  - reviewer cost: B=1.0 wins the backtest, but the ensemble underestimates t
#    on 44% of items (median x1.67), and rejecting fair costs 1.5a — B=1.5 buys
#    that robustness for ~1.6k/game in the backtest.
A_MULT = float(os.environ.get("C2F_A_MULT", "0.85"))
B_MULT = float(os.environ.get("C2F_B_MULT", "1.5"))
MIN_A = 1.0


@dataclass(frozen=True)
class Bid:
    index: int
    charge_price: float
    acceptance_limit: float


def decide(t_hat: dict[int, float]) -> list[Bid]:
    bids = []
    for idx in sorted(t_hat):
        t = max(t_hat[idx], 0.0)
        a = round(max(A_MULT * t, MIN_A), 2)
        b = round(max(B_MULT * t, a), 2)
        bids.append(Bid(index=idx, charge_price=a, acceptance_limit=b))
    return bids
