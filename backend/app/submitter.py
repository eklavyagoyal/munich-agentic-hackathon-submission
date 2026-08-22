"""The ONLY module that writes to the tournament API. Guard rails:
- C2F_READONLY=1 in .env -> raises instead of PUTting (safe on every machine
  that is not THE runner; PUT is last-write-wins).
- dry_run -> logs the payload, never sends.
- The PUT response echoes the stored rows; we verify them against what we sent.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

import requests

from .config import DATA, TEAM_API_KEY, TEAM_BASE
from .policy import Bid

EVENTS = DATA / "events" / "v2.jsonl"


class ReadOnlyMachine(RuntimeError):
    pass


def log_event(kind: str, **fields) -> None:
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS.open("a") as f:
        f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(),
                            "kind": kind, **fields}) + "\n")


def submit(game_id: int, bids: list[Bid], dry_run: bool = True) -> dict:
    payload = [{"index": b.index, "charge_price": b.charge_price,
                "acceptance_limit": b.acceptance_limit} for b in bids]
    if dry_run:
        log_event("dry_run", game=game_id, payload=payload)
        return {"ok": True, "dry_run": True, "n": len(payload)}
    if os.environ.get("C2F_READONLY"):
        raise ReadOnlyMachine("C2F_READONLY is set — this machine must not submit")
    t0 = time.monotonic()
    r = requests.put(f"{TEAM_BASE}/api/games/{game_id}/submissions",
                     headers={"X-API-Key": TEAM_API_KEY, "Content-Type": "application/json"},
                     json=payload, timeout=(2.0, 8.0))
    ms = int((time.monotonic() - t0) * 1000)
    ok = r.status_code == 200
    echo = r.json() if ok else None
    echo_ok = None
    if ok and isinstance(echo, list):
        got = {(e["line_item_index"], round(e["charge_price"], 2), round(e["acceptance_limit"], 2))
               for e in echo}
        want = {(p["index"], round(p["charge_price"], 2), round(p["acceptance_limit"], 2))
                for p in payload}
        echo_ok = want <= got
    log_event("submit", game=game_id, status=r.status_code, ms=ms,
              n=len(payload), echo_ok=echo_ok,
              detail=None if ok else r.text[:300], payload=payload)
    return {"ok": ok, "status": r.status_code, "ms": ms, "echo_ok": echo_ok,
            "detail": None if ok else r.text[:300]}
