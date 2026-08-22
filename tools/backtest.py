"""Replay finished games offline. Structurally incapable of submitting.

    PYTHONPATH=. .venv/bin/python tools/backtest.py --fetch-keys   # once per new game
    PYTHONPATH=. .venv/bin/python tools/backtest.py                # replay everything
    PYTHONPATH=. .venv/bin/python tools/backtest.py --diff last    # what my rule changed

WHY THIS CANNOT SUBMIT, AND HOW YOU CAN CHECK IT IN TEN SECONDS

The Runner takes an ApiClient. Here it is handed a `MockApi`, which has no HTTP
client and no PUT. There is no flag that turns this into a live run, because the
live client is never constructed. `--dry-run` is a promise a caller can forget;
this is a missing code path.

The one thing that does touch the network is `KeyVault`, and it can only issue
`GET /api/games/{id}/key`. It is a separate object with no `submit` method at
all, so even a mistaken hand-off cannot reach the tournament. Keys are cached on
disk and fetched once ever, so re-running a backtest a hundred times costs the
organisers nothing.

This matters right now because the primary runner is on someone else's machine.
Two writers is not redundancy: later submissions overwrite earlier ones, so a
second submitter silently destroys the primary's better answer.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from c2f.core.events import EventBus
from c2f.estimate.pricebook import fallback
from c2f.rules.engine import RuleEngine
from c2f.rules.loader import load_rules
from c2f.rules.protocol import RuleState
from c2f.runner import RoundConfig, Runner
from c2f.scheduler import find_archive
from c2f.submit.client import MockApi
from tools.serve import default_cases_dir

ROOT = Path(__file__).resolve().parent.parent
KEYS = ROOT / "data" / "keys.json"          # under data/, which is gitignored
OUT = ROOT / "data" / "backtest"


class KeyVault:
    """Read-only key fetcher plus an on-disk cache.

    Deliberately NOT an ApiClient: no `submit`, no `get_submission`. The only
    request it can make is a GET for a decryption key, and only for a game that
    has already started -- the API 403s otherwise, which is the organisers'
    rule, not ours to work around.
    """

    def __init__(self, path: Path = KEYS) -> None:
        self.path = path
        self.cache: dict[str, str] = {}
        if path.is_file():
            try:
                self.cache = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.cache = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.cache, indent=2, sort_keys=True), encoding="utf-8")

    def fetch(self, game_ids: list[int], pause: float = 0.4) -> tuple[int, list[str]]:
        """One GET per game we do not already hold. Never re-fetches."""
        import requests
        from c2f.submit.client import LiveApi

        key = LiveApi().team_key
        if not key:
            raise RuntimeError("TEAM_API_KEY not set -- put it in .env (never commit it)")
        got, problems = 0, []
        for gid in game_ids:
            if str(gid) in self.cache:
                continue
            url = f"{LiveApi.BASE}{LiveApi.PATH_KEY.format(game_id=gid)}"
            try:
                r = requests.get(url, headers={"X-API-Key": key}, timeout=(2.0, 5.0))
            except Exception as e:  # noqa: BLE001
                problems.append(f"game {gid}: {type(e).__name__}: {e}")
                continue
            if r.status_code == 403:
                problems.append(f"game {gid}: not started yet")
                continue
            if not r.ok:
                problems.append(f"game {gid}: HTTP {r.status_code}")
                continue
            k = (r.json() or {}).get("decryption_key")
            if not k:
                problems.append(f"game {gid}: no decryption_key in response")
                continue
            self.cache[str(gid)] = k
            got += 1
            time.sleep(pause)          # a polite trickle, never a burst
        if got:
            self._save()
        return got, problems

    def have(self) -> list[int]:
        return sorted(int(k) for k in self.cache)


@dataclass
class Replay:
    game_id: int
    items: list[dict[str, Any]]
    charge: float
    limit: float
    error: str | None = None


def replay(game_id: int, key: str, cases_dir: Path, engine: RuleEngine,
           bus: EventBus) -> Replay:
    archive = find_archive(cases_dir, game_id)
    if archive is None:
        return Replay(game_id, [], 0.0, 0.0, f"no archive for game {game_id}")

    # MockApi: holds the key, records the "submission" in memory, has no HTTP.
    api = MockApi(keys={str(game_id): key})
    try:
        subs = Runner(api, engine, bus).run_round(
            RoundConfig(round_no=game_id, case_id=str(game_id), archive=archive))
    except Exception as e:  # noqa: BLE001 -- one bad case must not end the sweep
        return Replay(game_id, [], 0.0, 0.0, f"{type(e).__name__}: {e}")

    last = subs[-1]
    items = [{
        "idx": d.idx, "a": round(d.a, 2), "b": round(d.b, 2), "covered": d.covered,
        "median": round(d.belief.median, 2) if d.belief else None,
        "sigma": round(d.belief.sigma, 3) if d.belief else None,
        "rules": [e.get("rule") for e in d.trace],
    } for d in last.decisions]
    return Replay(game_id, items,
                  round(sum(d.a for d in last.decisions), 2),
                  round(sum(d.b for d in last.decisions), 2))


def load_run(path: Path) -> dict[int, Replay]:
    out: dict[int, Replay] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        out[d["game_id"]] = Replay(d["game_id"], d["items"], d["charge"], d["limit"], d.get("error"))
    return out


def main() -> int:
    p = argparse.ArgumentParser(prog="backtest")
    p.add_argument("--fetch-keys", action="store_true",
                   help="GET the decryption key for every started game we do not hold yet")
    p.add_argument("--games", default=None,
                   help="e.g. 1-20 or 3,7,11. Default: every game we hold a key for")
    p.add_argument("--cases-dir", type=Path, default=None)
    p.add_argument("--label", default="run", help="name this run, for diffing later")
    p.add_argument("--diff", default=None, metavar="LABEL",
                   help="compare this run against an earlier one, in euros")
    p.add_argument("--shadow", action="store_true", help="leave rules SHADOW")
    a = p.parse_args()

    cases_dir = a.cases_dir or default_cases_dir()
    vault = KeyVault()

    if a.fetch_keys:
        from c2f.leaderboard import Leaderboard
        lb = Leaderboard()
        now = lb.server_now()
        started = [g.id for g in lb.games() if g.start_time <= now]
        print(f"started games: {len(started)} · keys held: {len(vault.have())}")
        got, problems = vault.fetch(started)
        print(f"fetched {got} new key(s)")
        for pr in problems[:8]:
            print(f"  {pr}")
        if len(problems) > 8:
            print(f"  ... and {len(problems) - 8} more")

    if a.games:
        wanted: list[int] = []
        for part in a.games.split(","):
            if "-" in part:
                lo, hi = part.split("-")
                wanted += list(range(int(lo), int(hi) + 1))
            else:
                wanted.append(int(part))
        games = [g for g in wanted if str(g) in vault.cache]
        missing = [g for g in wanted if str(g) not in vault.cache]
        if missing:
            print(f"no key for {missing} -- run --fetch-keys once they have started")
    else:
        games = vault.have()

    if not games:
        print("nothing to replay. Fetch keys first:  tools/backtest.py --fetch-keys")
        return 1

    engine = RuleEngine(fallback)
    report = load_rules(engine, ROOT / "rules_user")
    if report.rejected:
        print(f"REJECTED rules: {report.rejected}")
    if not a.shadow:
        for r in engine.rules:
            engine.set_state(r.name, RuleState.ACTIVE)
    print(f"rules  : {', '.join(report.loaded) or '(none)'} "
          f"[{'SHADOW' if a.shadow else 'ACTIVE'}]")
    print(f"replay : {len(games)} game(s), MockApi -- no submit path exists\n")

    OUT.mkdir(parents=True, exist_ok=True)
    bus = EventBus(OUT / f"{a.label}.events.jsonl")
    results: list[Replay] = []
    for gid in games:
        r = replay(gid, vault.cache[str(gid)], cases_dir, engine, bus)
        results.append(r)
        if r.error:
            print(f"  game {gid:>3}  FAILED  {r.error}")
        else:
            print(f"  game {gid:>3}  {len(r.items):>2} items  "
                  f"charge {r.charge:>10,.2f}  limit {r.limit:>10,.2f}")
    bus.close()

    out = OUT / f"{a.label}.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps({"game_id": r.game_id, "items": r.items,
                                 "charge": r.charge, "limit": r.limit,
                                 "error": r.error}) + "\n")

    ok = [r for r in results if not r.error]
    failed = [r for r in results if r.error]
    print(f"\n{len(ok)} replayed, {len(failed)} failed")
    if ok:
        n = sum(len(r.items) for r in ok)
        zero = sum(1 for r in ok for i in r.items if i["a"] == 0 and i["b"] == 0)
        print(f"line items : {n}, of which {zero} priced at 0/0 "
              f"({zero / n * 100:.1f}%)")
        print(f"charge     : total {sum(r.charge for r in ok):,.2f} · "
              f"median/game {statistics.median([r.charge for r in ok]):,.2f}")
    if failed:
        # A parse failure here is a round we would have lost. Game 1 cost -8273.70
        # exactly this way, so a failure in the sweep is the headline, not a footnote.
        print(f"\nFAILURES -- each of these would have been a lost round:")
        for r in failed:
            print(f"  game {r.game_id}: {r.error}")
    print(f"\nwrote {out}")

    if a.diff:
        prev = load_run(OUT / f"{a.diff}.jsonl")
        if not prev:
            print(f"no earlier run named '{a.diff}'")
            return 0
        print(f"\ndiff vs '{a.diff}' -- in euros, per game:")
        moved = 0
        for r in ok:
            old = prev.get(r.game_id)
            if not old or old.error:
                continue
            d_charge, d_limit = r.charge - old.charge, r.limit - old.limit
            if abs(d_charge) < 0.01 and abs(d_limit) < 0.01:
                continue
            moved += 1
            print(f"  game {r.game_id:>3}  charge {d_charge:>+10,.2f}  limit {d_limit:>+10,.2f}")
        if not moved:
            print("  nothing moved")
        else:
            tot = sum(r.charge for r in ok) - sum(
                p.charge for p in prev.values() if not p.error and p.game_id in {x.game_id for x in ok})
            print(f"  {moved} game(s) changed · total charge {tot:>+,.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
