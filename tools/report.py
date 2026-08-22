"""What the last game actually cost us, from the harvested results.

    PYTHONPATH=. .venv/bin/python tools/report.py            # latest finished game
    PYTHONPATH=. .venv/bin/python tools/report.py --game 2
    PYTHONPATH=. .venv/bin/python tools/report.py --all      # every game so far

Reads data/c2f.sqlite only. No network, no writes.

THE ECONOMICS THIS IS BUILT AROUND (GAME_DESCRIPTION §Payoffs)

As issuer, a fair charge (`a <= t`) is paid by EVERY opponent, whether they
accept or not -- rejecting still owes us `a`. Charge above `t` and we earn
nothing. So issuer revenue is a cliff, and undercharging is a silent, total loss
that never shows up as an error anywhere.

As reviewer, accepting costs `a`; rejecting costs `1.5a` if the charge was fair
and 0 if it was fraud. Wrongly accepting is exactly half as bad as wrongly
rejecting is -- which is why the accept limit sits at the 1/3-quantile.

Both sides are driven by the same belief about `t`. A belief that is too low
undercharges AND over-rejects at the same time, which is the failure this report
is designed to make obvious.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "c2f.sqlite"
US = "Oasis"


def game_report(con: sqlite3.Connection, gid: int, us: str) -> None:
    score = con.execute("SELECT score FROM scores WHERE game_id=? AND team=?", (gid, us)).fetchone()
    print(f"\n{'='*78}\nGAME {gid}   {us}: "
          f"{score[0]:+,.2f}" if score else f"\n{'='*78}\nGAME {gid}   {us}: no score")
    print("=" * 78)

    items = [r[0] for r in con.execute(
        "SELECT DISTINCT line_item FROM transactions WHERE game_id=? ORDER BY line_item", (gid,))]
    ours = {r[0]: r[1] for r in con.execute(
        "SELECT line_item, amount FROM transactions WHERE game_id=? AND issuer=? "
        "GROUP BY line_item", (gid, us))}
    missing = [i for i in items if i not in ours]

    print(f"\nAS ISSUER -- a fair charge is paid by everyone, so this is where income is won")
    print(f"{'item':>5}  {'ours':>10}  {'field median':>13}  {'field max':>10}  {'our rank':>9}")
    print("-" * 78)
    for i in items:
        field = sorted(r[0] for r in con.execute(
            "SELECT amount FROM transactions WHERE game_id=? AND line_item=? "
            "GROUP BY issuer", (gid, i)) if r[0] is not None)
        if not field:
            continue
        med = field[len(field) // 2]
        mine = ours.get(i)
        rank = (sorted(field, reverse=True).index(mine) + 1) if mine is not None else None
        mark = "  <- NOT SUBMITTED" if mine is None else ""
        print(f"{i:>5}  {('—' if mine is None else f'{mine:,.2f}'):>10}  {med:>13,.2f}  "
              f"{field[-1]:>10,.2f}  {('—' if rank is None else f'{rank}/{len(field)}'):>9}{mark}")
    if missing:
        print(f"\n  {len(missing)} line item(s) not submitted: {missing}")
        print("  Omitted items default to charge 0 / limit 0 -- they charge nobody and")
        print("  reject every fair claim, paying the 1.5a penalty on each. This is the")
        print("  single most expensive failure mode in the game.")

    print(f"\nAS REVIEWER -- rejecting a fair charge costs 1.5a")
    row = con.execute(
        "SELECT SUM(1-accepted) rej, COUNT(*) n, "
        "COALESCE(SUM(CASE WHEN accepted=0 THEN amount ELSE 0 END),0) amt "
        "FROM transactions WHERE game_id=? AND reviewer=?", (gid, us)).fetchone()
    if row and row["n"]:
        print(f"  rejected {row['rej']}/{row['n']} charges, worth {row['amt']:,.2f}")
        print(f"  worst case if every one of those was fair: {row['amt']*1.5:,.2f} in penalties")

    print(f"\nTHE FIELD")
    print(f"{'team':<24}{'charged':>10}{'rejected':>11}{'score':>13}")
    print("-" * 78)
    for r in con.execute("""
        SELECT s.team, s.score,
          (SELECT COALESCE(SUM(amount),0) FROM (SELECT amount FROM transactions
              WHERE game_id=s.game_id AND issuer=s.team GROUP BY line_item)) charged,
          (SELECT COALESCE(SUM(CASE WHEN accepted=0 THEN amount ELSE 0 END),0)
             FROM transactions WHERE game_id=s.game_id AND reviewer=s.team) rejected
        FROM scores s WHERE s.game_id=? ORDER BY s.score DESC""", (gid,)):
        mark = "  <- US" if r["team"] == us else ""
        print(f"{r['team']:<24}{r['charged']:>10,.2f}{r['rejected']:>11,.2f}"
              f"{r['score']:>13,.2f}{mark}")


def main() -> int:
    p = argparse.ArgumentParser(prog="report")
    p.add_argument("--game", type=int, default=None)
    p.add_argument("--all", action="store_true")
    p.add_argument("--team", default=US)
    p.add_argument("--db", type=Path, default=DB)
    a = p.parse_args()

    if not a.db.is_file():
        print(f"no {a.db} -- run tools/harvest.py --once first")
        return 1
    con = sqlite3.connect(a.db)
    con.row_factory = sqlite3.Row

    played = [r[0] for r in con.execute(
        "SELECT DISTINCT game_id FROM transactions ORDER BY game_id")]
    if not played:
        print("no transactions harvested yet")
        return 1
    games = played if a.all else [a.game or played[-1]]
    for gid in games:
        game_report(con, gid, a.team)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
