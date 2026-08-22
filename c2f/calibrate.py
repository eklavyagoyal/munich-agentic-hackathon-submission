"""Fit our estimator against what the tournament actually told us. ARCHITECTURE §8.

We never observe `t`. We observe interval-censored bounds on it, and only from
REJECTIONS — acceptance is uninformative:

  as insurer, we rejected `a` and then ate the 1.5a penalty   ->  t >= a
  as insurer, we rejected `a` and paid nothing                ->  t <  a
  as issuer, an opponent ate a penalty on our `a`             ->  t >= a
  as issuer, our `a` earned nothing from anyone               ->  t <  a

Each bound is a censored observation of the ratio `t / our median`. Fitting a
multiplicative correction to those ratios is the only way to see systematic bias,
which is invisible from the standings: a team that is never once rejected looks
flawless and may be leaving half the money on the table (GAMEPLAN §3, Hammer Hannes).

Global `k` first, per-trade once a trade has enough bounds, exactly as §8 prescribes.
Inputs come from the round event log, so there is no second source of truth.

    python -m c2f.calibrate                                  # self-check
    python -m c2f.calibrate data/events/*.jsonl --outcomes o.jsonl
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from c2f.core.events import read_events
from c2f.core.models import History, LineItem
from c2f.estimate.pricebook import match_rate

# Below this many bounds a trade borrows the global correction instead of its own.
MIN_BOUNDS_PER_TRADE = 4
# Refuse to move more than this in one step; a bad round should not whipsaw us.
K_LIMITS = (0.5, 2.0)


@dataclass(frozen=True)
class Bound:
    """One-sided evidence about `t` for one line item of one case."""

    case_id: str
    idx: int
    price: float
    t_at_least: bool  # True: t >= price. False: t < price.
    role: str = "issuer"

    @property
    def key(self) -> tuple[str, int]:
        return (self.case_id, self.idx)


@dataclass(frozen=True)
class Observed:
    """What we predicted for an item, recovered from the event log."""

    median: float
    trade: str


def from_events(paths: list[Path]) -> dict[tuple[str, int], Observed]:
    """Recover our own predictions from the round event log.

    Uses `case.parsed` for descriptions/units (hence the trade) and `item.belief`
    for the median we actually submitted against.
    """
    items: dict[tuple[str, int], LineItem] = {}
    medians: dict[tuple[str, int], float] = {}
    for path in paths:
        for ev in read_events(path):
            if ev.type == "case.parsed":
                for it in ev.payload.get("items", []):
                    items[(ev.case, int(it["idx"]))] = LineItem(
                        idx=int(it["idx"]),
                        description=it.get("desc", ""),
                        qty=float(it.get("qty", 1)),
                        unit=it.get("unit", ""),
                    )
            elif ev.type == "item.belief":
                # A later tier overwrites an earlier one, which is what we want:
                # the last belief is the one the final submission used.
                medians[(ev.case, int(ev.payload["idx"]))] = float(ev.payload["median"])
    out: dict[tuple[str, int], Observed] = {}
    for key, median in medians.items():
        item = items.get(key)
        out[key] = Observed(median, match_rate(item).trade if item else "unknown")
    return out


def bounds_from_transactions(rows: list[dict]) -> list[Bound]:
    """Normalised transaction rows -> bounds.

    ⚠️ WIRE FORMAT IS A GUESS until API_HANDBOOK.md lands (ASKS.md #4). Expected keys:
        case_id, idx, price, accepted (bool), role ("issuer"|"insurer"),
        and one of received (issuer) / paid (insurer).
    Only this adapter is format-specific; the fit below never sees a raw row.
    """
    out: list[Bound] = []
    for row in rows:
        try:
            if row.get("accepted"):
                continue  # acceptance proves nothing about t
            price = float(row["price"])
            if not (math.isfinite(price) and price > 0):
                continue
            role = str(row.get("role", "issuer"))
            if role == "issuer":
                # Paid despite the rejection => the charge was fair => t >= price.
                at_least = float(row.get("received", 0)) > 0
            else:
                # Billed after we rejected => we rejected a fair claim => t >= price.
                at_least = float(row.get("paid", 0)) > 0
            out.append(Bound(str(row["case_id"]), int(row["idx"]), price, at_least, role))
        except (KeyError, TypeError, ValueError) as e:
            print(f"warn: unparseable transaction row ({e}): {str(row)[:120]}")
    return out


def _fit_ratio(lows: list[float], highs: list[float]) -> tuple[float, int]:
    """Interval-censored fit of the ratio `t / our median`.

    `lows` are ratios from `t >= price`, `highs` from `t < price`. Because `t` genuinely
    varies per item the constraints conflict, so rather than intersecting them we pick
    the k violating the fewest — a censored-data median, not an interval.

    ponytail: an exact 1-D scan over the candidate ratios. Same answer as a survival
    fit for this objective, ~50 lines shorter, and still readable at 3am. Revisit only
    if we ever have hundreds of bounds per round.
    """
    if not lows and not highs:
        return 1.0, 0
    cands = sorted({r * s for r in lows + highs for s in (0.999, 1.001)} | {1.0})
    best_k, best_bad = 1.0, None
    for k in cands:
        bad = sum(r > k for r in lows) + sum(r <= k for r in highs)
        if best_bad is None or bad < best_bad:
            best_k, best_bad = k, bad
    return min(max(best_k, K_LIMITS[0]), K_LIMITS[1]), best_bad or 0


def fit(bounds: list[Bound], observed: dict[tuple[str, int], Observed]) -> dict:
    """Global k plus per-trade k for trades with enough evidence."""
    lows: list[float] = []
    highs: list[float] = []
    by_trade: dict[str, tuple[list[float], list[float]]] = {}
    unmatched = 0

    for b in bounds:
        obs = observed.get(b.key)
        if obs is None or obs.median <= 0:
            unmatched += 1
            continue
        ratio = b.price / obs.median
        (lows if b.t_at_least else highs).append(ratio)
        tl, th = by_trade.setdefault(obs.trade, ([], []))
        (tl if b.t_at_least else th).append(ratio)

    k, violations = _fit_ratio(lows, highs)
    n = len(lows) + len(highs)

    trade_bias: dict[str, float] = {}
    thin: list[str] = []
    for trade, (tl, th) in sorted(by_trade.items()):
        if len(tl) + len(th) < MIN_BOUNDS_PER_TRADE:
            thin.append(f"{trade}({len(tl) + len(th)})")
            continue
        trade_bias[trade] = _fit_ratio(tl, th)[0]

    return {
        "k": round(k, 4),
        "n": n,
        "lower_bounds": len(lows),
        "upper_bounds": len(highs),
        "violations": violations,
        "unmatched": unmatched,
        "trade_bias": {t: round(v, 4) for t, v in trade_bias.items()},
        "thin_trades": thin,
        "advice": _advice(k, lows, highs),
    }


def _advice(k: float, lows: list[float], highs: list[float]) -> str:
    if not lows and not highs:
        return "no bounds yet — every transaction was accepted, so we learned nothing"
    if not highs:
        # Never once found to have overcharged: the Hammer Hannes signature.
        return (
            "no upper bounds at all — we have never been caught overcharging, which almost "
            f"certainly means we are under-charging. Raise C2F_CALIBRATION to >= {max(k, 1.15):.2f}"
        )
    if not lows:
        return f"no lower bounds — we may be over-charging. Try C2F_CALIBRATION={min(k, 0.9):.2f}"
    if k > 1.08:
        return f"we under-estimate t by ~{(k - 1) * 100:.0f}% — set C2F_CALIBRATION={k:.2f}"
    if k < 0.92:
        return f"we over-estimate t by ~{(1 - k) * 100:.0f}% — set C2F_CALIBRATION={k:.2f}"
    return "well calibrated — leave C2F_CALIBRATION at 1.0"


def build_history(bounds: list[Bound], observed: dict[tuple[str, int], Observed]) -> History:
    """The `History` the rule engine consumes. Per-item bounds plus per-trade bias."""
    f = fit(bounds, observed)
    intervals: dict[str, tuple[float, float]] = {}
    for b in bounds:
        lo, hi = intervals.get(str(b.idx), (0.0, math.inf))
        intervals[str(b.idx)] = (max(lo, b.price), hi) if b.t_at_least else (lo, min(hi, b.price))
    bias = dict(f["trade_bias"])
    bias.setdefault("*", f["k"])  # global fallback for trades without their own fit
    return History(bounds=intervals, trade_bias=bias)


def field_stats(rows: list[dict]) -> dict:
    """How the field behaves against us as insurer. Gates the `b` level."""
    inc = [r for r in rows if r.get("role") == "insurer"]
    if not inc:
        return {"n": 0, "note": "no incoming transactions yet"}
    accepted = sum(bool(r.get("accepted")) for r in inc)
    wrongful = sum(
        1
        for r in inc
        if not r.get("accepted") and float(r.get("paid", 0)) > float(r.get("price", 0))
    )
    rejected = len(inc) - accepted
    return {
        "n": len(inc),
        "accept_rate": round(accepted / len(inc), 3),
        "wrongful_rejects": wrongful,
        "advice": (
            f"{wrongful} wrongful reject(s) at 0.5a each — raise C2F_BOLDNESS toward 1.15"
            if wrongful
            else "no wrongful rejects — b is safe; a lower b would buy information"
            if rejected
            else "we accepted everything, so we learned nothing — b may be too high"
        ),
    }


def demo() -> None:
    # Our medians were all 100; the truth sits near 130, i.e. we under-estimate ~30%.
    observed = {("1", i): Observed(100.0, "flooring" if i < 5 else "painting") for i in range(1, 8)}
    rows = [
        # Charged 120, rejected, paid anyway -> 120 <= t.
        {"case_id": "1", "idx": 1, "price": 120, "accepted": False, "role": "issuer", "received": 120},
        {"case_id": "1", "idx": 2, "price": 125, "accepted": False, "role": "issuer", "received": 125},
        # Charged 145, rejected, got nothing -> t < 145.
        {"case_id": "1", "idx": 3, "price": 145, "accepted": False, "role": "issuer", "received": 0},
        # We rejected an incoming 128 and were billed 1.5x -> we were wrong, 128 <= t.
        {"case_id": "1", "idx": 4, "price": 128, "accepted": False, "role": "insurer", "paid": 192},
        # We rejected an incoming 150 and paid nothing -> we were right, t < 150.
        {"case_id": "1", "idx": 5, "price": 150, "accepted": False, "role": "insurer", "paid": 0},
        # Accepted: carries no information and must be dropped.
        {"case_id": "1", "idx": 6, "price": 99, "accepted": True, "role": "insurer", "paid": 99},
    ]

    bounds = bounds_from_transactions(rows)
    assert len(bounds) == 5, bounds
    assert sum(b.t_at_least for b in bounds) == 3

    f = fit(bounds, observed)
    assert f["n"] == 5 and f["lower_bounds"] == 3 and f["upper_bounds"] == 2
    assert 1.28 <= f["k"] <= 1.45, f
    assert f["violations"] == 0, f
    assert "under-estimate" in f["advice"], f["advice"]

    # flooring has 4 bounds -> its own fit; painting has 1 -> too thin, borrows global.
    assert "flooring" in f["trade_bias"], f["trade_bias"]
    assert "painting" not in f["trade_bias"] and any("painting" in t for t in f["thin_trades"])

    # Bounds we have no prediction for are reported, never silently dropped.
    assert fit(bounds, {})["unmatched"] == 5
    assert fit([], observed)["k"] == 1.0

    # Never being caught overcharging is a warning, not a success.
    only_low = [b for b in bounds if b.t_at_least]
    assert "under-charging" in fit(only_low, observed)["advice"]

    # A wild round cannot whipsaw us more than the step limit allows.
    wild = [Bound("1", 1, 100_000.0, True)]
    assert fit(wild, {("1", 1): Observed(1.0, "x")})["k"] == K_LIMITS[1]

    h = build_history(bounds, observed)
    assert h.trade_bias["*"] == f["k"] and "flooring" in h.trade_bias
    assert h.bounds["1"][0] == 120 and h.bounds["3"][1] == 145

    fs = field_stats(rows)
    assert fs["n"] == 3 and fs["wrongful_rejects"] == 1 and "1.15" in fs["advice"]

    # Malformed rows warn and are skipped rather than killing the report.
    assert bounds_from_transactions([{"nope": 1}, {"case_id": "x"}]) == []

    print(f"calibrate.py self-check ok — k={f['k']} from {f['n']} bounds; "
          f"per-trade {f['trade_bias']}; {f['advice']}")


def main(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="c2f.calibrate")
    p.add_argument("events", nargs="*", type=Path, help="round event logs")
    p.add_argument("--outcomes", type=Path, help="jsonl of transaction rows")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args(argv)

    if a.self_test or not a.outcomes:
        demo()
        return 0
    rows = [json.loads(x) for x in a.outcomes.read_text().splitlines() if x.strip()]
    observed = from_events(a.events)
    print(json.dumps({"fit": fit(bounds_from_transactions(rows), observed),
                      "field": field_stats(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
