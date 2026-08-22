"""The tournament daemon. Start this once and leave it running.

    PYTHONPATH=. .venv/bin/python tools/serve.py --activate
    PYTHONPATH=. .venv/bin/python tools/serve.py --plan          # show the schedule, play nothing

52 of the 100 games fall between 21:00 and 08:00 UTC, so this is not a convenience --
it is most of the tournament. Every round it plays cleanly is score; every round it
misses is the -3247 outcome from GAMEPLAN §3.

Needs TEAM_API_KEY (put it in .env) and the encrypted case archives in --cases-dir.
Runs with neither --dry-run nor a model key: the price book alone still produces real
numbers, it just cannot judge relatedness.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from c2f.core.events import EventBus
from c2f.estimate.pricebook import fallback
from c2f.leaderboard import Leaderboard
from c2f.rules.engine import RuleEngine
from c2f.rules.loader import load_rules
from c2f.rules.protocol import RuleState
from c2f.runner import Runner
from c2f.scheduler import Scheduler, SchedulerConfig
from c2f.submit.client import LiveApi

ROOT = Path(__file__).resolve().parent.parent

# Where the organisers' archives actually land, in order of preference. Searched so
# nobody has to remember a flag at 03:00; --cases-dir still overrides.
CASE_DIRS = (
    ROOT / "public-cases-ehl" / "cases",
    ROOT / "cases",
    ROOT / "data" / "cases",
)


def default_cases_dir() -> Path:
    for d in CASE_DIRS:
        if d.is_dir() and any(d.glob("*.zip")):
            return d
    return CASE_DIRS[0]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cases-dir", type=Path, default=None)
    p.add_argument("--events", type=Path, default=ROOT / "data" / "events" / "tournament.jsonl")
    p.add_argument("--activate", action="store_true",
                   help="promote loaded rules to ACTIVE (they load as SHADOW)")
    p.add_argument("--dry-run", action="store_true", help="never POST a submission")
    p.add_argument("--plan", action="store_true", help="print the schedule and exit")
    p.add_argument("--lead", type=float, default=3.0, help="seconds to wake before a start")
    a = p.parse_args()
    if a.cases_dir is None:
        a.cases_dir = default_cases_dir()

    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
    lb = Leaderboard()

    games = lb.games()
    if not games:
        print("could not read the schedule -- is the leaderboard up?")
        return 1
    now = lb.server_now()
    upcoming = [g for g in games if g.scheduled and g.start_time >= now]
    cadence = Leaderboard.cadence(games)
    print(f"schedule   : {len(games)} games, {len(upcoming)} still ahead")
    print(f"cadence    : {cadence:.1f}s" if cadence else "cadence    : unknown")
    print(f"clock skew : {lb.clock_skew_s:+.2f}s (ours vs server; corrected for)")
    if upcoming:
        nxt = upcoming[0]
        print(f"next       : game {nxt.id} at {nxt.start_time.isoformat()} "
              f"(in {(nxt.start_time - now).total_seconds():.0f}s)")
    if a.plan:
        for g in upcoming[:12]:
            print(f"  game {g.id:>3}  {g.start_time.isoformat()}")
        return 0

    if not a.cases_dir.is_dir():
        print(f"\ncases dir {a.cases_dir} does not exist -- nothing to decrypt, refusing to start")
        return 1
    archives = sorted(a.cases_dir.glob("*.zip"))
    print(f"archives   : {len(archives)} in {a.cases_dir}")
    if not archives:
        print("no archives -- every round would be skipped. Refusing to start.")
        return 1

    bus = EventBus(a.events)
    engine = RuleEngine(fallback)
    report = load_rules(engine, ROOT / "rules_user")
    print(f"rules      : {', '.join(report.loaded) or '(none)'}")
    if report.rejected:
        print(f"REJECTED   : {report.rejected}")
    if a.activate:
        for r in engine.rules:
            engine.set_state(r.name, RuleState.ACTIVE)
        print("           : all promoted to ACTIVE")
    else:
        print("           : all SHADOW -- pass --activate to actually apply them")

    api = LiveApi(dry_run=a.dry_run)
    sched = Scheduler(lb, Runner(api, engine, bus), bus,
                      SchedulerConfig(cases_dir=a.cases_dir, lead_s=a.lead))

    print(f"\nrunning{' (DRY RUN)' if a.dry_run else ''}. ctrl-c to stop.\n")
    try:
        state = sched.run()
    except KeyboardInterrupt:
        state = sched.state
        print("\ninterrupted")
    finally:
        bus.close()

    print(f"played {len(state.played)} | failed {len(state.failed)} | skipped {len(state.skipped)}")
    if state.failed:
        print(f"  failed games : {state.failed}")
    if state.skipped:
        print(f"  skipped games: {state.skipped}  (no archive found)")
    print(f"events -> {a.events}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
