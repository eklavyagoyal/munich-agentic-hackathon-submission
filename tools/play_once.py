"""Play one game right now, off the schedule. Proves the live round trip before it matters.

    PYTHONPATH=. .venv/bin/python tools/play_once.py 0 --dry-run   # key + pipeline, no PUT
    PYTHONPATH=. .venv/bin/python tools/play_once.py 0             # ... and the real PUT

Game 0 is the organisers' permanent test game (see LiveApi's docstring), so this is safe
to run against the live API at any time. Same wiring as tools/serve.py -- same rule set,
same archive lookup, same client -- so a green run here means the daemon's hot path works.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from c2f.core.events import EventBus
from c2f.estimate.pricebook import fallback
from c2f.rules.engine import RuleEngine
from c2f.rules.loader import load_rules
from c2f.rules.protocol import RuleState
from c2f.runner import RoundConfig, Runner
from c2f.scheduler import find_archive
from c2f.submit.client import LiveApi
from tools.serve import default_cases_dir

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("game_id", type=int)
    p.add_argument("--cases-dir", type=Path, default=None)
    p.add_argument("--dry-run", action="store_true", help="run everything except the PUT")
    p.add_argument("--shadow", action="store_true", help="leave rules SHADOW (default: ACTIVE)")
    p.add_argument("--events", type=Path, default=ROOT / "data" / "events" / "play_once.jsonl")
    a = p.parse_args()
    cases_dir = a.cases_dir or default_cases_dir()

    if os.environ.get("C2F_READONLY", "").strip() not in ("", "0", "false", "no"):
        print("\n*** C2F_READONLY is set -- this machine will REFUSE to submit. ***")
        print("*** Backtesting and watching are fine. Unset it in .env to arm. ***\n")
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
    archive = find_archive(cases_dir, a.game_id)
    if archive is None:
        print(f"no archive for game {a.game_id} in {cases_dir}")
        return 1
    print(f"archive : {archive}")

    bus = EventBus(a.events)
    engine = RuleEngine(fallback)
    report = load_rules(engine, ROOT / "rules_user")
    print(f"rules   : {', '.join(report.loaded) or '(none)'}")
    if report.rejected:
        print(f"REJECTED: {report.rejected}")
    if not a.shadow:
        for r in engine.rules:
            engine.set_state(r.name, RuleState.ACTIVE)
    print(f"state   : {'SHADOW' if a.shadow else 'ACTIVE'}")

    # Where the append-only log ends now; everything after this offset is this run.
    a.events.parent.mkdir(parents=True, exist_ok=True)
    log_start = a.events.stat().st_size if a.events.exists() else 0

    api = LiveApi(dry_run=a.dry_run)
    print(f"mode    : {'DRY RUN (no PUT)' if a.dry_run else 'LIVE (will PUT)'}\n")
    try:
        subs = Runner(api, engine, bus).run_round(
            RoundConfig(round_no=a.game_id, case_id=str(a.game_id), archive=archive))
    except Exception as e:  # noqa: BLE001 -- report it, do not traceback-spam at 03:00
        print(f"FAILED  : {type(e).__name__}: {e}")
        bus.close()
        return 1
    finally:
        pass

    for sub in subs:
        print(f"submission tier {sub.tier}: {len(sub.decisions)} line items, "
              f"charge {sum(d.a for d in sub.decisions):.2f} / "
              f"limit {sum(d.b for d in sub.decisions):.2f} EUR")
    last = subs[-1]
    print(f"\n{'#':>2}  {'median':>9} {'sigma':>6}  {'a':>9} {'b':>9}  {'cov':>5}  rules")
    print("-" * 92)
    for d in last.decisions:
        med = f"{d.belief.median:9.2f}" if d.belief else " " * 9
        sig = f"{d.belief.sigma:6.2f}" if d.belief else " " * 6
        print(f"{d.idx:>2}  {med} {sig}  {d.a:9.2f} {d.b:9.2f}  {str(d.covered):>5}  "
              f"{' -> '.join(e['rule'] for e in d.trace)}")
    print("-" * 92)
    bus.close()

    # "run_round returned" and "the server stored our numbers" are different claims.
    # Read the outcome back out of the event log and make it the exit code, so a failed
    # PUT can never look like a successful run -- to a human or to a wrapper script.
    import json
    sent, verified = [], []
    with a.events.open("r", encoding="utf-8") as fh:
        fh.seek(log_start)
        lines = fh.read().splitlines()
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev["type"] == "submission.sent":
            sent.append(ev["payload"])
        elif ev["type"] == "submission.verified":
            verified.append(ev["payload"])
    print()
    for s_ in sent:
        print(f"PUT tier {s_['tier']}: ok={s_['ok']} status={s_['status']} "
              f"{s_['ms']}ms {s_.get('detail','')}")
    for v in verified:
        print(f"echo tier {v['tier']}: ok={v['ok']} {v.get('detail','')}")
    print(f"events -> {a.events}")
    if a.dry_run:
        return 0
    if not sent or not all(s_["ok"] for s_ in sent):
        print("FAILED: no submission landed")
        return 1
    if any(v["ok"] is False for v in verified):
        print("FAILED: server stored something other than what we sent")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
