"""Play a round end to end: key -> decrypt -> parse -> estimate -> policy -> submit.

    .venv/bin/python -m backend.app.play --game 0                # dry run (no PUT)
    .venv/bin/python -m backend.app.play --game 0 --submit       # real PUT (game 0 = test game)
    .venv/bin/python -m backend.app.play --watch --submit        # live loop over the schedule

The watch loop derives "when" from the published schedule (no hardcoded cadence)
and never plays a game whose archive is missing.
"""
from __future__ import annotations

import argparse
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from . import team
from .config import CASES_EXTRACTED, CASES_ZIPS, DATA
from .db import connect
from .decrypt import extract
from .estimate import estimate
from .parse import load_case
from .policy import A_MULT, B_MULT, decide
from .submitter import log_event, submit


def archive_for(game_id: int) -> Path | None:
    for pat in (f"case_{game_id:02d}.zip", f"case_{game_id}.zip"):
        p = CASES_ZIPS / pat
        if p.is_file():
            return p
    return None


def play_game(game_id: int, do_submit: bool) -> dict:
    t_start = time.monotonic()
    tl: dict[str, int] = {}

    def mark(name: str) -> None:
        tl[name] = int((time.monotonic() - t_start) * 1000)

    arc = archive_for(game_id)
    if arc is None:
        raise RuntimeError(f"no archive for game {game_id} in {CASES_ZIPS}")

    key = team.fetch_key(game_id)
    mark("key")

    dest = CASES_EXTRACTED / f"game_{game_id:03d}"
    if not any(dest.glob("**/*")) if dest.exists() else True:
        pass
    if not dest.exists() or not any(dest.iterdir()):
        extract(arc, key, dest)
    mark("decrypt")

    case = load_case(game_id, dest)
    mark("parse")

    t_hat, meta = estimate(case)
    mark("estimate")

    bids = decide(t_hat)
    result = submit(game_id, bids, dry_run=not do_submit)
    mark("submit")

    log_event("round", game=game_id, timeline_ms=tl, n_items=len(case.items),
              a_mult=A_MULT, b_mult=B_MULT,
              models=meta["models_answered"],
              bids=[{"i": b.index, "a": b.charge_price, "b": b.acceptance_limit,
                     "src": meta["source"].get(b.index, "?")} for b in bids],
              submit=result)
    print(f"game {game_id}: {len(case.items)} items · timeline {tl} · submit {result}")
    for b in bids:
        it = case.items[b.index - 1]
        print(f"  {b.index:2d} a={b.charge_price:>10.2f} b={b.acceptance_limit:>10.2f} "
              f"[{meta['source'].get(b.index, '?'):>10s}] {it.description[:55]}")
    return result


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def watch(do_submit: bool) -> None:
    from . import lb
    played: set[int] = set()
    print(f"watch: A_MULT={A_MULT} B_MULT={B_MULT} submit={do_submit}")
    while True:
        try:
            rows = lb.games()
        except Exception as e:  # noqa: BLE001
            print(f"schedule fetch failed: {e}; retrying in 30s")
            time.sleep(30)
            continue
        now = datetime.now(timezone.utc)
        nxt = None
        for g in rows:
            st = parse_ts(g["start_time"])
            if g["id"] in played or g["status"] == "completed":
                continue
            # play if started less than 50s ago, else wait for the next start
            age = (now - st).total_seconds()
            if -1.0 <= age <= 50.0:
                nxt = ("now", g, st)
                break
            if st > now:
                nxt = ("wait", g, st)
                break
        if nxt is None:
            print("schedule exhausted")
            return
        mode, g, st = nxt
        if mode == "wait":
            delay = (st - datetime.now(timezone.utc)).total_seconds() + 0.5
            print(f"next game {g['id']} at {g['start_time']} (in {delay:.0f}s)")
            time.sleep(max(min(delay, 300), 0.2))
            continue
        try:
            play_game(g["id"], do_submit)
        except Exception as e:  # noqa: BLE001
            log_event("error", game=g["id"], error=f"{type(e).__name__}: {e}")
            print(f"game {g['id']} FAILED: {type(e).__name__}: {e}")
        played.add(g["id"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", type=int)
    ap.add_argument("--submit", action="store_true", help="actually PUT (default: dry run)")
    ap.add_argument("--watch", action="store_true")
    a = ap.parse_args()
    DATA.mkdir(exist_ok=True)
    if a.watch:
        watch(a.submit)
    elif a.game is not None:
        play_game(a.game, a.submit)
    else:
        ap.error("--game N or --watch")


if __name__ == "__main__":
    main()
