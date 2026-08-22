"""Does an item's description relate to the claim's damage text -- and does that predict t?

    PYTHONPATH=. .venv/bin/python tools/measure_description_match.py

WHY THIS EXISTS, AND WHY IT IS A MEASUREMENT AND NOT A RULE

Stage 4 of the pipeline sketch: "check what matches the description". It is the only
unbuilt stage with usable ground truth, and it matters because the binding constraint
on the most valuable mechanism we have is DETECTOR PRECISION, not wiring.

rules_user/worthless_accept_guard.py already keeps the charge and zeroes the
acceptance limit; the oracle for that is +14,575.16 exact. Built on LLM zero-votes it
measured -75.00, because the detector fires on the wrong items. So a second,
independent, deterministic detector for the same mechanism is worth more than another
valuation model.

The hypothesis, stated so it can fail: an invoice line whose description is unrelated
to the claim's damage description is padding, and padding has low t.

This script does NOT ship a rule. It asks whether the signal exists, the way
c2f/estimate/fuzzy.py asked and got told no. Nothing here touches a round: no network,
no model, no submission -- keys come from the local cache.

GROUND TRUTH, the same split tools/validate_masks.py gates on:
  worthless : t_lo == 0 AND bounded, proven ceiling below 176
  valuable  : t_lo >= 200, proven floor
Items proven neither way are skipped; counting them would flatter the detector free.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from c2f.core import env

env.load()

from c2f.estimate.fuzzy import _cosine, _grams  # noqa: E402
from c2f.ingest import decrypt, parse  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "c2f.sqlite"
KEYS = ROOT / "data" / "keys.json"
CASES = ROOT / "public-cases-ehl" / "cases"

WORTHLESS_CEILING = 176.0
VALUABLE_FLOOR = 200.0
_FOLD = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
                       "Ä": "ae", "Ö": "oe", "Ü": "ue"})


def fold(t: str) -> str:
    t = t.translate(_FOLD).lower()
    return "".join(c if c.isalnum() else " " for c in t)


def containment(item_desc: str, damage: str) -> float | None:
    """Fraction of the item's content words that appear in the damage text.

    Substring rather than token equality, because German compounds carry the signal:
    "Wasserschadenbeseitigung" should count as a hit when the damage text says
    "Wasser". Tokens under four characters are dropped -- they are articles and
    prepositions, and they match everything.
    """
    hay = fold(damage)
    toks = [w for w in fold(item_desc).split() if len(w) >= 4]
    if not toks:
        return None
    return sum(1 for w in toks if w in hay) / len(toks)


def classes(con: sqlite3.Connection) -> tuple[dict, dict]:
    """Same derivation as tools/validate_masks.py -- proven ceilings and floors."""
    side: dict[tuple, str] = {}
    lo: dict[tuple, float] = {}
    hi: dict[tuple, float] = {}
    rows = con.execute("select game_id,issuer,line_item,accepted,amount "
                       "from transactions").fetchall()
    for g, iss, it, acc, amt in rows:
        if acc:
            continue
        k = (g, it, iss)
        if amt > 0:
            side[k] = "fair"
            lo[(g, it)] = max(lo.get((g, it), 0.0), amt)
        else:
            side.setdefault(k, "fraud")
    for g, iss, it, acc, amt in rows:
        if acc and amt > 0 and side.get((g, it, iss)) == "fraud":
            hi[(g, it)] = min(hi.get((g, it), float("inf")), amt)
    worthless = {k: v for k, v in hi.items()
                 if v <= WORTHLESS_CEILING and lo.get(k, 0.0) == 0.0}
    valuable = {k: v for k, v in lo.items() if v >= VALUABLE_FLOOR}
    return worthless, valuable


def main() -> int:
    if not DB.exists():
        print("no data/c2f.sqlite -- run tools/harvest.py --once")
        return 1
    if not KEYS.is_file():
        print("no data/keys.json -- nothing to decrypt from")
        return 1
    keys = {int(k): v for k, v in json.loads(KEYS.read_text()).items()}
    con = sqlite3.connect(DB)
    worthless, valuable = classes(con)
    games = sorted({g for g, _ in list(worthless) + list(valuable)})
    print(f"ground truth: {len(worthless)} proven-worthless, {len(valuable)} "
          f"proven-valuable, over {len(games)} games\n")

    rows = []
    for g in games:
        arch = CASES / f"case_{g:02d}.zip"
        if not arch.exists() or g not in keys:
            continue
        try:
            with tempfile.TemporaryDirectory() as tmp:
                files = decrypt.extract(arch, keys[g], Path(tmp))
                case = parse.build_case(str(g), files)
        except Exception as e:                                    # noqa: BLE001
            print(f"  game {g}: {type(e).__name__}")
            continue
        for it in case.items:
            k = (g, it.idx)
            truth = ("worthless" if k in worthless
                     else "valuable" if k in valuable else None)
            if truth is None:
                continue
            c = containment(it.description, case.damage_description)
            cos = _cosine(_grams(it.description), _grams(case.damage_description))
            rows.append((truth, c, cos))

    if not rows:
        print("no labelled items resolved -- cannot measure")
        return 1

    for name, i in (("containment", 1), ("trigram cosine", 2)):
        print(f"=== {name} ===")
        for truth in ("worthless", "valuable"):
            v = sorted(r[i] for r in rows if r[0] == truth and r[i] is not None)
            if not v:
                continue
            med = v[len(v) // 2]
            print(f"  {truth:>10}  n={len(v):<4} min={v[0]:.2f} "
                  f"med={med:.2f} max={v[-1]:.2f} mean={sum(v)/len(v):.3f}")
        # A detector says "worthless" BELOW a threshold: unrelated text means padding.
        print(f"  {'thresh':>7} {'flagged':>8} {'precision':>10} {'recall':>8}")
        nw = sum(1 for r in rows if r[0] == "worthless")
        for th in (0.0, 0.05, 0.10, 0.20, 0.34, 0.50):
            tp = sum(1 for r in rows if r[i] is not None and r[i] <= th
                     and r[0] == "worthless")
            fp = sum(1 for r in rows if r[i] is not None and r[i] <= th
                     and r[0] == "valuable")
            if tp + fp == 0:
                print(f"  {th:>7.2f} {0:>8} {'never fires':>10}")
                continue
            print(f"  {th:>7.2f} {tp+fp:>8} {tp/(tp+fp):>10.2f} "
                  f"{(tp/nw if nw else 0):>8.2f}")
        print()
    print("  gate is precision >= 0.90 (docs/CLAIM_PIPELINE_PLAN.md 4.1).")
    print("  Cost is concentrated -- one false positive on a valuable item makes us")
    print("  reject its fair charges and pay 1.5a on each.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
