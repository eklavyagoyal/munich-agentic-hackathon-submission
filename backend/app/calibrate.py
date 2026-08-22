"""Fit the policy multipliers on played games.

Step 1 (--estimates): run THE SAME ensemble the live pipeline uses over every
extracted case; cache t_hat per item in SQLite.
Step 2 (--sweep): grid over (A, B); score against proven t-bands and the real
opponent charges. Issuer income is scored STRICTLY (only a <= proven t_lo
earns; grey zone earns 0), so the recommended A is a floor, not a gamble.

    .venv/bin/python -m backend.app.calibrate --estimates
    .venv/bin/python -m backend.app.calibrate --sweep
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf

from .config import CASES_EXTRACTED, OUR_TEAM
from .db import connect
from .estimate import estimate
from .parse import ParseError, load_case

N_OPP = 16


def _ensure_schema(con) -> None:
    con.execute("""CREATE TABLE IF NOT EXISTS estimates (
        game_id INTEGER, line_item INTEGER, t_hat REAL, source TEXT,
        PRIMARY KEY (game_id, line_item))""")
    con.execute("""CREATE TABLE IF NOT EXISTS estimates_v (
        variant TEXT, game_id INTEGER, line_item INTEGER, t_hat REAL, source TEXT,
        PRIMARY KEY (variant, game_id, line_item))""")
    # migrate the original run once, as variant 'base'
    con.execute("INSERT OR IGNORE INTO estimates_v "
                "SELECT 'base', game_id, line_item, t_hat, source FROM estimates")
    con.commit()


def build_estimates(variant: str = "base") -> None:
    con = connect()
    _ensure_schema(con)
    done = {r["game_id"] for r in con.execute(
        "SELECT DISTINCT game_id FROM estimates_v WHERE variant=?", (variant,))}
    dirs = [(int(d.name.split("_")[1]), d) for d in sorted(CASES_EXTRACTED.iterdir()) if d.is_dir()]
    todo = [(g, d) for g, d in dirs if g not in done and g != 0]
    print(f"estimates[{variant}]: {len(todo)} cases to run")

    def run(pair):
        gid, d = pair
        case = load_case(gid, d)
        t_hat, meta = estimate(case, use_anchors=variant.startswith("anchored"))
        return gid, t_hat, meta

    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for fut in cf.as_completed([ex.submit(run, p) for p in todo]):
            try:
                gid, t_hat, meta = fut.result()
            except (ParseError, Exception) as e:  # noqa: BLE001
                print(f"  case failed: {type(e).__name__}: {e}")
                continue
            con.executemany("INSERT OR REPLACE INTO estimates_v VALUES (?,?,?,?,?)",
                            [(variant, gid, i, v, meta["source"].get(i, "?")) for i, v in t_hat.items()])
            con.commit()
            ens = sum(1 for s in meta["source"].values() if s.startswith("ensemble"))
            print(f"  game {gid}: {len(t_hat)} items ({ens} ensemble)")


def sweep(p_fair_grey: float = 0.5, variant: str = "base") -> None:
    con = connect()
    _ensure_schema(con)
    est = {(r["game_id"], r["line_item"]): r["t_hat"]
           for r in con.execute("SELECT * FROM estimates_v WHERE variant=?", (variant,))}
    bands = {(r["game_id"], r["line_item"]): (r["t_lo"], r["t_hi"])
             for r in con.execute("SELECT * FROM item_bounds")}
    # opponent charges with reconstructed a
    charges = [(r["game_id"], r["line_item"], r["a"])
               for r in con.execute(
                   "SELECT game_id, line_item, a FROM issuer_prices "
                   "WHERE issuer != ? AND a IS NOT NULL AND a > 0", (OUR_TEAM,))]

    def charge_status(g, item, a):
        lo, hi = bands.get((g, item), (0.0, None))
        if lo and a <= lo + 1e-9:
            return "fair"
        if hi is not None and a >= hi - 1e-9:
            return "fraud"
        return "grey"

    print(f"[{variant}] scoring {len(est)} estimated items, {len(charges)} opponent charges "
          f"(p_fair in grey zone = {p_fair_grey})")

    results = []
    A_grid = [0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0, 1.1, 1.2, 1.4, 1.7, 2.0, 2.5]
    B_grid = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 12.0, 1e9]
    for A in A_grid:
        # issuer income, strict: a earns 16a iff a <= proven t_lo
        income = 0.0
        n_safe = 0
        for (g, item), t_hat in est.items():
            lo, hi = bands.get((g, item), (0.0, None))
            a = A * t_hat
            if lo and a <= lo + 1e-9:
                income += N_OPP * a
                n_safe += 1
        for B in B_grid:
            cost = 0.0
            for g, item, a_opp in charges:
                t_hat = est.get((g, item))
                if t_hat is None:
                    continue
                b = B * t_hat
                st = charge_status(g, item, a_opp)
                if a_opp <= b:                       # we accept
                    cost += a_opp
                else:                                # we reject
                    if st == "fair":
                        cost += 1.5 * a_opp
                    elif st == "grey":
                        cost += p_fair_grey * 1.5 * a_opp
            results.append((A, B, income, cost, income - cost, n_safe))

    results.sort(key=lambda r: -r[4])
    print(f"\n  A      B    | income(strict) |     cost     |     NET    | safe items")
    for A, B, inc, cost, net, n_safe in results[:12]:
        b_str = "inf" if B >= 1e8 else f"{B:g}"
        print(f"{A:5.2f} {b_str:>6s} | {inc:14,.0f} | {cost:12,.0f} | {net:10,.0f} | {n_safe}")
    # Also show current defaults and B extremes for context
    print("\nreference points:")
    for A, B in ((0.85, 3.0), (1.0, 1e9), (0.85, 1.0)):
        for rA, rB, inc, cost, net, n in results:
            if rA == A and rB == B:
                b_str = "inf" if B >= 1e8 else f"{B:g}"
                print(f"  A={A} B={b_str}: net {net:,.0f} (income {inc:,.0f}, cost {cost:,.0f})")
                break


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--estimates", action="store_true")
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--p-fair", type=float, default=0.5)
    ap.add_argument("--variant", default="base")
    a = ap.parse_args()
    if a.estimates:
        build_estimates(a.variant)
    if a.sweep:
        sweep(a.p_fair, a.variant)
    if not (a.estimates or a.sweep):
        ap.error("--estimates and/or --sweep")


if __name__ == "__main__":
    main()
