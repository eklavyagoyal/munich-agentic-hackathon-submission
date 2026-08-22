"""Run one full round against the local fixture and print what happened.

    PYTHONPATH=. .venv/bin/python tools/run_demo.py [--activate]

No credentials needed -- this is the whole pipeline against MockApi.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from c2f.core.events import EventBus
from c2f.estimate.pricebook import fallback
from c2f.rules.engine import RuleEngine
from c2f.rules.loader import load_rules
from c2f.rules.protocol import RuleState
from c2f.runner import RoundConfig, Runner
from c2f.submit.client import MockApi
from tools.make_fixture import PASSWORD

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    activate = "--activate" in sys.argv
    archive = ROOT / "data" / "cases" / "case-0.zip"
    if not archive.exists():
        print("no fixture; run tools/make_fixture.py first")
        return 1

    bus = EventBus(ROOT / "data" / "events" / "demo.jsonl")
    engine = RuleEngine(fallback)
    report = load_rules(engine, ROOT / "rules_user")
    print(f"rules loaded : {', '.join(report.loaded) or '(none)'}")
    if report.rejected:
        print(f"rules REJECTED: {report.rejected}")
    if activate:
        for r in engine.rules:
            engine.set_state(r.name, RuleState.ACTIVE)
        print("all rules promoted to ACTIVE")

    api = MockApi(keys={"case-0": PASSWORD})
    sub = Runner(api, engine, bus).run_round(RoundConfig(1, "case-0", archive))[0]

    print(f"\ncase {sub.case_id}, tier {sub.tier}, {len(sub.decisions)} line items\n")
    print(f"{'#':>2}  {'median':>9} {'sigma':>6}  {'a':>9} {'b':>9}  {'cov':>4}  rules")
    print("-" * 92)
    for d in sub.decisions:
        med = f"{d.belief.median:9.2f}" if d.belief else " " * 9
        sig = f"{d.belief.sigma:6.2f}" if d.belief else " " * 6
        rules = " -> ".join(e["rule"] for e in d.trace)
        print(f"{d.idx:>2}  {med} {sig}  {d.a:9.2f} {d.b:9.2f}  {str(d.covered):>4}  {rules}")
    print("-" * 92)
    print(f"{'':>2}  {'':>9} {'':>6}  {sum(d.a for d in sub.decisions):9.2f} "
          f"{sum(d.b for d in sub.decisions):9.2f}   totals (gross EUR)")
    bus.close()
    print(f"\nevents -> data/events/demo.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
