#!/usr/bin/env python3
"""Build `data/anchors.jsonl` -- one proven price floor per line, per (game, item).

    PYTHONPATH=. .venv/bin/python tools/build_anchors.py            # write the store
    PYTHONPATH=. .venv/bin/python tools/build_anchors.py --dry-run  # counts only
    PYTHONPATH=. .venv/bin/python tools/build_anchors.py --demo     # self-check

WHY A SEPARATE TOOL

The store is rebuilt HERE and never by the ensemble, so a mid-round rebuild cannot
introduce game N into game N's own pool. Call this from the harvest loop, not from the
round path. It is cheap either way -- the labels take about 0.1s and re-parsing every
case PDF about 0.8s -- but "cheap" is not the reason: the reason is that the thing
which decides what a round may see must not be the thing a round runs.

LABELS COME FROM `tools/thresholds.py --jsonl` AND NOWHERE ELSE. This file contains no
SQL. Hand-rolled SQL against `transactions` has produced a confidently INVERTED answer
twice, and an inverted floor is worse than no floor: it argues a price DOWN.

WHAT A ROW IS

  {"game", "item", "desc", "qty", "unit", "unit_class", "t_lo", "u_lo", "n_fair"}

`t_lo` is the proven floor exactly as thresholds.py reports it: a GROSS LINE TOTAL that
some reviewer rejected and paid anyway, so the true fair value of that line was at
least that much. `u_lo` is `c2f.estimate.anchors.net_unit_floor(t_lo, item)` -- the
same NET-per-unit quantity the valuation prompt asks the model to produce -- and that
function is the only place the division happens.

Only rows with `n_fair > 0 and t_lo > 0` are kept. A `t_lo` of 0 with no fair charge
ever seen is the ABSENCE of a floor, not a proven price of zero, and writing it as an
anchor would tell the model that a line is worth nothing when nobody proved anything.

PRIVACY. Every row carries an invoice line description, so this file is claim data.
It is written under `data/`, which `.gitignore` denies wholesale. Do not move it, do
not print descriptions to stdout (this tool prints counts only), and do not commit it.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from c2f.core.models import LineItem                       # noqa: E402
from c2f.estimate import anchors, pricebook                # noqa: E402
from c2f.ingest.parse import parse_line_items, read_files  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
THRESHOLDS = ROOT / "tools" / "thresholds.py"
CASES = ROOT / "data" / "cases"
STORE = ROOT / "data" / "anchors.jsonl"
LABEL_TIMEOUT_S = 180.0

# `case-08` and `case_8` both appear in the wild; the archive globs in
# c2f/scheduler.py tolerate the same spread. A directory whose trailing number is the
# GAME id is the only thing this needs.
CASE_GLOBS = ("case-*", "case_*")


class BuildError(RuntimeError):
    """Loud. A store that is silently short is a feature that silently stops paying."""


# ----------------------------------------------------------------------- the sources

def load_labels(games: set[int] | None = None) -> list[dict]:
    """`tools/thresholds.py --jsonl`, parsed. The ONLY label source."""
    if not THRESHOLDS.exists():
        raise BuildError(f"missing {THRESHOLDS}")
    proc = subprocess.run(
        [sys.executable, str(THRESHOLDS), "--jsonl"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=LABEL_TIMEOUT_S,
    )
    if proc.returncode != 0:
        raise BuildError(f"thresholds.py failed ({proc.returncode}): "
                         f"{proc.stderr.strip()[:400]}")
    rows: list[dict] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue                       # the human table, when --jsonl was ignored
        r = json.loads(line)
        if games is not None and int(r["game"]) not in games:
            continue
        rows.append(r)
    if not rows:
        raise BuildError("thresholds.py produced no labelled rows -- "
                         "run tools/harvest.py --once first")
    return rows


def _game_of(d: Path) -> int | None:
    tail = d.name.rsplit("-", 1)[-1].rsplit("_", 1)[-1]
    return int(tail) if tail.isdigit() else None


def case_items(cases_dir: Path = CASES) -> dict[int, tuple[LineItem, ...]]:
    """{game: parsed line items}. Uses the same parser the round uses, so an index
    here can never mean a different row than an index there."""
    out: dict[int, tuple[LineItem, ...]] = {}
    seen: set[Path] = set()
    for pattern in CASE_GLOBS:
        for d in sorted(cases_dir.glob(pattern)):
            if not d.is_dir() or d in seen:
                continue
            seen.add(d)
            game = _game_of(d)
            if game is None:
                continue
            files = sorted(p for p in d.iterdir() if p.is_file())
            try:
                cf = read_files(files)
                out[game] = parse_line_items(cf.invoice_text)
            except Exception as e:                                  # noqa: BLE001
                # One unreadable case must not cost the whole store: the other 51
                # games are still a pool. Loud, per game, and counted at the end.
                print(f"  game {game}: parse failed ({type(e).__name__}) -- skipped")
    return out


# ------------------------------------------------------------------------- the build

def build(labels: list[dict], items_by_game: dict[int, tuple[LineItem, ...]]
          ) -> tuple[list[dict], Counter]:
    """Join labels to line-item metadata. Returns (rows, why-we-dropped counters)."""
    stats: Counter = Counter()
    rows: list[dict] = []
    for r in labels:
        stats["labels"] += 1
        game, item = int(r["game"]), int(r["item"])
        t_lo = float(r["t_lo"] or 0.0)
        n_fair = int(r.get("n_fair", 0) or 0)
        if n_fair <= 0 or t_lo <= 0:
            # The absence of a floor, not a proven zero. See the module docstring.
            stats["no_floor"] += 1
            continue
        items = items_by_game.get(game)
        if not items:
            stats["no_case"] += 1
            continue
        if not 1 <= item <= len(items):
            stats["index_out_of_range"] += 1
            continue
        li = items[item - 1]
        if li.idx != item:                    # parse.validate_items reindexes 1..N
            raise BuildError(f"game {game}: item {item} landed on idx {li.idx}")
        if li.qty <= 0:
            stats["bad_qty"] += 1
            continue
        u_lo = anchors.net_unit_floor(t_lo, li)
        if u_lo <= 0:
            stats["bad_u_lo"] += 1
            continue
        rows.append({
            "game": game, "item": item,
            "desc": li.description[:200],
            "qty": round(li.qty, 4),
            "unit": li.unit[:24],
            "unit_class": pricebook.unit_class(li.unit),
            "t_lo": round(t_lo, 2),
            "u_lo": round(u_lo, 4),
            "n_fair": n_fair,
        })
        stats["kept"] += 1
    rows.sort(key=lambda r: (r["game"], r["item"]))
    return rows, stats


def write_store(rows: list[dict], path: Path = STORE) -> None:
    """Temp file + os.replace, so a reader in another process sees either the old
    store or the new one and never a half-written line. `load()` tolerates a torn
    file anyway; this makes the tolerance unnecessary rather than load-bearing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


# ------------------------------------------------------------------------ self-check

def demo() -> None:
    """Hand-computed rows. No I/O, no labels, no case directories."""
    items = {
        4: (LineItem(idx=1, description="Remove laminate", qty=20.0, unit="m2"),
            LineItem(idx=2, description="Dispose of debris", qty=1.0, unit="pauschal")),
    }
    labels = [
        {"game": 4, "item": 1, "t_lo": 238.0, "t_hi": None, "n_fair": 2},
        {"game": 4, "item": 2, "t_lo": 0.0, "t_hi": 50.0, "n_fair": 0},   # no floor
        {"game": 4, "item": 9, "t_lo": 100.0, "t_hi": None, "n_fair": 1}, # off the end
        {"game": 7, "item": 1, "t_lo": 100.0, "t_hi": None, "n_fair": 1}, # no case dir
    ]
    rows, stats = build(labels, items)
    assert len(rows) == 1, rows
    assert stats["labels"] == 4 and stats["kept"] == 1, stats
    assert stats["no_floor"] == 1 and stats["index_out_of_range"] == 1, stats
    assert stats["no_case"] == 1, stats
    r = rows[0]
    assert r["unit_class"] == "m2" and r["t_lo"] == 238.0
    assert abs(r["u_lo"] - 238.0 / (20.0 * 1.19)) < 1e-3, r
    # the store round-trips through the loader, and the loader filters
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "anchors.jsonl"
        write_store(rows, p)
        assert len(anchors.load(p, before_game=5)) == 1
        assert anchors.load(p, before_game=4) == ()      # strictly earlier games only
    print("build_anchors self-check OK: floors only, indices aligned, VAT via "
          "anchors.net_unit_floor, store round-trips through the causal loader")


# ------------------------------------------------------------------------------ main

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--cases-dir", type=Path, default=CASES)
    p.add_argument("--out", type=Path, default=STORE)
    p.add_argument("--dry-run", action="store_true", help="print counts, write nothing")
    p.add_argument("--demo", action="store_true", help="run the self-check and exit")
    a = p.parse_args(argv)

    if a.demo:
        demo()
        return 0

    t0 = time.time()
    try:
        labels = load_labels()
    except (BuildError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        print(f"cannot build: {e}")
        return 1
    t_labels = time.time() - t0

    t1 = time.time()
    items = case_items(a.cases_dir)
    t_parse = time.time() - t1
    if not items:
        print(f"no case directories under {a.cases_dir} -- nothing to join against")
        return 1

    try:
        rows, stats = build(labels, items)
    except BuildError as e:
        print(f"cannot build: {e}")
        return 1
    if not rows:
        print("no proven floors joined -- store not written")
        return 1

    games = sorted({r["game"] for r in rows})
    by_unit = Counter(r["unit_class"] or "?" for r in rows)
    print(f"labels {stats['labels']}  ->  anchors {stats['kept']} "
          f"over {len(games)} games (parsed {sum(len(v) for v in items.values())} "
          f"items in {len(items)} cases)")
    print(f"  dropped: no floor {stats['no_floor']}, no case {stats['no_case']}, "
          f"index out of range {stats['index_out_of_range']}, "
          f"bad qty {stats['bad_qty']}, bad u_lo {stats['bad_u_lo']}")
    print(f"  unit classes: " + ", ".join(f"{u} {n}" for u, n in by_unit.most_common()))
    u = sorted(r["u_lo"] for r in rows)
    print(f"  u_lo net/unit: min {u[0]:,.2f}  p50 {u[len(u) // 2]:,.2f}  "
          f"max {u[-1]:,.2f}")
    print(f"  labels {t_labels:.2f}s, case parse {t_parse:.2f}s")

    if a.dry_run:
        print("--dry-run: nothing written")
        return 0
    write_store(rows, a.out)
    print(f"wrote {len(rows)} rows to {a.out}  "
          f"({a.out.stat().st_size:,} bytes; claim data, keep it out of git)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
