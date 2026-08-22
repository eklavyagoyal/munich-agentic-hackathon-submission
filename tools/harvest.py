"""Pull the tournament's public results into a local SQLite file, before they are gone.

    PYTHONPATH=. .venv/bin/python tools/harvest.py --once     # catch up and exit
    PYTHONPATH=. .venv/bin/python tools/harvest.py --watch    # keep catching up
    PYTHONPATH=. .venv/bin/python tools/harvest.py --stats    # what we hold

WHY A LOCAL COPY, WHEN THE API STILL SERVES HISTORY

It does today: `transactions?game_id=1` still answers after game 1 finished. But
that data exists in exactly one place, on someone else's server, for the length
of a hackathon. `matrix` already takes a `game_limit` and honours it as a window
(`game_limit=1` returns one cell), so the shape of a cap is present in the API;
whether it starts biting at 100 games is not something we get to find out safely.
Harvesting is cheap and reversible. Discovering at game 80 that game 3 is no
longer readable is not.

WHAT IT IS FOR

`transactions` is the only place the hidden threshold `t` leaks. Per line item it
says who issued, who reviewed, whether the charge was accepted, and for how much.
A rejection proves the charge sat above that reviewer's limit; an acceptance
proves almost nothing. Those one-sided bounds are what c2f/calibrate.py fits.

READ-ONLY. This module imports Leaderboard, which speaks to the public feed with
no credentials and has no write path of any kind.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from c2f.leaderboard import Leaderboard

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "c2f.sqlite"        # under data/, which is gitignored

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id          INTEGER PRIMARY KEY,
    start_time  TEXT,
    status      TEXT,
    seen_at     REAL
);
CREATE TABLE IF NOT EXISTS scores (
    game_id     INTEGER,
    team        TEXT,
    score       REAL,
    PRIMARY KEY (game_id, team)
);
-- One row per line item per opponent pairing. The primary key is the natural one,
-- so re-harvesting a game overwrites in place and can never duplicate.
CREATE TABLE IF NOT EXISTS transactions (
    game_id     INTEGER,
    issuer      TEXT,
    reviewer    TEXT,
    line_item   INTEGER,
    accepted    INTEGER,
    amount      REAL,
    PRIMARY KEY (game_id, issuer, reviewer, line_item)
);
CREATE INDEX IF NOT EXISTS ix_tx_issuer   ON transactions(issuer, game_id);
CREATE INDEX IF NOT EXISTS ix_tx_reviewer ON transactions(reviewer, game_id);
-- What we have already asked for, so a re-run costs nothing.
CREATE TABLE IF NOT EXISTS harvested (
    game_id     INTEGER,
    team        TEXT,
    rows        INTEGER,
    fetched_at  REAL,
    PRIMARY KEY (game_id, team)
);
"""


def connect(path: Path = DB) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def sync_games(con: sqlite3.Connection, lb: Leaderboard) -> int:
    games = lb.games()
    now = time.time()
    con.executemany(
        "INSERT INTO games(id, start_time, status, seen_at) VALUES(?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET status=excluded.status, seen_at=excluded.seen_at",
        [(g.id, g.start_time.isoformat(), g.status, now) for g in games])
    con.commit()
    return len(games)


def sync_scores(con: sqlite3.Connection, lb: Leaderboard) -> tuple[int, list[str]]:
    """Per-game scores from the matrix. `game_ids` names the columns of `cells`,
    so we never have to guess which cell belongs to which game."""
    raw = lb._get("/matrix", page=1, game_limit=100) or {}
    rows, ids = raw.get("items", []), raw.get("game_ids", [])
    teams = [r.get("team_name") for r in rows]
    out = []
    for r in rows:
        for gid, cell in zip(ids, r.get("cells", [])):
            if cell is not None:
                out.append((gid, r.get("team_name"), float(cell)))
    con.executemany("INSERT OR REPLACE INTO scores(game_id, team, score) VALUES(?,?,?)", out)
    con.commit()
    return len(out), [t for t in teams if t]


def harvest_transactions(con: sqlite3.Connection, lb: Leaderboard, game_id: int,
                         team: str) -> int:
    rows = lb.transactions(game_id=game_id, team=team)
    recs = [(game_id, r.get("issuer"), r.get("reviewer"), r.get("line_item_index"),
             1 if r.get("accepted") else 0, float(r.get("amount") or 0.0)) for r in rows]
    con.executemany(
        "INSERT OR REPLACE INTO transactions"
        "(game_id, issuer, reviewer, line_item, accepted, amount) VALUES(?,?,?,?,?,?)", recs)
    con.execute("INSERT OR REPLACE INTO harvested(game_id, team, rows, fetched_at) "
                "VALUES(?,?,?,?)", (game_id, team, len(recs), time.time()))
    con.commit()
    return len(recs)


def pending(con: sqlite3.Connection, teams: list[str]) -> list[tuple[int, str]]:
    """(game, team) pairs for finished games we have not asked about yet."""
    done = {(r["game_id"], r["team"]) for r in con.execute("SELECT game_id, team FROM harvested")}
    finished = [r["id"] for r in con.execute(
        "SELECT id FROM games WHERE status IS NOT NULL AND status != 'scheduled' ORDER BY id")]
    return [(g, t) for g in finished for t in teams if (g, t) not in done]


def run_once(con: sqlite3.Connection, lb: Leaderboard, teams_filter: str | None,
             pause: float, budget: int) -> tuple[int, int]:
    sync_games(con, lb)
    n_scores, teams = sync_scores(con, lb)
    if teams_filter:
        teams = [t for t in teams if t.lower() == teams_filter.lower()]
        if not teams:
            print(f"team {teams_filter!r} is not on the leaderboard yet")
            return 0, 0
    todo = pending(con, teams)
    if not todo:
        return n_scores, 0
    fetched = 0
    for gid, team in todo[:budget]:
        try:
            n = harvest_transactions(con, lb, gid, team)
        except Exception as e:  # noqa: BLE001 -- one bad pairing must not end the sweep
            print(f"  game {gid} / {team}: {type(e).__name__}: {str(e)[:90]}")
            continue
        fetched += 1
        print(f"  game {gid:>3} / {team:<28} {n:>4} rows")
        time.sleep(pause)          # a trickle, never a burst
    if len(todo) > budget:
        # Never let a cap look like completion.
        print(f"  ... {len(todo) - budget} pairing(s) left this pass (budget {budget})")
    return n_scores, fetched


def stats(con: sqlite3.Connection) -> None:
    def q(sql: str, *args):
        return con.execute(sql, args).fetchone()[0]

    print(f"games       : {q('SELECT COUNT(*) FROM games')} known, "
          f"{q('SELECT COUNT(*) FROM games WHERE status != ?', 'scheduled')} finished")
    print(f"scores      : {q('SELECT COUNT(*) FROM scores')} cells, "
          f"{q('SELECT COUNT(DISTINCT team) FROM scores')} teams")
    print(f"transactions: {q('SELECT COUNT(*) FROM transactions')} rows over "
          f"{q('SELECT COUNT(DISTINCT game_id) FROM transactions')} game(s)")
    rej = q("SELECT COUNT(*) FROM transactions WHERE accepted=0")
    tot = q("SELECT COUNT(*) FROM transactions")
    if tot:
        print(f"rejections  : {rej} ({rej/tot*100:.1f}%) -- the only rows that bound `t`")
    top = con.execute(
        "SELECT team, SUM(score) s FROM scores GROUP BY team ORDER BY s DESC LIMIT 5").fetchall()
    if top:
        print("leaders     :")
        for r in top:
            print(f"  {r['team']:<28} {r['s']:>12,.2f}")


def main() -> int:
    p = argparse.ArgumentParser(prog="harvest")
    p.add_argument("--once", action="store_true", help="one catch-up pass, then exit")
    p.add_argument("--watch", action="store_true", help="keep catching up as games finish")
    p.add_argument("--stats", action="store_true", help="summarise what is stored")
    p.add_argument("--team", default=None, help="only this team (default: every team)")
    p.add_argument("--db", type=Path, default=DB)
    p.add_argument("--pause", type=float, default=0.5, help="seconds between requests")
    p.add_argument("--budget", type=int, default=400, help="max requests per pass")
    p.add_argument("--interval", type=float, default=300.0, help="--watch loop interval")
    a = p.parse_args()

    con = connect(a.db)
    if a.stats and not (a.once or a.watch):
        stats(con)
        return 0

    lb = Leaderboard()
    if a.once or not a.watch:
        n_scores, fetched = run_once(con, lb, a.team, a.pause, a.budget)
        print(f"\n{n_scores} score cell(s), {fetched} new transaction pull(s)")
        stats(con)
        return 0

    print(f"watching, every {a.interval:.0f}s. ctrl-c to stop.")
    try:
        while True:
            n_scores, fetched = run_once(con, lb, a.team, a.pause, a.budget)
            if fetched:
                print(f"  +{fetched} pull(s), {n_scores} score cell(s)")
            time.sleep(a.interval)
    except KeyboardInterrupt:
        print("\nstopped")
        stats(con)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
