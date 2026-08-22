"""Score a set of (a, b) decisions against what the tournament actually did.

    PYTHONPATH=. .venv/bin/python tools/score.py --actual            # our realised scores
    PYTHONPATH=. .venv/bin/python tools/score.py --label l3          # a backtest run
    PYTHONPATH=. .venv/bin/python tools/score.py --label l3 --vs b2  # two runs, per game

WHY THIS EXISTS

`backtest.py --diff` reports charge and limit SUMS, which are not euro impact: a
higher charge earns 16x when it is fair and nothing when it is not. Every agent that
has priced a change today rebuilt this scorer in a scratchpad and validated it by
hand. Once, in the repo, validated by a flag.

THE PAYOFF MATRIX (docs/MODEL_BRIEF.md 1)

                     a <= t (fair)            a > t (fraud)
  a <= b  accepted   I pays a,   H gets a     I pays min(a,c), H gets same
  a >  b  rejected   I pays 1.5a, H gets a    I pays 0,        H gets 0

As issuer we are H; as insurer we are I. A fair charge is paid by every reviewer
whether they accept or not, which is why undercharging a fair line costs 16x.

WHAT IS EXACT AND WHAT IS NOT

Exact: our realised score, and the insurer side of any change that only LOWERS b.
Lowering b can only turn an acceptance into a rejection, and every charge is either
fair with its amount visible or already rejected by all sixteen.

Not exact: RAISING b. A fraudulent charge that every reviewer rejected pays nothing
and therefore never reveals its amount -- 423 such charges over games 1-10. Raising
b would start paying them, at a size we cannot observe. Those rows are reported
separately as `unpriced_risk` rather than folded into a total, because a number that
silently assumes they are free is worse than no number.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "c2f.sqlite"
BACKTEST = ROOT / "data" / "backtest"
EVENTS = ROOT / "data" / "events" / "tournament.jsonl"
US = "Oasis"


def labels(con: sqlite3.Connection) -> tuple[dict, dict]:
    """(game,item,issuer) -> 'fair'/'fraud', and the fair charge amount when known."""
    side: dict[tuple, str] = {}
    amount: dict[tuple, float] = {}
    for g, iss, acc, it, amt in con.execute(
            "select game_id,issuer,accepted,line_item,amount from transactions"):
        k = (g, it, iss)
        if acc:
            continue
        if amt > 0:                      # rejected yet paid => fair, and amt IS the charge
            side[k] = "fair"
            amount[k] = max(amount.get(k, 0.0), amt)
        else:                            # rejected and unpaid => fraud, size hidden
            side.setdefault(k, "fraud")
    return side, amount


def our_decisions_from_events(path: Path, only_last_tier: bool = True) -> dict:
    """(game,item) -> (a, b) from an event log, taking the last tier submitted."""
    out: dict[tuple, tuple[float, float]] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") == "item.decided":
                p = e["payload"]
                out[(e["round"], p["idx"])] = (p["a"], p["b"])
    return out


def score(con: sqlite3.Connection, ours: dict) -> dict:
    """Per game: income, cost, net, and the rows whose cost we cannot price."""
    side, amount = labels(con)
    per = defaultdict(lambda: {"income": 0.0, "cost": 0.0, "unpriced_risk": 0})
    rows = con.execute("select game_id,issuer,reviewer,line_item,accepted,amount "
                       "from transactions").fetchall()
    for g, iss, rev, it, acc, amt in rows:
        r = per[g]
        if iss == US:
            # What we were paid as handyman. Under a counterfactual (a, b) this only
            # holds where our charge stayed on the same side of t, so callers compare
            # runs whose charges are both fair or both fraudulent for that item.
            r["income"] += amt
        if rev == US:
            lab = side.get((g, it, iss))
            ab = ours.get((g, it))
            if ab is None:
                r["cost"] += 1.5 * amt if (not acc and amt > 0) else (amt if acc else 0.0)
                continue
            a_charge = amount.get((g, it, iss))
            if lab == "fair" and a_charge is not None:
                # Exact: we know the charge, so we know which side of our b it falls.
                r["cost"] += a_charge if a_charge <= ab[1] else 1.5 * a_charge
            elif lab == "fraud":
                # Rejected fraud hides its amount. If our b would now accept it we
                # cannot say what it costs, so count it rather than guess.
                if acc:
                    r["cost"] += amt          # observed size
                else:
                    r["unpriced_risk"] += 1
            elif acc:
                r["cost"] += amt
    for g, r in per.items():
        r["net"] = r["income"] - r["cost"]
    return dict(per)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--actual", action="store_true", help="score our realised submissions")
    p.add_argument("--label", default=None, help="score a backtest run by label")
    p.add_argument("--vs", default=None, help="compare against another label")
    a = p.parse_args()
    if not DB.exists():
        print("no data/c2f.sqlite -- run tools/harvest.py --once")
        return 1
    con = sqlite3.connect(DB)

    def load(which: str | None):
        if which is None:
            return our_decisions_from_events(EVENTS)
        return our_decisions_from_events(BACKTEST / f"{which}.events.jsonl")

    runs = {}
    if a.actual or (not a.label):
        runs["actual"] = load(None)
    if a.label:
        runs[a.label] = load(a.label)
    if a.vs:
        runs[a.vs] = load(a.vs)

    scored = {name: score(con, d) for name, d in runs.items()}
    games = sorted({g for s in scored.values() for g in s})
    names = list(scored)
    print("  " + "".join(f"{n:>42}" for n in names))
    print(f"{'game':>4}"
          + "".join(f"{'income':>11}{'cost':>11}{'net':>12}{'unpriced':>8}" for _ in names))
    tot = {n: 0.0 for n in names}
    risk_tot = {n: 0 for n in names}
    for g in games:
        line = f"{g:>4}"
        for n in names:
            r = scored[n].get(g, {"income": 0.0, "cost": 0.0, "net": 0.0, "unpriced_risk": 0})
            line += (f"{r['income']:>11,.0f}{r['cost']:>11,.0f}{r['net']:>12,.0f}"
                     f"{r['unpriced_risk']:>8}")
            tot[n] += r["net"]
            risk_tot[n] += r["unpriced_risk"]
        print(line)
    # Per run, not a max across runs: the whole point is to see WHICH run took on the
    # invisible risk, and a max hides exactly that.
    print(f"{'TOT':>4}" + "".join(f"{'':>22}{tot[n]:>12,.0f}{risk_tot[n]:>8}" for n in names))
    if len(names) == 2:
        d = tot[names[0]] - tot[names[1]]
        print(f"\n  {names[0]} minus {names[1]}: {d:+,.2f}")
        print("  'unpriced' counts rejected-fraud charges whose amount is invisible.")
        print("  A raise in b that increases that count is NOT proven positive.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
