"""Pull EVERYTHING fresh: schedule, matrix, performance, all teams' transactions,
decryption keys, case archives; decrypt; convert invoices to text.

Idempotent and resumable: completed (game, team) transaction pulls and decrypted
cases are recorded in SQLite and skipped on re-run.

    .venv/bin/python -m backend.app.sync            # one full pass
    .venv/bin/python -m backend.app.sync --loop     # every 5 minutes
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import lb, team
from .config import CASES_EXTRACTED, CASES_ZIPS, DATA, V1_CASES_DIR
from .db import connect

WORKERS = 4  # polite parallelism against the public feed


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def sync_games(con) -> list[dict]:
    rows = lb.games()
    con.executemany("INSERT INTO games (id, start_time, status) VALUES (?,?,?) "
                    "ON CONFLICT(id) DO UPDATE SET start_time=excluded.start_time, status=excluded.status",
                    [(g["id"], g["start_time"], g["status"]) for g in rows])
    con.commit()
    print(f"games: {len(rows)} "
          f"({sum(1 for g in rows if g['status'] == 'completed')} completed)")
    return rows


def sync_matrix(con) -> list[str]:
    items = lb.matrix()
    teams = [r["team_name"] for r in items]
    cells = []
    for r in items:
        for i, v in enumerate(r["cells"], start=1):
            cells.append((i, r["team_name"], v))
    con.executemany("INSERT INTO scores (game_id, team, score) VALUES (?,?,?) "
                    "ON CONFLICT(game_id, team) DO UPDATE SET score=excluded.score", cells)
    con.commit()
    print(f"matrix: {len(teams)} teams × {len(items[0]['cells']) if items else 0} games")
    return teams


def sync_performance(con, teams: list[str]) -> None:
    for t in teams:
        try:
            p = lb.performance(t)
        except Exception as e:  # noqa: BLE001
            print(f"  performance {t}: {e}", file=sys.stderr)
            continue
        con.execute(
            "INSERT INTO performance VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(team) DO UPDATE SET income=excluded.income, costs=excluded.costs, "
            "net=excluded.net, issued_count=excluded.issued_count, issued_accepted=excluded.issued_accepted, "
            "reviewed_count=excluded.reviewed_count, reviewed_accepted=excluded.reviewed_accepted, "
            "reviewed_accepted_right=excluded.reviewed_accepted_right, "
            "reviewed_accepted_wrong=excluded.reviewed_accepted_wrong, "
            "reviewed_correct_rejections=excluded.reviewed_correct_rejections, "
            "reviewed_penalties=excluded.reviewed_penalties",
            (p["team_name"], p["income"], p["costs"], p["net"],
             p["issued_count"], p["issued_accepted"], p["reviewed_count"], p["reviewed_accepted"],
             p["reviewed_accepted_right"], p["reviewed_accepted_wrong"],
             p["reviewed_correct_rejections"], p["reviewed_penalties"]))
    con.commit()
    print(f"performance: {len(teams)} teams")


def sync_transactions(con, teams: list[str], completed: list[int]) -> None:
    done = {(r["game_id"], r["team"]) for r in con.execute("SELECT game_id, team FROM harvested")}
    todo = [(g, t) for g in completed for t in teams if (g, t) not in done]
    if not todo:
        print("transactions: up to date")
        return
    print(f"transactions: fetching {len(todo)} (game, team) pairs …")

    def fetch(pair):
        g, t = pair
        return g, t, lb.transactions(g, t)

    n_rows = 0
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for fut in cf.as_completed([ex.submit(fetch, p) for p in todo]):
            try:
                g, t, rows = fut.result()
            except Exception as e:  # noqa: BLE001
                print(f"  tx fetch failed: {e}", file=sys.stderr)
                continue
            con.executemany(
                "INSERT INTO transactions (game_id, issuer, reviewer, line_item, accepted, amount) "
                "VALUES (?,?,?,?,?,?) ON CONFLICT DO NOTHING",
                [(g, r["issuer"], r["reviewer"], r["line_item_index"],
                  1 if r["accepted"] else 0, r["amount"]) for r in rows])
            con.execute("INSERT INTO harvested (game_id, team, rows) VALUES (?,?,?) "
                        "ON CONFLICT DO NOTHING", (g, t, len(rows)))
            con.commit()
            n_rows += len(rows)
    total = con.execute("SELECT COUNT(*) c FROM transactions").fetchone()["c"]
    print(f"transactions: +{n_rows} fetched, {total} unique rows in db")


def sync_zips() -> int:
    """Copy the organizers' encrypted archives into data/ (one-time, cheap)."""
    CASES_ZIPS.mkdir(parents=True, exist_ok=True)
    n = 0
    if V1_CASES_DIR.is_dir():
        for z in sorted(V1_CASES_DIR.glob("*.zip")):
            dst = CASES_ZIPS / z.name
            if not dst.exists():
                shutil.copy2(z, dst)
                n += 1
    have = len(list(CASES_ZIPS.glob("*.zip")))
    print(f"zips: {have} archives ({n} newly copied)")
    return have


def archive_for(game_id: int) -> Path | None:
    for pat in (f"case_{game_id:02d}.zip", f"case_{game_id}.zip"):
        p = CASES_ZIPS / pat
        if p.is_file():
            return p
    return None


def sync_keys(con, games_rows: list[dict]) -> None:
    have = {r["game_id"] for r in con.execute("SELECT game_id FROM keys")}
    started = [g["id"] for g in games_rows
               if parse_ts(g["start_time"]) <= now_utc() and g["id"] not in have]
    for gid in started:
        try:
            k = team.fetch_key(gid)
        except Exception as e:  # noqa: BLE001
            print(f"  key {gid}: {e}", file=sys.stderr)
            continue
        con.execute("INSERT INTO keys (game_id, key) VALUES (?,?) ON CONFLICT DO NOTHING", (gid, k))
        con.commit()
    n = con.execute("SELECT COUNT(*) c FROM keys").fetchone()["c"]
    print(f"keys: {n} total ({len(started)} newly tried)")


def pdf_to_text(pdf: Path) -> None:
    txt = pdf.with_suffix(".pdf.txt")
    if txt.exists():
        return
    exe = shutil.which("pdftotext")
    if not exe:
        return
    subprocess.run([exe, "-layout", str(pdf), str(txt)], capture_output=True, timeout=30)


def sync_extract(con) -> None:
    from .decrypt import DecryptError, extract
    keys = {r["game_id"]: r["key"] for r in con.execute("SELECT game_id, key FROM keys")}
    done = {r["game_id"] for r in con.execute("SELECT game_id FROM cases")}
    n_new = 0
    for gid, key in sorted(keys.items()):
        if gid in done:
            continue
        arc = archive_for(gid)
        if arc is None:
            print(f"  extract {gid}: no archive", file=sys.stderr)
            continue
        dest = CASES_EXTRACTED / f"game_{gid:03d}"
        try:
            files = extract(arc, key, dest)
        except DecryptError as e:
            print(f"  extract {gid}: {e}", file=sys.stderr)
            continue
        for f in files:
            if f.suffix.lower() == ".pdf":
                pdf_to_text(f)
        con.execute("INSERT INTO cases (game_id, dir, n_files) VALUES (?,?,?) "
                    "ON CONFLICT DO NOTHING", (gid, str(dest), len(files)))
        con.commit()
        n_new += 1
    total = con.execute("SELECT COUNT(*) c FROM cases").fetchone()["c"]
    print(f"cases: {total} extracted ({n_new} new)")


def run_once() -> None:
    DATA.mkdir(exist_ok=True)
    con = connect()
    t0 = time.monotonic()
    games_rows = sync_games(con)
    teams = sync_matrix(con)
    sync_performance(con, teams)
    completed = [g["id"] for g in games_rows if g["status"] == "completed"]
    sync_transactions(con, teams, completed)
    sync_zips()
    sync_keys(con, games_rows)
    sync_extract(con)
    print(f"sync done in {time.monotonic() - t0:.1f}s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true", help="repeat every 5 minutes")
    a = ap.parse_args()
    while True:
        run_once()
        try:
            from .bounds import reconstruct, validate
            con = connect()
            reconstruct(con)
            validate(con)
        except Exception as e:  # noqa: BLE001
            print(f"bounds refresh failed: {e}", file=sys.stderr)
        if not a.loop:
            break
        time.sleep(300)


if __name__ == "__main__":
    main()
