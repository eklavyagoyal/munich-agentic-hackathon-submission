#!/usr/bin/env python
"""One round, end to end, inside 60 seconds.

  python run.py --case-dir cases/case0 --case-id 0 --dry-run    # rehearse
  python run.py --case-id 7 --zip cases/case7.zip              # live

Latency budget (GAMEPLAN §4). The point of the two stages is that after stage 1 the
deadline can no longer hurt us: everything after it is pure upside, and a stage-2
timeout leaves the stage-1 submission standing.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

from c2f import api, decide, value
from c2f.extract import Case, line_items
from c2f.value import Estimate

log = logging.getLogger("c2f")

# Raise toward 1.15 once round data shows the field charging fairly (GAMEPLAN §2.2).
BOLDNESS = float(os.environ.get("C2F_BOLDNESS", "1.0"))
# Global bias correction from the calibration loop (GAMEPLAN §6). 1.0 = uncalibrated.
CALIBRATION = float(os.environ.get("C2F_CALIBRATION", "1.0"))


def rows_from(estimates: list[Estimate]) -> list[dict]:
    """Estimates -> the two numbers, with the trap guards from GAMEPLAN §8."""
    rows = []
    for e in estimates:
        m = e.gross_median() * CALIBRATION
        lo, hi = e.gross_quantiles()
        sigma = decide.sigma_from_quantiles(lo, hi)
        a, b = decide.submission(m, sigma, e.covered, e.related, boldness=BOLDNESS)
        rows.append(
            {"position": e.item.pos, "a": a, "b": b, "m": m, "sigma": sigma, "est": e}
        )
    return rows


def check(rows: list[dict]) -> None:
    """Trap 1: the -3247 mistake. Never leave here with a blanket zero acceptance limit."""
    if not rows:
        raise RuntimeError("no rows to submit — refusing to send an empty submission")
    priced = [r for r in rows if r["est"].source != "failed"]
    if not priced:
        raise RuntimeError("every line item failed to price — do not submit defaults")
    if all(r["b"] == 0 for r in rows) and not all(
        not (r["est"].covered and r["est"].related) for r in rows
    ):
        raise RuntimeError("all acceptance limits are 0 but not all items are uncovered")


def show(rows: list[dict], elapsed: float, tag: str) -> None:
    print(f"\n=== {tag}  t+{elapsed:.1f}s ===")
    print(f"{'pos':>4} {'qty':>7} {'unit':<9} {'m (gross)':>10} {'sig':>5} {'a':>9} {'b':>9}  item")
    for r in rows:
        e = r["est"]
        mark = "" if e.covered and e.related else "  NOT COVERED" if not e.covered else "  UNRELATED"
        if e.source == "failed":
            mark = "  *** NO ESTIMATE ***"
        print(
            f"{r['position']:>4} {e.item.qty:>7g} {e.item.unit:<9} {r['m']:>10.2f} "
            f"{r['sigma']:>5.2f} {r['a']:>9.2f} {r['b']:>9.2f}  {e.item.description[:40]}{mark}"
        )
        if e.flag:
            print(f"{'':>4} ⚑ {e.flag}")
    print(f"{'':>4} {'':>7} {'':<9} {'':>10} {'':>5} {sum(r['a'] for r in rows):>9.2f} "
          f"{sum(r['b'] for r in rows):>9.2f}  TOTAL")


def merge(fast: list[Estimate], deep: list[Estimate]) -> list[Estimate]:
    """Deep wins, but a deep failure falls back to the fast estimate rather than to zero."""
    by_pos = {e.item.pos: e for e in fast}
    return [by_pos.get(d.item.pos, d) if d.source == "failed" else d for d in deep]


async def round_(case_dir: Path, case_id: str, *, dry_run: bool, deadline: float) -> None:
    t0 = time.monotonic()
    el = lambda: time.monotonic() - t0  # noqa: E731

    case = Case.load(case_dir)
    log.warning(
        "loaded: policy %dc, damage %dc, invoice %dc, %d image(s)  [t+%.1fs]",
        len(case.policy), len(case.damage), len(case.invoice_text), len(case.images), el(),
    )

    items = await line_items(case, fast=True)
    if not items:
        raise RuntimeError("no line items — cannot submit anything meaningful")
    log.warning("%d line items  [t+%.1fs]", len(items), el())

    # ---- stage 1: the safety net -------------------------------------------------
    fast = await value.value_case(case, items, fast=True, timeout=14.0)
    rows = rows_from(fast)
    check(rows)
    show(rows, el(), "STAGE 1 (fast)")
    api.submit(case_id, rows, dry_run=dry_run, tag="s1")

    # ---- stage 2: the real answer, inside whatever time is left -------------------
    left = deadline - el()
    if left < 8:
        log.warning("only %.1fs left — keeping stage 1", left)
        return
    try:
        deep = await asyncio.wait_for(_stage2(case, items, left), timeout=left)
    except asyncio.TimeoutError:
        log.warning("stage 2 timed out with %.1fs budget — stage 1 stands", left)
        return
    except Exception as e:
        log.error("stage 2 failed (%s) — stage 1 stands", e)
        return

    rows2 = rows_from(merge(fast, deep))
    check(rows2)
    show(rows2, el(), "STAGE 2 (deep, final)")
    api.submit(case_id, rows2, dry_run=dry_run, tag="s2")


async def _stage2(case: Case, items, budget: float) -> list[Estimate]:
    dg = ""
    try:
        dg = await asyncio.wait_for(value.digest(case, timeout=min(18.0, budget * 0.4)), budget * 0.45)
    except Exception as e:
        log.warning("policy digest unavailable (%s) — valuing without it", e)
    return await value.value_case(case, items, fast=False, digest_text=dg, timeout=25.0)


def self_test() -> int:
    from c2f import decide as d, extract as x, value as v

    d.demo(); x.demo(); v.demo()
    print("\nall self-checks passed")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--case-id", default="0")
    p.add_argument("--case-dir", type=Path, help="already-decrypted case folder")
    p.add_argument("--zip", type=Path, help="encrypted archive; fetches the key and decrypts")
    p.add_argument("--dry-run", action="store_true", help="write the payload to logs/, do not post")
    p.add_argument("--deadline", type=float, default=55.0, help="hard stop, seconds into the round")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
    if a.self_test:
        return self_test()

    case_dir = a.case_dir
    if a.zip:
        key = api.fetch_key(a.case_id)
        case_dir = api.decrypt(a.zip, key, Path("cases") / f"case{a.case_id}")
    if not case_dir:
        p.error("need --case-dir or --zip")

    asyncio.run(round_(case_dir, a.case_id, dry_run=a.dry_run, deadline=a.deadline))
    return 0


if __name__ == "__main__":
    sys.exit(main())
