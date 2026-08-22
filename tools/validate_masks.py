"""Does the worthless-item detector actually discriminate? Precision and recall.

    PYTHONPATH=. .venv/bin/python tools/validate_masks.py --games 5,8,9,10,12
    PYTHONPATH=. .venv/bin/python tools/validate_masks.py --games 8 --samples 3

WHY THIS EXISTS, AND WHY IT COMES BEFORE THE PIPELINE

`rules_user/worthless_accept_guard.py` is the mechanism for the most valuable thing
we have measured: keeping the charge and zeroing the acceptance limit on a worthless
item is worth +14,575.16 over 15 games, exactly (lowering b only converts
acceptances into rejections, so it never runs into the 423 rejected-fraud charges
whose amounts are invisible).

The guard, built, measured -75.00. The mechanism was right -- charges identical,
game 9's limit 1,142 -> 713, game 10's 843 -> 398 -- and it still lost money,
because the DETECTOR fires on the wrong items often enough to cancel a five-figure
oracle. So the binding constraint is precision, not wiring, and precision is
measurable without spending a tournament round.

THE GROUND TRUTH, from tools/thresholds.py

  worthless : t_lo == 0 AND bounded. Proven ceiling, median 38.25, never above 176.
  valuable  : t_lo >= 200. Proven floor, some above 7,000.

Items in neither class are skipped -- an unbounded t_lo == 0 item is consistent with
worthless but not proven, and counting it either way would flatter or punish the
detector for free.

WHY PRECISION MATTERS MORE THAN RECALL HERE

Cost is concentrated: the median worst item is ~49% of a round's cost and game 10
was 92% in one item. A false positive zeroes b on a VALUABLE item, so we reject its
fair charges and pay 1.5a on each -- the game-1 failure mode in miniature. A false
negative merely leaves money on the table. The gate in
docs/CLAIM_PIPELINE_PLAN.md 4.1 is therefore precision >= 0.90, and recall is
reported but not gated.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from c2f.core import env

env.load()

from c2f.estimate import ensemble  # noqa: E402
from c2f.ingest import decrypt, parse  # noqa: E402
from c2f.submit.client import LiveApi  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "c2f.sqlite"
CASES = ROOT / "public-cases-ehl" / "cases"

WORTHLESS_CEILING = 176.0    # highest proven ceiling in the worthless population
VALUABLE_FLOOR = 200.0


def classes(con: sqlite3.Connection) -> tuple[dict, dict]:
    """(game,item) -> ceiling for proven-worthless; -> floor for proven-valuable."""
    side: dict[tuple, str] = {}
    lo: dict[tuple, float] = {}
    hi: dict[tuple, float] = {}
    rows = con.execute("select game_id,issuer,line_item,accepted,amount "
                       "from transactions").fetchall()
    for g, iss, it, acc, amt in rows:
        k = (g, it, iss)
        if acc:
            continue
        if amt > 0:
            side[k] = "fair"
            lo[(g, it)] = max(lo.get((g, it), 0.0), amt)
        else:
            side.setdefault(k, "fraud")
    for g, iss, it, acc, amt in rows:
        # An ACCEPTED fraudulent charge is the only thing that reveals an upper bound.
        if acc and amt > 0 and side.get((g, it, iss)) == "fraud":
            hi[(g, it)] = min(hi.get((g, it), float("inf")), amt)
    worthless = {k: v for k, v in hi.items()
                 if v <= WORTHLESS_CEILING and lo.get(k, 0.0) == 0.0}
    valuable = {k: v for k, v in lo.items() if v >= VALUABLE_FLOOR}
    return worthless, valuable


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--games", default=None, help="comma list; default every labelled game")
    p.add_argument("--samples", type=int, default=2)
    p.add_argument("--timeout", type=float, default=35.0)
    a = p.parse_args()
    if not DB.exists():
        print("no data/c2f.sqlite -- run tools/harvest.py --once")
        return 1
    con = sqlite3.connect(DB)
    worthless, valuable = classes(con)
    labelled = sorted({g for g, _ in list(worthless) + list(valuable)})
    games = ([int(x) for x in a.games.split(",")] if a.games else labelled)
    print(f"ground truth: {len(worthless)} proven-worthless, {len(valuable)} proven-valuable, "
          f"over games {labelled}")
    print(f"testing games {games}, {a.samples} ensemble samples per item\n")

    api = LiveApi()
    tp = fp = tn = fn = 0
    rows = []
    for g in games:
        arch = CASES / f"case_{g:02d}.zip"
        if not arch.exists():
            print(f"  game {g}: no archive"); continue
        try:
            key = api.fetch_key(str(g), poll_for=6.0)
        except Exception as e:  # noqa: BLE001
            print(f"  game {g}: no key ({type(e).__name__})"); continue
        with tempfile.TemporaryDirectory() as tmp:
            files = decrypt.extract(arch, key, Path(tmp))
            case = parse.build_case(str(g), files)
            est = ensemble.prefetch_sync(case, samples=a.samples, timeout=a.timeout,
                                         fast=True)
        for idx, e in est.items():
            k = (g, idx)
            truth = ("worthless" if k in worthless
                     else "valuable" if k in valuable else None)
            if truth is None:
                continue          # not proven either way; scoring it would be free credit
            votes = getattr(e, "worthless_votes", 0)
            n = max(getattr(e, "samples", 0), 1)
            said = votes * 2 > n
            if truth == "worthless":
                if said: tp += 1
                else: fn += 1
            else:
                if said: fp += 1
                else: tn += 1
            rows.append((g, idx, truth, votes, n, said,
                         worthless.get(k) or valuable.get(k, 0.0)))

    print(f"{'game':>4} {'item':>4} {'truth':>10} {'votes':>7} {'says':>6} {'proven':>10}")
    for g, idx, truth, votes, n, said, bound in rows:
        mark = "" if (truth == "worthless") == said else "   <-- WRONG"
        print(f"{g:>4} {idx:>4} {truth:>10} {votes:>3}/{n:<3} "
              f"{'worthless' if said else 'valuable':>6} {bound:>10.2f}{mark}")

    print()
    if tp + fp == 0:
        print("the detector never fired: precision undefined, recall 0")
    else:
        prec = tp / (tp + fp)
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        print(f"  precision {prec:.2f}   recall {rec:.2f}   "
              f"(tp {tp}, fp {fp}, tn {tn}, fn {fn})")
        print(f"  gate is precision >= 0.90 -> "
              f"{'PASS' if prec >= 0.90 else 'FAIL, do not build on this detector'}")
        if fp:
            print(f"  {fp} false positive(s): b would be zeroed on a PROVEN VALUABLE item, "
                  "so we reject its fair charges and pay 1.5a on each")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
