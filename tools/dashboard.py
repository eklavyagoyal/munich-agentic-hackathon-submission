"""Live dashboard -- what the pipeline is doing, right now (PIPELINE.md §1, §2).

    PYTHONPATH=. .venv/bin/python tools/dashboard.py

A SECOND PROCESS, deliberately. It tails the append-only event stream and never
imports, calls or blocks the runner. A wedged websocket, fifty page reloads or a
browser left open overnight cannot add a millisecond to the 60-second path.

Stdlib only. Nothing to install 20 minutes before a tournament.

Two guards against getting us rate-limited or banned:

  1. ONE upstream leaderboard fetch per TTL, shared by every open tab. The
     browser polls US; we poll the leaderboard on a fixed, slow timer. Ten
     dashboards on ten laptops still cost the organisers one request per 90s.
     On failure we serve stale and back off -- we never retry-storm.
  2. Secrets are scrubbed before anything reaches a browser. Decryption keys and
     TEAM_API_KEY must not end up on a projector, in a screenshot or in a
     screen recording.
"""
from __future__ import annotations

import argparse
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, parse_qs

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from c2f.leaderboard import Leaderboard

ROOT = Path(__file__).resolve().parent.parent

# -- secret scrubbing ------------------------------------------------------
# Belt and braces: the emitters already keep key material out of the stream
# (`key.received` carries a case id and a duration, never the key). This is the
# second layer, because "no event carries a secret" is a property that a
# teammate adding an event tomorrow can break without noticing.
SECRET_KEYS = re.compile(r"key|token|secret|password|passwd|auth(?!or)|credential", re.I)
SAFE_KEYS = {"case_id", "n_items", "key.received", "keys"}


def scrub(value: Any, kname: str = "") -> Any:
    if SECRET_KEYS.search(kname) and kname not in SAFE_KEYS:
        if isinstance(value, str) and value:
            return f"<redacted {len(value)} chars>"
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        return "<redacted>"
    if isinstance(value, dict):
        return {k: scrub(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v, kname) for v in value]
    return value


# -- event tail ------------------------------------------------------------
class EventTail:
    """Reads the JSONL sink. Read-only: we never hold a lock the writer wants."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def since(self, cursor: int, limit: int = 2000) -> tuple[list[dict], int]:
        """`cursor` is lines already delivered, NOT the last event `seq`.

        The bus numbers events from 1 per process and appends to the same file,
        so a restarted runner re-emits seq 1, 2, 3... A seq-based cursor would
        sit at 400 and go permanently blind exactly when someone restarts the
        runner mid-tournament -- the moment you most need to be watching."""
        if not self.path.is_file():
            return [], cursor
        out: list[dict] = []
        n = 0
        try:
            with self.path.open("r", encoding="utf-8", errors="replace") as fh:
                for raw in fh:
                    n += 1                      # count every physical line, so
                    if n <= cursor:             # the cursor stays aligned even
                        continue                # with blank or torn ones
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        n -= 1                  # torn last line: the writer is
                        break                   # mid-flush, re-read it next poll
                    ev["payload"] = scrub(ev.get("payload", {}))
                    out.append(ev)
        except OSError:
            return [], cursor
        return out[-limit:], n


# -- leaderboard cache -----------------------------------------------------
class LeaderboardCache:
    """One upstream fetch per TTL, no matter how many browsers are watching."""

    TTL = 90.0            # standings
    GAMES_TTL = 600.0     # the schedule barely changes; scheduler.py uses 600s too
    FAIL_BACKOFF = 300.0  # after an error, stay away for five minutes

    def __init__(self, team: str | None = None) -> None:
        self.lb = Leaderboard()
        self.team = team
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {"standings": [], "games": [], "skew_s": None,
                                      "team": team, "performance": None, "matchup": [],
                                      "fetched_at": None, "error": None, "upstream_calls": 0}
        self._at = 0.0
        self._games_at = 0.0
        self._blocked_until = 0.0

    def get(self) -> dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            if now < self._blocked_until or (now - self._at) < self.TTL:
                return dict(self._data)          # cache hit: zero upstream cost
            self._at = now
        try:
            standings = self.lb.standings(game_limit=20)
            calls = 1
            # Opponent data rides the same 90s TTL. Two extra calls per TTL only
            # once we know our own team name -- and only ever per TTL, never per
            # browser tab. This is the whole rate-limit story in one place.
            perf, matchup = None, []
            if self.team:
                try:
                    perf = self.lb.performance(self.team)
                    matchup = self.lb.matchup(self.team)
                    calls += 2
                except Exception:  # noqa: BLE001 -- 404 until we have played a round
                    pass
            games = self._data.get("games") or []
            if not games or (now - self._games_at) >= self.GAMES_TTL:
                games = [{"id": g.id, "start_time": g.start_time.isoformat(),
                          "status": g.status} for g in self.lb.games()]
                self._games_at = now
                calls += 1
            with self._lock:
                self._data = {
                    "standings": standings, "games": games,
                    "team": self.team, "performance": perf, "matchup": matchup,
                    "skew_s": round(self.lb.clock_skew_s, 2),
                    "server_now": self.lb.server_now().isoformat(),
                    "fetched_at": time.time(), "error": None,
                    "upstream_calls": self._data.get("upstream_calls", 0) + calls,
                }
                self._blocked_until = 0.0
                return dict(self._data)
        except Exception as e:  # noqa: BLE001 -- a dashboard must not die on a 500
            with self._lock:
                self._blocked_until = now + self.FAIL_BACKOFF
                self._data["error"] = f"{type(e).__name__}: {e} (backing off {self.FAIL_BACKOFF:.0f}s)"
                return dict(self._data)


def make_handler(tail: EventTail, cache: LeaderboardCache, page: str):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _send(self, body: bytes, ctype: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            # The Next UI runs on :3000 and reads this API. Localhost only -- this
            # process is bound to 127.0.0.1 and must stay that way.
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            u = urlparse(self.path)
            if u.path == "/":
                return self._send(page.encode(), "text/html; charset=utf-8")
            if u.path == "/api/events":
                q = parse_qs(u.query)
                try:
                    since = int(q.get("since", ["0"])[0])
                except ValueError:
                    since = 0
                events, cursor = tail.since(since)
                return self._send(json.dumps({"events": events, "seq": cursor}).encode(),
                                  "application/json")
            if u.path == "/api/leaderboard":
                return self._send(json.dumps(cache.get(), default=str).encode(),
                                  "application/json")
            self.send_error(404)

        def log_message(self, *a) -> None:  # keep the console for the runner
            pass

    return Handler


def main() -> int:
    p = argparse.ArgumentParser(prog="dashboard")
    p.add_argument("--events", type=Path,
                   default=ROOT / "data" / "events" / "tournament.jsonl")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--team", default=None, help="our team name, for the standings highlight")
    a = p.parse_args()

    page = (ROOT / "tools" / "dashboard.html").read_text(encoding="utf-8")
    page = page.replace("__TEAM__", json.dumps(a.team))
    page = page.replace("__EVENTS_PATH__", json.dumps(str(a.events)))

    tail = EventTail(a.events)
    cache = LeaderboardCache(a.team)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(tail, cache, page))
    srv.daemon_threads = True
    print(f"data API   : http://127.0.0.1:{a.port}   (the UI reads this)")
    print(f"REAL UI    : http://localhost:3000        <- cd ui && npm install && npm run dev")
    print(f"fallback   : http://127.0.0.1:{a.port}   no-build page, only if node is down")
    print(f"tailing    : {a.events}"
          f"{'' if a.events.is_file() else '  (not there yet -- appears when a round runs)'}")
    print(f"leaderboard: 1 upstream fetch per {LeaderboardCache.TTL:.0f}s, shared by all tabs")
    print("secrets    : scrubbed before anything reaches a browser\nctrl-c to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
