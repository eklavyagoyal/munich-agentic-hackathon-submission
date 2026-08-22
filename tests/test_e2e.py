"""Full round against the encrypted fixture: key -> decrypt -> parse -> rules
-> decide -> submit -> verify. This is build-order step 1, the gate that
everything else waits on."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from c2f.core.events import EventBus, read_events
from c2f.core.invariants import check_decision
from c2f.estimate.pricebook import fallback
from c2f.rules.engine import RuleEngine
from c2f.rules.loader import load_rules
from c2f.rules.protocol import RuleState
from c2f.runner import RoundConfig, Runner
from c2f.submit.client import MockApi
from tools.make_fixture import PASSWORD

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "data" / "cases" / "case-0.zip"


@pytest.fixture(scope="module", autouse=True)
def fixture_archive():
    if not ARCHIVE.exists():
        subprocess.run([sys.executable, str(ROOT / "tools" / "make_fixture.py")],
                       cwd=ROOT, check=True, capture_output=True)


def build(tmp_path, activate_all=False):
    bus = EventBus(tmp_path / "events.jsonl")
    engine = RuleEngine(fallback)
    report = load_rules(engine, ROOT / "rules_user")
    assert report.ok(), report.rejected
    if activate_all:
        for r in engine.rules:
            engine.set_state(r.name, RuleState.ACTIVE)
    api = MockApi(keys={"case-0": PASSWORD}, store=tmp_path / "submission.json")
    return bus, engine, api, Runner(api, engine, bus)


def test_round_trip_produces_a_valid_submission(tmp_path):
    bus, engine, api, runner = build(tmp_path)
    sent = runner.run_round(RoundConfig(1, "case-0", ARCHIVE))

    assert len(sent) == 1
    sub = sent[0]
    assert len(sub.decisions) == 4
    for d in sub.decisions:
        check_decision(d.a, d.b, d.covered)

    payload = json.loads((tmp_path / "submission.json").read_text())
    assert [i["idx"] for i in payload["items"]] == [1, 2, 3, 4]
    assert all(i["charge_price"] < i["acceptance_limit"] for i in payload["items"])


def test_event_stream_records_the_whole_round(tmp_path):
    bus, engine, api, runner = build(tmp_path)
    runner.run_round(RoundConfig(1, "case-0", ARCHIVE))
    bus.close()

    types = [e.type for e in read_events(tmp_path / "events.jsonl")]
    for expected in ("round.scheduled", "key.received", "case.decrypted", "case.parsed",
                     "item.decided", "submission.built", "submission.sent",
                     "submission.verified", "round.closed"):
        assert expected in types, f"missing {expected}"


def test_rule_snapshot_is_recorded_for_reproducibility(tmp_path):
    bus, engine, api, runner = build(tmp_path)
    runner.run_round(RoundConfig(1, "case-0", ARCHIVE))
    bus.close()
    ev = next(e for e in read_events(tmp_path / "events.jsonl") if e.type == "round.scheduled")
    names = {r["name"] for r in ev.payload["rules"]}
    assert {"pricebook_prior", "sanity_clamp", "policy_exclusion"} <= names


def test_rules_default_to_shadow_and_do_not_touch_the_submission(tmp_path):
    """New rules must not reach a submission until someone promotes them.

    Provenance is the observable, not the numbers: the shadow run must be
    produced by the fallback, never by an unpromoted rule. (Here the numbers
    happen to agree because the fallback IS the price book -- which is the
    point of choosing an anchored fallback, not an accident.)"""
    _, _, _, shadow_runner = build(tmp_path / "a")
    shadow = shadow_runner.run_round(RoundConfig(1, "case-0", ARCHIVE))[0]
    rules_used = {e["rule"] for d in shadow.decisions for e in d.trace}
    assert rules_used == {"fallback:pricebook"}

    _, _, _, active_runner = build(tmp_path / "b", activate_all=True)
    active = active_runner.run_round(RoundConfig(1, "case-0", ARCHIVE))[0]
    active_rules = {e["rule"] for d in active.decisions for e in d.trace}
    assert "pricebook_prior" in active_rules and "sanity_clamp" in active_rules
    assert "fallback:pricebook" not in active_rules


def test_explicitly_excluded_item_is_zeroed(tmp_path):
    """Item 4 (repaint ceiling for visual uniformity) is cosmetic work the
    policy excludes. An uncovered item must submit a = b = 0."""
    _, _, _, runner = build(tmp_path, activate_all=True)
    sub = runner.run_round(RoundConfig(1, "case-0", ARCHIVE))[0]
    item4 = next(d for d in sub.decisions if d.idx == 4)
    assert (item4.a, item4.b, item4.covered) == (0.0, 0.0, False)
    assert all(d.covered for d in sub.decisions if d.idx != 4)


def test_submission_is_read_back_and_verified(tmp_path):
    bus, engine, api, runner = build(tmp_path)
    runner.run_round(RoundConfig(1, "case-0", ARCHIVE))
    bus.close()
    ev = next(e for e in read_events(tmp_path / "events.jsonl")
              if e.type == "submission.verified")
    assert ev.payload["ok"] is True
