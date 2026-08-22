"""Backtest every candidate config against every played game, in one table.

    PYTHONPATH=. .venv/bin/python tools/bench_all.py --list
    PYTHONPATH=. .venv/bin/python tools/bench_all.py --games 2-31
    PYTHONPATH=. .venv/bin/python tools/bench_all.py --games 2-48 --with llm_prior

WHY THIS EXISTS, AND WHY THE FIRST THING IT DOES IS REFUSE A FOOTGUN

`tools/backtest.py` promotes every rule it can find when given NEITHER --shadow nor
--promote. Run it that way and the replay silently activates `interval_valuation_prior`,
whose sigma is 2.863 against production's 0.780. That crushes the charge to 0.227x the
belief median and produced a 191,637 EUR phantom "regression" in our own production
config, which cost an hour to chase down and nearly got reported as real. The rule
"always pass --shadow or --promote" was already written down. It was still violated,
because it lived in a doc rather than in code.

So this tool never shells out without an explicit rule set, and it prints the exact
`--promote`/`--shadow` argument it used on every row. If you cannot see which rules were
active, the number is not usable.

WHAT IT MEASURES, AND WHICH HALF IS EXACT

Per candidate, on the SAME games, against the SAME transactions:

  reviewer cost   exact where the charge against us is visible. A fair charge is
                  visible because rejected-yet-paid reveals its amount. A REJECTED
                  FRAUDULENT charge records amount 0, so if a candidate raises `b`
                  enough to accept it we cannot price what we just bought. Those rows
                  are counted in `unpriced` and never folded into the total.
  provable income sum of 16*a over items where a <= t_lo, i.e. charges PROVEN fair
                  (t >= t_lo always, and t_lo is itself a charge someone rejected and
                  still paid). Exact, but a LOWER bound: charges above t_lo may also
                  have been fair and earn nothing here.
  median charge   the sanity column. A candidate whose median charge collapses is
                  undercharging, which is a 16x silent loss and never surfaces as an
                  error anywhere.

A candidate with a better cost AND a positive `unpriced` delta has not been shown to
win: it may simply have started buying invisible fraud. Read those two columns together
or not at all.

WHAT IT DOES NOT DO

It does not submit, does not touch the daemon, and does not promote anything. Promotion
is a human edit to rules_user/rules_state.json after reading this table.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import statistics as st
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from c2f.core import env

env.load()

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "c2f.sqlite"
BT = ROOT / "data" / "backtest"
EVENTS = ROOT / "data" / "events" / "tournament.jsonl"
OPP = 16

# Rules whose verdict comes from a model. Replaying these WITHOUT
# --allow-model-network makes backtest.py default C2F_BACKEND=none, the prior abstains,
# and the rule becomes a silent no-op that reports "no change" in 11 seconds. That is
# indistinguishable from a real null result, so it is refused rather than passed.
NEEDS_MODEL = {"llm_prior", "llm_coverage"}

# The rules that exist to be promoted. Anything not listed loads SHADOW, which is the
# safe default and the reason an unknown rule can never quietly change a submission.
KNOWN = [
    "calibration_bias", "policy_exclusion", "pricebook_prior", "sanity_clamp",
    "worthless_accept_guard", "llm_prior", "llm_coverage",
    "interval_valuation_prior", "unparsed_row_prior",
]


def read_events(path: Path, kind: str) -> dict:
    out: dict = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") == kind:
                p = e["payload"]
                out[(e["round"], p.get("idx"))] = p
    return out


def labels(con: sqlite3.Connection) -> tuple[dict, dict]:
    side: dict = {}
    amount: dict = {}
    for g, iss, it, acc, amt in con.execute(
            "select game_id,issuer,line_item,accepted,amount from transactions"):
        if acc:
            continue
        k = (g, it, iss)
        if amt > 0:
            side[k] = "fair"
            amount[k] = max(amount.get(k, 0.0), amt)
        else:
            side.setdefault(k, "fraud")
    return side, amount


def floors() -> dict:
    """Proven floors on t, from the ONLY sanctioned source."""
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "thresholds.py"), "--jsonl"],
                       capture_output=True, text=True, cwd=str(ROOT),
                       env={**os.environ, "PYTHONPATH": str(ROOT)})
    out: dict = {}
    for line in r.stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("t_lo") is not None:
            out[(d["game"], d["item"])] = d["t_lo"]
    return out


def score(dec: dict, rows: list, side: dict, amount: dict, games: set) -> tuple[float, int]:
    cost = 0.0
    unpriced = 0
    for g, iss, rev, it, acc, amt in rows:
        if rev != "Oasis" or g not in games:
            continue
        ab = dec.get((g, it))
        if ab is None:
            cost += 1.5 * amt if (not acc and amt > 0) else (amt if acc else 0.0)
            continue
        lab = side.get((g, it, iss))
        charged = amount.get((g, it, iss))
        if lab == "fair" and charged is not None:
            cost += charged if charged <= ab["b"] else 1.5 * charged
        elif lab == "fraud":
            if acc:
                cost += amt
            else:
                # We reject it today and it costs nothing. Under a higher b we might
                # buy it, at a size the server never revealed. Counted, never priced.
                unpriced += 1
        elif acc:
            cost += amt
    return cost, unpriced


def replay(label: str, games: str, promote: list[str] | None,
           allow_model: bool = False) -> Path:
    """One backtest run. NEVER invoked without an explicit rule decision."""
    cmd = [sys.executable, str(ROOT / "tools" / "backtest.py"),
           "--games", games, "--label", label]
    if promote:
        cmd += ["--promote", ",".join(promote)]
        needs = NEEDS_MODEL & set(promote)
        if needs and not allow_model:
            raise SystemExit(
                f"{sorted(needs)} need a model. Without --allow-model-network the prior "
                "abstains and this run would report a false null. Re-run with "
                "--allow-model-network (it spends money), or drop those rules.")
        if needs:
            cmd += ["--allow-model-network"]
    else:
        cmd += ["--shadow"]
    subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT),
                   env={**os.environ, "PYTHONPATH": str(ROOT)})
    for name in (f"{label}.events.jsonl", f"{label}.jsonl"):
        p = BT / name
        if p.exists():
            return p
    raise SystemExit(f"backtest produced no output for label {label}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--games", default="2-31", help="e.g. 2-31 or 2-48")
    p.add_argument("--with", dest="extra", action="append", default=[],
                   help="also try promoting this rule on top of the live set; repeatable")
    p.add_argument("--list", action="store_true", help="show known rules and the live set")
    p.add_argument("--allow-model-network", action="store_true",
                   help="required for llm_prior / llm_coverage; spends real money")
    a = p.parse_args()

    state_path = ROOT / "rules_user" / "rules_state.json"
    live = []
    if state_path.exists():
        state = json.loads(state_path.read_text())
        live = sorted(k for k, v in state.items() if v == "active")

    if a.list:
        print("known rules:")
        for r in KNOWN:
            print(f"  {r:<28}{'ACTIVE' if r in live else 'shadow'}")
        print("\nAnything absent from rules_state.json loads SHADOW. That is the safe")
        print("default: an unknown rule can never quietly change a submission.")
        return 0

    if not DB.exists():
        print("no data/c2f.sqlite -- run tools/harvest.py --once")
        return 1

    con = sqlite3.connect(DB)
    side, amount = labels(con)
    rows = con.execute("select game_id,issuer,reviewer,line_item,accepted,amount "
                       "from transactions").fetchall()
    tlo = floors()

    candidates: list[tuple[str, list[str] | None]] = [
        ("as-submitted", None),          # special-cased below: read the real event log
        ("live config", live),
    ]
    for r in a.extra:
        if r not in KNOWN:
            print(f"unknown rule {r!r}; see --list")
            return 1
        candidates.append((f"live + {r}", sorted(set(live) | {r})))

    print(f"games {a.games}\n")
    results = []
    for name, promote in candidates:
        if promote is None:
            dec = read_events(EVENTS, "item.decided")
            bel = read_events(EVENTS, "item.belief")
            arg = "(the real submissions)"
        else:
            out = replay(name.replace(" ", "_").replace("+", "plus"), a.games, promote,
                         allow_model=a.allow_model_network)
            dec = read_events(out, "item.decided")
            bel = read_events(out, "item.belief")
            arg = "--promote " + ",".join(promote) if promote else "--shadow"
        games = {g for g, _ in dec}
        results.append((name, arg, dec, bel, games))

    common = set.intersection(*[r[4] for r in results]) if results else set()
    print(f"scoring on the {len(common)} games every candidate covers\n")
    print(f"  {'candidate':<18}{'reviewer cost':>15}{'unpriced':>9}"
          f"{'provable income':>17}{'median a':>10}{'med sigma':>11}")
    base = None
    for name, arg, dec, bel, _ in results:
        cost, unp = score(dec, rows, side, amount, common)
        inc = sum(OPP * dec[k]["a"] for k in dec
                  if k[0] in common and k in tlo and dec[k]["a"] <= tlo[k])
        A = [dec[k]["a"] for k in dec if k[0] in common]
        S = [bel[k]["sigma"] for k in dec if k in bel
             and bel[k].get("sigma") is not None and k[0] in common]
        line = (f"  {name:<18}{cost:>15,.0f}{unp:>9}{inc:>17,.0f}"
                f"{(st.median(A) if A else 0):>10.2f}"
                f"{(st.median(S) if S else float('nan')):>11.3f}")
        print(line)
        if base is None:
            base = (cost, unp, inc)
        elif (round(cost, 2), unp, round(inc, 2)) == (round(base[0], 2), base[1],
                                                      round(base[2], 2)):
            print(f"  {'':<18}^^ IDENTICAL to the first row. Either the rule never "
                  "fired, or it was a no-op.")
    print()
    for name, arg, dec, bel, _ in results:
        print(f"  {name:<18} {arg}")
    print()
    print("  A better cost WITH a higher 'unpriced' is not a win -- it may just be")
    print("  buying invisible fraud. Read those two columns together.")
    print("  'provable income' is a LOWER bound: only charges proven fair are counted.")
    return 0


def demo() -> None:
    """Self-check: the scorer must price the payoff matrix correctly."""
    side = {(1, 1, "X"): "fair", (1, 2, "X"): "fraud"}
    amount = {(1, 1, "X"): 100.0}
    rows = [(1, "X", "Oasis", 1, 0, 100.0), (1, "X", "Oasis", 2, 0, 0.0)]
    # b above the fair charge -> we accept it and pay a, not 1.5a
    c, u = score({(1, 1): {"a": 50.0, "b": 150.0}, (1, 2): {"a": 50.0, "b": 150.0}},
                 rows, side, amount, {1})
    assert abs(c - 100.0) < 1e-9, c
    assert u == 1, u          # the rejected fraud row stays unpriced, never free
    # b below it -> we reject a fair charge and pay the 1.5x penalty
    c2, _ = score({(1, 1): {"a": 50.0, "b": 10.0}, (1, 2): {"a": 50.0, "b": 10.0}},
                  rows, side, amount, {1})
    assert abs(c2 - 150.0) < 1e-9, c2
    assert c2 > c, "rejecting a fair charge must cost more than accepting it"
    print("demo ok")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo()
    else:
        raise SystemExit(main())
