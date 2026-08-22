"""Replay finished games offline. Structurally incapable of submitting.

    PYTHONPATH=. .venv/bin/python tools/backtest.py --add-keys keys.txt  # paste them in
    PYTHONPATH=. .venv/bin/python tools/backtest.py --verify             # do they open?
    PYTHONPATH=. .venv/bin/python tools/backtest.py                      # replay everything
    PYTHONPATH=. .venv/bin/python tools/backtest.py --diff last          # what my rule changed

Keys arrive by hand, one per finished case, and go into `data/keys.json`. Fetching
them over the API (`--fetch-keys`) needs a TEAM_API_KEY we do not have on this
machine; it is kept for the machine that does. Nothing else here needs the network.

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
import re
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

    # -- keys that arrive by hand ----------------------------------------
    # Whitespace counts as a separator: "case_03  abc123" is what a chat paste
    # actually looks like. That makes the pattern greedy enough to match prose
    # like "game 3 started", which is fine -- verify() opens the archive before
    # anything is stored, so a false positive is rejected, not believed.
    _PAIR = re.compile(
        r"(?:case[_\-\s]*)?(\d{1,3})[\s:=,]+[\"']?([^\s\"',;]{4,})[\"']?",
        re.I)

    def add_text(self, text: str) -> tuple[dict[int, str], list[str]]:
        """Parse pasted keys. Forgiving on format, strict on the result.

        Accepts JSON, or one pair per line in any of `1: abc`, `1=abc`,
        `case_01 abc`, `1,abc`. Whatever a human pastes out of a chat window
        should work; what must not happen is a silently mis-parsed line that
        backtests the wrong case with a key that happens to be valid.
        """
        found: dict[int, str] = {}
        problems: list[str] = []

        stripped = text.strip()
        if stripped.startswith("{"):
            try:
                for k, v in json.loads(stripped).items():
                    found[int(k)] = str(v)
                return found, problems
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                problems.append(f"looked like JSON but is not: {e}")

        for lineno, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            m = self._PAIR.search(line)
            if not m:
                problems.append(f"line {lineno}: no game:key pair in {line[:60]!r}")
                continue
            gid, key = int(m.group(1)), m.group(2)
            if gid in found and found[gid] != key:
                problems.append(f"line {lineno}: game {gid} given twice with different keys")
                continue
            found[gid] = key
        return found, problems

    def store(self, pairs: dict[int, str]) -> None:
        for gid, key in pairs.items():
            self.cache[str(gid)] = key
        self._save()

    def verify(self, cases_dir: Path, game_ids: list[int] | None = None) -> list[tuple[int, str]]:
        """Actually open each archive with its key. Returns (game_id, problem).

        Worth the seconds it costs: a key that decrypts nothing and a key paired
        with the wrong case both look identical in a JSON file, and the second
        one produces a backtest that is confidently about the wrong invoice.
        """
        import tempfile

        from c2f.ingest import decrypt

        out: list[tuple[int, str]] = []
        for gid in (game_ids if game_ids is not None else self.have()):
            key = self.cache.get(str(gid))
            if not key:
                out.append((gid, "no key held"))
                continue
            archive = find_archive(cases_dir, gid)
            if archive is None:
                out.append((gid, f"no archive for game {gid}"))
                continue
            with tempfile.TemporaryDirectory(prefix="c2f-verify-") as tmp:
                try:
                    files = decrypt.extract(archive, key, Path(tmp))
                except Exception as e:  # noqa: BLE001
                    out.append((gid, f"{archive.name}: {type(e).__name__}: {str(e)[:120]}"))
                    continue
                if not files:
                    out.append((gid, f"{archive.name}: opened but empty"))
        return out


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
    p.add_argument("--add-keys", metavar="FILE",
                   help="import decryption keys from a file, or '-' for stdin. "
                        "One 'game: key' per line, or JSON. Verified before they are kept.")
    p.add_argument("--verify", action="store_true",
                   help="open every archive we hold a key for, and say which ones fail")
    p.add_argument("--fetch-keys", action="store_true",
                   help="GET keys from the API instead. Needs TEAM_API_KEY, which this "
                        "machine does not have.")
    p.add_argument("--games", default=None,
                   help="e.g. 1-20 or 3,7,11. Default: every game we hold a key for")
    p.add_argument("--cases-dir", type=Path, default=None)
    p.add_argument("--label", default="run", help="name this run, for diffing later")
    p.add_argument("--diff", default=None, metavar="LABEL",
                   help="compare this run against an earlier one, in euros")
    p.add_argument("--shadow", action="store_true", help="leave rules SHADOW")
    p.add_argument("--promote", default=None, metavar="a,b,c",
                   help="promote ONLY these rules; everything else stays SHADOW. "
                        "Use this to price one rule without a higher-priority rule masking it.")
    a = p.parse_args()

    cases_dir = a.cases_dir or default_cases_dir()
    vault = KeyVault()

    if a.add_keys:
        text = sys.stdin.read() if a.add_keys == "-" else Path(a.add_keys).read_text(encoding="utf-8")
        pairs, problems = vault.add_text(text)
        for pr in problems:
            print(f"  ignored: {pr}")
        if not pairs:
            print("no game:key pairs found")
            return 1
        print(f"parsed {len(pairs)} key(s): games {sorted(pairs)}")

        # Verify BEFORE storing. A key that does not open its archive is worse
        # than a missing one: it turns a loud failure into a quiet wrong answer.
        probe = KeyVault(Path("/dev/null"))
        probe.cache = {str(g): k for g, k in pairs.items()}
        bad = probe.verify(cases_dir, sorted(pairs))
        good = {g: k for g, k in pairs.items() if g not in {b[0] for b in bad}}
        for gid, why in bad:
            print(f"  REJECTED game {gid}: {why}")
        if good:
            vault.store(good)
            print(f"stored {len(good)} verified key(s) -> {vault.path}")
        if bad:
            print(f"{len(bad)} key(s) did not open their archive and were NOT stored")

    if a.verify:
        bad = vault.verify(cases_dir)
        held = vault.have()
        if bad:
            print(f"{len(bad)} of {len(held)} held key(s) FAILED:")
            for gid, why in bad:
                print(f"  game {gid}: {why}")
        else:
            print(f"all {len(held)} held key(s) open their archive")
        if not a.games and not a.add_keys:
            return 1 if bad else 0

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
    if a.promote:
        # Measure ONE rule in isolation. Force-promoting everything (the default) lets a
        # high-priority rule mask the change you are trying to price: the interval model
        # sits at PRIOR 20 and outranks pricebook_prior at 10, so a price-book edit
        # measured without this looks inert.
        wanted = {n.strip() for n in a.promote.split(",") if n.strip()}
        unknown = wanted - {r.name for r in engine.rules}
        if unknown:
            print(f"--promote names no such rule: {sorted(unknown)}")
            return 1
        for r in engine.rules:
            engine.set_state(r.name, RuleState.ACTIVE if r.name in wanted else RuleState.SHADOW)
        mode = f"PROMOTED {sorted(wanted)}"
    elif not a.shadow:
        for r in engine.rules:
            engine.set_state(r.name, RuleState.ACTIVE)
        mode = "ACTIVE"
    else:
        mode = "SHADOW"
    print(f"rules  : {', '.join(report.loaded) or '(none)'} [{mode}]")
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
