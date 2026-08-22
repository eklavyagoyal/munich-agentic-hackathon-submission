"""Publish per-game JSON to the side branches, so nobody has to pull or re-query.

    PYTHONPATH=. .venv/bin/python tools/publish.py --game 6
    PYTHONPATH=. .venv/bin/python tools/publish.py --catch-up      # every game we can
    PYTHONPATH=. .venv/bin/python tools/publish.py --game 6 --dry-run

Two branches, neither ever merged into main:

    inputs/game-NNN.json    what WE submitted, and why -- the full derivation of
                            every a and b, rule by rule
    results/game-NNN.json   what the tournament did with it -- scores and every
                            transaction, in the schema tools/export.py established

WHY THE DERIVATION AND NOT JUST THE NUMBERS

A bare pair of numbers cannot be argued with. Anyone reading `a = 199.25` needs to
know it came from a per-piece band the price book inferred for an item it did not
recognise, at sigma 0.91, and that b is the 1/3-quantile of that same belief -- and
therefore that the whole pair is only as good as one guess about the unit. So each
item carries its belief, its source, and the ordered list of rules that touched it,
including the ones that ran in SHADOW and changed nothing. That is the context
someone needs to disagree with us usefully.

NO CLAIM DATA. Line item descriptions are the organisers' invoice content, and
checked-in claim data is a ranking penalty (Discord, Hailong@QuantCo, 14:35). This
publishes idx, qty and unit -- never the description. Decrypted files stay under
gitignored data/. The keys branch is the sensitive one and this tool does not
touch it.

HOW IT WRITES WITHOUT DISTURBING ANYTHING

Git plumbing against a temporary index: hash-object, update-index, write-tree,
commit-tree, then push the commit straight at the remote ref. The working tree,
the current branch and main are never touched, so this is safe to run while the
daemon is mid-tournament.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
EVENTS = ROOT / "data" / "events" / "tournament.jsonl"
DB = ROOT / "data" / "c2f.sqlite"

TX_COLUMNS = ["issuer", "reviewer", "line_item", "accepted", "amount"]

# Written into every inputs file. The formulas are the contract between the belief
# and the submission; without them the numbers are unfalsifiable.
DERIVATION_NOTE = {
    "belief": "t is modelled as LogNormal(log(median), sigma) per line item.",
    "charge_a": (
        "a maximises expected revenue a*P(a<=t). A fair charge (a<=t) is paid by "
        "EVERY opponent whether they accept or reject, so revenue is 16a; above t "
        "only the opponents whose limit clears a pay anything. The optimum solves "
        "the Mills ratio phi(z)/(1-Phi(z))=sigma, giving a=median*exp(z*sigma), "
        "capped so P(a<=t)>=0.70 rather than betting on the tail."
    ),
    "limit_b": (
        "b is the 1/3-quantile of the same belief. Accepting costs a when the "
        "charge is fair and min(a,c) when it is fraud; rejecting costs 1.5a when "
        "fair and 0 when fraud. Accept is better iff P(fair)>2/3, so the limit "
        "belongs at the 1/3-quantile."
    ),
    "t_is_never_observed": (
        "We never see t. It is bracketed after the fact from transactions: a "
        "rejected charge that was still PAID proves a<=t; rejected and unpaid "
        "proves a>t. See tools/thresholds.py and docs/MODEL_BRIEF.md 5a."
    ),
    "uncovered": "An item the policy does not cover has t=0, and a=b=0 is correct for it.",
}


def git(args: list[str], *, stdin: str | None = None, env: dict | None = None,
        check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, input=stdin, capture_output=True,
                       text=True, env=env)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()[:300]}")
    return r.stdout.strip()


def rev(ref: str) -> str | None:
    r = subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=ROOT,
                       capture_output=True, text=True)
    return r.stdout.strip() or None


# -- inputs: what we submitted, and the reasoning behind it -------------------

def read_round(game: int) -> dict | None:
    """Reconstruct one round from the event log. Descriptions are never read."""
    beliefs: dict[int, dict] = {}
    decided: dict[int, dict] = {}
    meta: dict = {}
    parsed: dict[int, dict] = {}
    if not EVENTS.exists():
        return None
    with EVENTS.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("round") != game:
                continue
            p, t = e.get("payload", {}), e["type"]
            if t == "item.belief":
                beliefs[p["idx"]] = p
            elif t == "item.decided":
                decided[p["idx"]] = p
            elif t == "case.parsed":
                for it in p.get("items", []):
                    parsed[it["idx"]] = {"qty": it.get("qty"), "unit": it.get("unit")}
            elif t == "submission.built":
                meta["tier"] = p.get("tier")
                meta["total_a"] = p.get("total_a")
                meta["total_b"] = p.get("total_b")
            elif t == "submission.sent":
                meta["submitted"] = bool(p.get("ok"))
                meta["http_status"] = p.get("status")
                meta["submit_ms"] = p.get("ms")
            elif t == "submission.verified":
                meta["server_echo_matched"] = p.get("ok")
            elif t == "round.closed":
                meta["elapsed_s"] = p.get("elapsed_s")
            elif t == "round.scheduled":
                meta["rules_snapshot"] = p.get("rules")
    if not decided:
        return None

    items = []
    for idx in sorted(decided):
        d, b = decided[idx], beliefs.get(idx, {})
        items.append({
            "idx": idx,
            "qty": parsed.get(idx, {}).get("qty"),
            "unit": parsed.get(idx, {}).get("unit"),
            "a": d.get("a"),
            "b": d.get("b"),
            "covered": d.get("covered"),
            "belief": {"median": b.get("median"), "sigma": b.get("sigma"),
                       "source": b.get("source")},
            # The ordered chain that produced this pair, stage by stage, including
            # clamps and their reasons. This is the "why" for this line item.
            "trace": d.get("trace", []),
        })
    return {"game": game, **meta, "n_items": len(items),
            "how_a_and_b_are_derived": DERIVATION_NOTE, "items": items}


# -- results: what the tournament did, from the local harvest -----------------

def read_results(game: int) -> dict | None:
    if not DB.exists():
        return None
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    g = con.execute("select id,start_time,status from games where id=?", (game,)).fetchone()
    tx = con.execute(
        "select issuer,reviewer,line_item,accepted,amount from transactions "
        "where game_id=? order by issuer,reviewer,line_item", (game,)).fetchall()
    if not tx:
        return None
    scores = {r["team"]: r["score"]
              for r in con.execute("select team,score from scores where game_id=?", (game,))}
    return {
        "game": game,
        "start_time": g["start_time"] if g else None,
        "status": g["status"] if g else None,
        "note": ("amount is what the ISSUER was paid, not what they charged. "
                 "See docs/MODEL_BRIEF.md 5a before drawing conclusions about t."),
        "scores": scores,
        "columns": TX_COLUMNS,
        "transactions": [[r["issuer"], r["reviewer"], r["line_item"],
                          bool(r["accepted"]), r["amount"]] for r in tx],
    }


# -- pushing, without touching the working tree ------------------------------

def publish(branch: str, path: str, content: str, message: str, dry_run: bool) -> str:
    if dry_run:
        return f"  would push {path} ({len(content)} bytes) to {branch}"
    git(["fetch", "-q", "origin", branch], check=False)
    parent = rev(f"origin/{branch}")
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
        if parent:
            git(["read-tree", parent], env=env)
        blob = git(["hash-object", "-w", "--stdin"], stdin=content)
        git(["update-index", "--add", "--cacheinfo", f"100644,{blob},{path}"], env=env)
        tree = git(["write-tree"], env=env)
    args = ["commit-tree", tree, "-m", message]
    if parent:
        args += ["-p", parent]
    commit = git(args)
    git(["push", "-q", "origin", f"{commit}:refs/heads/{branch}"])
    return f"  pushed {path} -> {branch} ({commit[:9]})"


def games_with_events() -> list[int]:
    seen = set()
    if EVENTS.exists():
        with EVENTS.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("type") == "submission.built" and e.get("round"):
                    seen.add(e["round"])
    return sorted(seen)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--game", type=int, default=None)
    p.add_argument("--catch-up", action="store_true", help="every game we have data for")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-inputs", action="store_true")
    p.add_argument("--skip-results", action="store_true")
    a = p.parse_args()

    if a.game is None and not a.catch_up:
        p.error("pass --game N or --catch-up")
    games = [a.game] if a.game is not None else games_with_events()
    if not games:
        print("no rounds in the event log yet")
        return 0

    for game in games:
        print(f"game {game}:")
        if not a.skip_inputs:
            payload = read_round(game)
            if payload is None:
                print("  inputs : no round in the event log (did this daemon play it?)")
            else:
                print(publish("inputs", f"inputs/game-{game:03d}.json",
                              json.dumps(payload, indent=1, sort_keys=True) + "\n",
                              f"inputs: game {game} submission and derivation", a.dry_run))
        if not a.skip_results:
            res = read_results(game)
            if res is None:
                print("  results: nothing harvested yet -- run tools/harvest.py --once")
            else:
                print(publish("results", f"results/game-{game:03d}.json",
                              json.dumps(res, indent=1, sort_keys=True) + "\n",
                              f"results: game {game} scores and transactions", a.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
