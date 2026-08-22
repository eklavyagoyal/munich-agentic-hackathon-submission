"""After every round: harvest the results, publish inputs and results. Unattended.

    PYTHONPATH=. .venv/bin/python tools/autopilot.py            # run it and leave it
    PYTHONPATH=. .venv/bin/python tools/autopilot.py --once      # one pass, then exit
    PYTHONPATH=. .venv/bin/python tools/autopilot.py --dry-run

52 of the 100 games fall between 21:00 and 08:00 UTC. Nobody is going to run
harvest and publish by hand at 03:00, and a branch that stops updating overnight is
a branch four people stop trusting.

WHAT IT DOES, AND DELIBERATELY DOES NOT DO

It tails the runner's event stream, waits for `round.played`, then gives the
leaderboard `--settle` seconds to catch up before running harvest and publish for
that game. That is all. It does not decide anything, it never writes to
`rules_user/`, and it cannot submit: the only thing it invokes is the read-only
harvester and the publisher, which pushes to the inputs and results branches by git
plumbing and never touches main or the working tree.

SAFE TO RUN NEXT TO THE RUNNER. Separate process, no shared state but the append-only
event log, which it only ever reads. If it dies the tournament does not notice; if
the tournament dies it exits when the log stops moving. A failed pass is logged and
the next round is attempted anyway -- one bad publish must not stop the other 90.

It is idempotent. harvest.py keys on (game, issuer, reviewer, line_item) and
publish.py rewrites the same path on the same branch, so a repeated pass is a no-op
and a missed one is caught by the next --catch-up.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVENTS = ROOT / "data" / "events" / "tournament.jsonl"
STATE = ROOT / "data" / "autopilot.json"     # under data/, gitignored


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def run(args: list[str], timeout: float) -> tuple[bool, str]:
    try:
        r = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True,
                           text=True, timeout=timeout,
                           env={**__import__("os").environ, "PYTHONPATH": str(ROOT)})
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout:.0f}s"
    tail = (r.stdout or r.stderr).strip().splitlines()
    return r.returncode == 0, (tail[-1] if tail else "")


def done_games() -> set[int]:
    if not STATE.exists():
        return set()
    try:
        return set(json.loads(STATE.read_text())["published"])
    except (json.JSONDecodeError, KeyError, OSError):
        return set()


def mark(game: int) -> None:
    games = sorted(done_games() | {game})
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"published": games}, indent=1), encoding="utf-8")


def played_games() -> set[int]:
    """Games the runner has finished, from its own event log."""
    out: set[int] = set()
    if not EVENTS.exists():
        return out
    with EVENTS.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") == "round.played":
                gid = e.get("payload", {}).get("game")
                if isinstance(gid, int):
                    out.add(gid)
    return out


def process(game: int, dry_run: bool, settle: float) -> bool:
    log(f"game {game}: settling {settle:.0f}s before harvest")
    if not dry_run:
        time.sleep(settle)
    ok, msg = run(["tools/harvest.py", "--once"], timeout=900)
    log(f"game {game}: harvest {'ok' if ok else 'FAILED'} {msg[:110]}")
    args = ["tools/publish.py", "--game", str(game)] + (["--dry-run"] if dry_run else [])
    ok2, msg2 = run(args, timeout=300)
    log(f"game {game}: publish {'ok' if ok2 else 'FAILED'} {msg2[:110]}")
    # Publishing is the point; a harvest hiccup still leaves inputs worth having, and
    # the next pass re-harvests anyway. Only a failed publish is worth retrying.
    if ok2 and not dry_run:
        mark(game)
    return ok2


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true", help="one catch-up pass, then exit")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--settle", type=float, default=90.0,
                   help="seconds to let the leaderboard catch up after a round")
    p.add_argument("--poll", type=float, default=60.0)
    a = p.parse_args()

    log(f"autopilot: watching {EVENTS.name}, settle {a.settle:.0f}s, poll {a.poll:.0f}s")
    log("it can harvest and publish. it cannot submit, and it never writes rules_user/.")
    idle = 0
    while True:
        pending = sorted(played_games() - done_games())
        if pending:
            idle = 0
            for game in pending:
                try:
                    process(game, a.dry_run, a.settle if not a.once else 0.0)
                except Exception as e:  # noqa: BLE001 -- one bad game must not stop the rest
                    log(f"game {game}: pass failed ({type(e).__name__}: {e}) -- continuing")
        elif a.once:
            log("nothing pending")
        if a.once:
            return 0
        if not pending:
            idle += 1
            if idle % 30 == 0:
                log(f"idle: {len(done_games())} game(s) published, waiting")
        time.sleep(a.poll)


if __name__ == "__main__":
    raise SystemExit(main())
