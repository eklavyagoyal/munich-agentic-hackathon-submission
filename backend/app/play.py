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
from .policy import decide, load_policy
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

    def phase(stage: str, status: str, **payload) -> None:
        # Observability must never cost a round.
        try:
            log_event("phase", game=game_id, stage=stage, status=status,
                      t_ms=int((time.monotonic() - t_start) * 1000), **payload)
        except Exception:  # noqa: BLE001
            pass

    arc = archive_for(game_id)
    if arc is None:
        raise RuntimeError(f"no archive for game {game_id} in {CASES_ZIPS}")
    phase("key", "start", archive=arc.name)

    key = team.fetch_key(game_id)
    mark("key")
    phase("key", "done", ms=tl["key"])

    dest = CASES_EXTRACTED / f"game_{game_id:03d}"
    if not dest.exists() or not any(dest.iterdir()):
        extract(arc, key, dest)
    mark("decrypt")
    files = [{"name": f.name, "kb": round(f.stat().st_size / 1024, 1)}
             for f in sorted(dest.rglob("*")) if f.is_file()]
    phase("decrypt", "done", ms=tl["decrypt"], files=files)

    case = load_case(game_id, dest)
    mark("parse")
    phase("parse", "done", ms=tl["parse"], n_items=len(case.items),
          items=[{"i": it.idx, "desc": it.description, "qty": it.qty, "unit": it.unit}
                 for it in case.items])

    policy = load_policy()
    models = tuple(m.strip() for m in str(policy["models"]).split(",") if m.strip())
    phase("estimate", "start", models=list(models), anchors=bool(policy.get("anchors", True)))
    t_hat, meta = estimate(case, models=models, use_anchors=bool(policy.get("anchors", True)))
    mark("estimate")
    phase("anchors", "done", n=len(meta.get("anchors", [])), anchors=meta.get("anchors", []))
    phase("estimate", "done", ms=tl["estimate"] - tl["parse"],
          models_answered=meta["models_answered"], errors=meta.get("errors", {}))

    try:
        from .anchors import anchors_per_item
        per_item = anchors_per_item(case, exclude_game=game_id)
    except Exception as e:  # noqa: BLE001
        print(f"  per-item anchors failed: {type(e).__name__}: {e}")
        per_item = {}
    bids = decide(t_hat, policy, anchors_by_item=per_item)
    phase("decide", "done", n=len(bids),
          total_a=round(sum(b.charge_price for b in bids), 2),
          total_b=round(sum(b.acceptance_limit for b in bids), 2))
    result = submit(game_id, bids, dry_run=not do_submit)
    mark("submit")
    phase("submit", "done", ms=tl["submit"], result=result)

    log_event("round", game=game_id, timeline_ms=tl, n_items=len(case.items),
              policy=policy, models=meta["models_answered"], errors=meta.get("errors", {}),
              prompt=meta.get("prompt", ""),
              per_model=meta.get("per_model", {}),
              items=[{"i": it.idx, "desc": it.description, "qty": it.qty, "unit": it.unit}
                     for it in case.items],
              bids=[{"i": b.index, "a": b.charge_price, "b": b.acceptance_limit,
                     "t_hat": round(t_hat.get(b.index, 0), 2),
                     "src": meta["source"].get(b.index, "?"), "b_src": b.b_src} for b in bids],
              submit=result)
    print(f"game {game_id}: {len(case.items)} items · timeline {tl} · submit {result}")
    for b in bids:
        it = case.items[b.index - 1]
        print(f"  {b.index:2d} a={b.charge_price:>10.2f} b={b.acceptance_limit:>10.2f} "
              f"[{meta['source'].get(b.index, '?'):>10s}] {it.description[:55]}")
    return result


def emergency_game(game_id: int, do_submit: bool) -> None:
    """Best-effort round with no LLM: parse, per-unit fallback rates, submit."""
    from .estimate import fallback_estimates

    arc = archive_for(game_id)
    if arc is None:
        raise RuntimeError(f"no archive for game {game_id}")
    key = team.fetch_key(game_id, poll_for=10.0)
    dest = CASES_EXTRACTED / f"game_{game_id:03d}"
    if not dest.exists() or not any(dest.iterdir()):
        extract(arc, key, dest)
    case = load_case(game_id, dest)
    t_hat = fallback_estimates(case)
    bids = decide(t_hat)
    result = submit(game_id, bids, dry_run=not do_submit)
    log_event("round", game=game_id, emergency=True, n_items=len(case.items),
              bids=[{"i": b.index, "a": b.charge_price, "b": b.acceptance_limit,
                     "t_hat": round(t_hat.get(b.index, 0), 2), "src": "fallback"}
                    for b in bids],
              submit=result)
    print(f"game {game_id}: EMERGENCY submitted {len(bids)} items -> {result}")


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def watch(do_submit: bool) -> None:
    from . import lb
    from .submitter import load_submitted_ok
    # Survive restarts: a game this machine already PUT successfully is never
    # played again, even when its submission window is still open.
    played: set[int] = load_submitted_ok()
    print(f"watch: policy={load_policy()} submit={do_submit} "
          f"already_submitted={sorted(played)[-5:] if played else []}")
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
            # Emergency path: a defaulted round (0/0 on every item) both rejects
            # every fair charge (1.5a penalty) AND earns nothing — the worst
            # possible outcome. Any submission beats none. No LLM, no frills:
            # parse + per-unit fallback rates + submit.
            # NEVER double-submit: if the main path already PUT successfully
            # (the exception came after), the good submission must stand.
            from .submitter import SUBMITTED_OK
            try:
                if g["id"] in SUBMITTED_OK:
                    print(f"game {g['id']}: main path already submitted — no emergency")
                else:
                    emergency_game(g["id"], do_submit)
            except Exception as e2:  # noqa: BLE001
                log_event("error", game=g["id"], error=f"emergency failed: {type(e2).__name__}: {e2}")
                print(f"game {g['id']} EMERGENCY FAILED: {type(e2).__name__}: {e2}")
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
