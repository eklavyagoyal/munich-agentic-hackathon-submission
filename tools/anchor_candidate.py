#!/usr/bin/env python3
"""Emit valuation candidates for `tools/bench_valuation.py`, with retrieval anchors.

    # the deterministic anchor prior, walk-forward, no network at all
    PYTHONPATH=. .venv/bin/python tools/anchor_candidate.py --mode floors --out cand.jsonl
    PYTHONPATH=. .venv/bin/python tools/anchor_candidate.py --mode book   --out book.jsonl

    # retrieval quality on its own terms: bracket / ceiling / best-anchor dex
    PYTHONPATH=. .venv/bin/python tools/anchor_candidate.py --report

    # the same anchors injected into the LLM ensemble prompt (costs provider calls)
    PYTHONPATH=. .venv/bin/python tools/anchor_candidate.py --mode llm \\
        --allow-model-network --games 20-31 --out llm_anchored.jsonl

    PYTHONPATH=. .venv/bin/python tools/anchor_candidate.py --demo    # self-check

Output is exactly what bench_valuation reads: one {"game","item","median","sigma"} per
line, `median` a GROSS LINE TOTAL in EUR. bench_valuation turns that into a charge
through `c2f.decision.quantile.decide`, so a candidate is scored through the same
Mills shading the tournament applies and never through its own median.

WALK-FORWARD, ENFORCED IN ONE PLACE

Game N is priced from `anchors.load(store, before_game=N)` and nothing else. The store
on disk holds every game ever harvested, so a replay of game 6 would otherwise be
predicting game 6 from game 41. `load()` takes the cutoff as a required keyword and
filters inside it, and `select()` asserts the cutoff on every row it returns.

The `--leak` modes exist to prove the filter is load-bearing rather than decorative,
and they print a banner saying the number is not a result:

  causal   games < N                 the only admissible setting
  game     games <= N, self excluded same-case siblings allowed in
  item     games <= N, self included THE ITEM ITSELF in its own pool

MODES

  book    price book alone. The baseline, on this exact universe.
  nn      the single nearest gated comparable REPLACES the book's median.
  floors  the anchor may only RAISE the book's median, never lower it. This is the
          framing the label supports: t_lo is a lower bound and says nothing about a
          ceiling, so an anchor is evidence that a price is at LEAST something.
  down    the anchor may only LOWER it. Kept because it is the control that makes
          `floors` a finding rather than a preference.
  llm     the ensemble prompt with the anchor block injected. Needs a provider.

Prints counts only. No invoice, policy or damage text reaches stdout or the output
file -- the output carries game, item and two numbers.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from c2f.core.models import Belief, LineItem                             # noqa: E402
from c2f.estimate import anchors as anchor_lib                           # noqa: E402
from c2f.estimate import pricebook                                       # noqa: E402
from c2f.ingest.parse import build_case, parse_line_items, read_files    # noqa: E402
from tools.build_anchors import CASE_GLOBS, load_labels                  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "data" / "cases"
STORE = ROOT / "data" / "anchors.jsonl"

# The anchor prior's spread. Wide on purpose: a proven floor pins the ORDER OF
# MAGNITUDE of one comparable line, not this line's price, so the honest statement is
# "about here, within a factor of ~1.6". Narrower would let decide() charge closer to
# the median than the evidence supports; sigma is not a lever on the outcome anyway
# (at q=1/2 the inverse normal CDF is 0), it is the uncertainty the decision layer
# prices.
ANCHOR_SIGMA = 0.50

MODES = ("book", "nn", "floors", "down", "llm")
LEAKS = ("causal", "game", "item")
# The population the bracketing numbers in anchors.py are quoted on. Games 1..5 have a
# pool of at most four games, so including them measures the pool's growth curve
# rather than the scheme.
REPORT_FIRST_GAME = 6
TAIL_T_LO = 1200.0
CHEAP_T_LO = 50.0


@dataclass(frozen=True)
class Prediction:
    game: int
    item: int
    median: float
    sigma: float
    source: str


# --------------------------------------------------------------------------- inputs

def case_dirs(cases_dir: Path = CASES) -> dict[int, Path]:
    out: dict[int, Path] = {}
    for pattern in CASE_GLOBS:
        for d in sorted(cases_dir.glob(pattern)):
            if not d.is_dir():
                continue
            tail = d.name.rsplit("-", 1)[-1].rsplit("_", 1)[-1]
            if tail.isdigit():
                out.setdefault(int(tail), d)
    return out


def parsed_items(d: Path) -> tuple[LineItem, ...]:
    cf = read_files(sorted(p for p in d.iterdir() if p.is_file()))
    return parse_line_items(cf.invoice_text)


def pool_for(store: Path, game: int, leak: str) -> tuple[anchor_lib.Anchor, ...]:
    """The admissible pool for pricing `game`. `causal` is the only honest one."""
    if leak == "causal":
        return anchor_lib.load(store, before_game=game)
    return anchor_lib.load(store, before_game=game + 1)      # leaks, deliberately


def _drop_self(pool: tuple[anchor_lib.Anchor, ...], game: int, item: int
               ) -> tuple[anchor_lib.Anchor, ...]:
    return tuple(a for a in pool if not (a.game == game and a.item == item))


# ---------------------------------------------------------------- the deterministic

# The DETERMINISTIC predictor uses ONE comparable, not anchors.K_COMP. These are two
# different jobs: the prompt shows the model a ranked shortlist of 3 and tells it the
# first is closest, while a deterministic rule has to commit to a number, and level
# accuracy PEAKS at one neighbour -- averaging more dilutes the one that matches. The
# --k-comp sweep below is what that claim rests on.
K_COMP_PREDICT = 1


def predict(item: LineItem, pool: tuple[anchor_lib.Anchor, ...], *, before_game: int,
            mode: str, gate: float = anchor_lib.GATE,
            k_comp: int = K_COMP_PREDICT) -> tuple[Belief, str]:
    """One line item -> (gross-total belief, which half of the rule produced it).

    `gate` and `k_comp` are exposed so the sweeps that justify their defaults can be
    re-run rather than quoted. `gate=0.0` is the ungated predictor -- the control that
    shows the gate, not the lexical matcher, is what earns the money.
    """
    book = pricebook.lookup(item)
    if mode == "book" or not pool:
        return book, "book"
    comps, _ladder = anchor_lib.select(item, pool, before_game=before_game,
                                      gate=gate, k_comp=k_comp)
    if not comps:
        return book, "book:no_comparable"        # the gate abstained. That IS the result.
    # Geometric mean over the retrieved shortlist. At k_comp=1 this IS the nearest
    # comparable; above 1 it is what a consumer that AVERAGES the list would get,
    # which is the quantity the k sweep is about.
    u = math.exp(statistics.fmean(math.log(c.u_lo) for c in comps))
    nn = anchor_lib.gross_line_total(u, item)
    if nn <= 0:
        return book, "book:degenerate_anchor"
    if mode == "nn":
        return Belief(nn, ANCHOR_SIGMA, source="anchor:nn"), "anchor"
    if mode == "floors":
        if nn > book.median:
            return Belief(nn, ANCHOR_SIGMA, source="anchor:floor"), "anchor"
        return book, "book:anchor_below"
    if mode == "down":
        if nn < book.median:
            return Belief(nn, ANCHOR_SIGMA, source="anchor:down"), "anchor"
        return book, "book:anchor_above"
    raise ValueError(f"unknown mode {mode!r}")


def run_deterministic(store: Path, cases: dict[int, Path], *, mode: str, leak: str,
                      games: set[int] | None, gate: float = anchor_lib.GATE,
                      k_comp: int = anchor_lib.K_COMP
                      ) -> tuple[list[Prediction], Counter]:
    stats: Counter = Counter()
    out: list[Prediction] = []
    for game in sorted(cases):
        if games is not None and game not in games:
            continue
        try:
            items = parsed_items(cases[game])
        except Exception as e:                                            # noqa: BLE001
            print(f"  game {game}: parse failed ({type(e).__name__}) -- skipped")
            stats["case_failed"] += 1
            continue
        pool = pool_for(store, game, leak)
        before = game if leak == "causal" else game + 1
        stats["pool_rows"] = max(stats["pool_rows"], len(pool))
        for it in items:
            p = pool if leak == "item" else _drop_self(pool, game, it.idx)
            belief, src = predict(it, p, before_game=before, mode=mode,
                                  gate=gate, k_comp=k_comp)
            stats[src] += 1
            stats["items"] += 1
            out.append(Prediction(game, it.idx, belief.median, belief.sigma, src))
    return out, stats


# ------------------------------------------------------------------- the model route

def run_llm(store: Path, cases: dict[int, Path], *, leak: str, games: set[int] | None,
            samples: int, timeout: float) -> tuple[list[Prediction], Counter]:
    """The ensemble prompt with the anchor block injected. Falls back to the price book
    for every item the ensemble abstains on, exactly as a round does."""
    from c2f.estimate import ensemble, llm

    stats: Counter = Counter()
    out: list[Prediction] = []
    if llm.backend() == "none":
        # Not an error: it is the honest null. A bench that silently reports the price
        # book as "the LLM with anchors" is the false null bench_all refuses to print.
        print("  no model backend — every item falls back to the price book. "
              "This run measures NOTHING about the model.")
    for game in sorted(cases):
        if games is not None and game not in games:
            continue
        d = cases[game]
        try:
            case = build_case(f"game-{game}", sorted(p for p in d.iterdir() if p.is_file()))
        except Exception as e:                                            # noqa: BLE001
            print(f"  game {game}: parse failed ({type(e).__name__}) -- skipped")
            stats["case_failed"] += 1
            continue
        pool = pool_for(store, game, leak)
        before = game if leak == "causal" else game + 1
        t0 = time.time()
        pre = ensemble.prefetch_sync(case, samples=samples, timeout=timeout,
                                     anchors=pool, anchor_game=before)
        elapsed = time.time() - t0
        print(f"  game {game}: {len(case.items)} items, {len(pre)} model estimates, "
              f"{elapsed:.1f}s, pool {len(pool)}")
        stats["seconds"] += elapsed
        for it in case.items:
            est = pre.get(it.idx)
            if est is not None and est.belief is not None:
                stats["model"] += 1
                out.append(Prediction(game, it.idx, est.belief.median, est.belief.sigma,
                                      "model"))
                continue
            stats["book_fallback"] += 1
            book = pricebook.lookup(it)
            out.append(Prediction(game, it.idx, book.median, book.sigma, "book"))
        stats["items"] += len(case.items)
    return out, stats


# --------------------------------------------------------------- retrieval diagnostics

@dataclass(frozen=True)
class _Checked:
    """One floored item, its selected anchors, and the errors that follow."""

    game: int
    item: int
    t_lo: float
    truth_u: float          # the proven floor, NET per unit -- the quantity anchors carry
    lo_u: float             # smallest selected anchor
    hi_u: float             # largest selected anchor
    best_dex: float         # |log10| of the CLOSEST anchor
    centroid_dex: float     # ... of the anchor set's log centroid: what averaging gets
    book_dex: float         # ... of the price book's own per-unit estimate
    had_comparable: bool

    @property
    def bracketed(self) -> bool:
        return self.lo_u <= self.truth_u <= self.hi_u

    @property
    def ceilinged(self) -> bool:
        """The largest anchor is at or above the truth. The direction that matters:
        undershooting t collects 0.50 per euro charged, overshooting 0.17."""
        return self.hi_u >= self.truth_u


def _book_net_per_unit(it: LineItem) -> float:
    """The price book's own estimate, in the anchors' units, so the two are comparable."""
    return pricebook.lookup(it).median / (1.0 + it.vat_rate) / max(it.qty, anchor_lib.QTY_FLOOR)


def check(store: Path, cases: dict[int, Path], *, first_game: int = REPORT_FIRST_GAME,
          leak: str = "causal", gate: float = anchor_lib.GATE,
          k_comp: int = anchor_lib.K_COMP, k_ladder: int = anchor_lib.K_LADDER
          ) -> list[_Checked]:
    """Retrieval quality per item, walk-forward. Pure measurement, no euros."""
    labels = {(int(r["game"]), int(r["item"])): r for r in load_labels()}
    out: list[_Checked] = []
    for game in sorted(cases):
        if game < first_game:
            continue
        try:
            items = parsed_items(cases[game])
        except Exception:                                                 # noqa: BLE001
            continue
        pool = pool_for(store, game, leak)
        if not pool:
            continue
        before = game if leak == "causal" else game + 1
        for it in items:
            lab = labels.get((game, it.idx))
            if lab is None:
                continue
            t_lo, n_fair = float(lab["t_lo"] or 0.0), int(lab.get("n_fair", 0) or 0)
            if n_fair <= 0 or t_lo <= 0:
                continue              # no floor was ever proven: nothing to check against
            truth = anchor_lib.net_unit_floor(t_lo, it)
            if truth <= 0:
                continue
            p = pool if leak == "item" else _drop_self(pool, game, it.idx)
            comps, ladder = anchor_lib.select(it, p, before_game=before, gate=gate,
                                              k_comp=k_comp, k_ladder=k_ladder)
            picked = comps + ladder
            if not picked:
                continue
            us = [a.u_lo for a in picked]
            book_u = _book_net_per_unit(it)
            out.append(_Checked(
                game=game, item=it.idx, t_lo=t_lo, truth_u=truth,
                lo_u=min(us), hi_u=max(us),
                best_dex=min(abs(math.log10(u / truth)) for u in us),
                centroid_dex=abs(statistics.fmean(math.log10(u) for u in us)
                                 - math.log10(truth)),
                book_dex=abs(math.log10(book_u / truth)) if book_u > 0 else math.nan,
                had_comparable=bool(comps),
            ))
    return out


def report(store: Path, cases: dict[int, Path], *, first_game: int = REPORT_FIRST_GAME,
           leak: str = "causal", gate: float = anchor_lib.GATE,
           k_comp: int = anchor_lib.K_COMP, k_ladder: int = anchor_lib.K_LADDER
           ) -> None:
    """Bracket / ceiling / best-anchor error of the SELECTED SET, against the truth.

    This is retrieval quality, not euros. It says whether the anchors put the truth
    inside their span and how close the best of them gets. The euro answer belongs to
    bench_valuation, run on a candidate file from --mode.
    """
    rows = check(store, cases, first_game=first_game, leak=leak, gate=gate,
                 k_comp=k_comp, k_ladder=k_ladder)
    if not rows:
        print("no scoreable items -- is the store built and are the cases present?")
        return

    def summarise(name: str, sel: list[_Checked]) -> None:
        if not sel:
            print(f"  {name:<24} (no items)")
            return
        books = [r.book_dex for r in sel if not math.isnan(r.book_dex)]
        print(f"  {name:<24}{len(sel):>5} items  bracket "
              f"{statistics.fmean(1.0 if r.bracketed else 0.0 for r in sel):.3f}  "
              f"ceiling {statistics.fmean(1.0 if r.ceilinged else 0.0 for r in sel):.3f}  "
              f"best-anchor {statistics.fmean(r.best_dex for r in sel):.3f} dex  "
              f"book {statistics.fmean(books) if books else float('nan'):.3f} dex")

    print(f"labels: tools/thresholds.py --jsonl     pool: {leak}"
          f"{'  (LEAKING -- not a result)' if leak != 'causal' else ''}"
          f"     games >= {first_game}, priced from games < N only")
    print(f"scheme: comparables gate {gate} x{k_comp} + unit ladder x{k_ladder}"
          "   (truth = proven floor, NET per unit)")
    summarise("all floored items", rows)
    summarise(f"tail t_lo >= {TAIL_T_LO:.0f}", [r for r in rows if r.t_lo >= TAIL_T_LO])
    summarise(f"mid {CHEAP_T_LO:.0f}..{TAIL_T_LO:.0f}",
              [r for r in rows if CHEAP_T_LO <= r.t_lo < TAIL_T_LO])
    summarise(f"cheap t_lo < {CHEAP_T_LO:.0f}", [r for r in rows if r.t_lo < CHEAP_T_LO])
    n_comp = sum(1 for r in rows if r.had_comparable)
    print(f"  got a gated comparable: {n_comp}/{len(rows)} = {n_comp / len(rows):.1%}"
          "  <- watch this per round: it IS the mechanism, and it can decay")
    widths = [math.log10(r.hi_u / r.lo_u) for r in rows if r.lo_u > 0]
    books = [r.book_dex for r in rows if not math.isnan(r.book_dex)]
    centroid = statistics.fmean(r.centroid_dex for r in rows)
    best = statistics.fmean(r.best_dex for r in rows)
    print(f"  anchor-set width {statistics.fmean(widths):.2f} dex;  "
          f"CENTROID error {centroid:.3f} dex   (the book: {statistics.fmean(books):.3f}, "
          f"the best single anchor: {best:.3f})")
    print(f"  ^ the centroid is where a consumer that AVERAGES the block lands. It beats "
          f"the book\n    by {statistics.fmean(books) - centroid:+.3f} dex but loses to "
          f"the best single anchor by {centroid - best:.3f} dex,\n    i.e. averaging "
          f"throws away {1 - best / centroid:.0%} of the available accuracy. That is why "
          "the prompt\n    says nearest-first and calls the ladder a RANGE, not a menu.")


# ------------------------------------------------------------------- prompt cost

# Characters per token. THERE IS NO TOKENIZER IN THIS VENV (no tiktoken, no
# transformers) and Anthropic's count_tokens is a network call, so every token number
# printed by --cost is CHARACTER-DERIVED. 3.6 is the middle of the range English-plus-
# German prose lands in for these tokenizers; the low/high columns exist so nobody
# reads the middle as measured. The block is mostly digits, unit codes and short
# nouns, which tokenizes WORSE than prose, so treat the high column as the planning
# number.
CHARS_PER_TOKEN = (3.2, 3.6, 4.0)


def _tok(chars: int) -> str:
    return " / ".join(f"{chars / c:,.0f}" for c in CHARS_PER_TOKEN)


def cost(store: Path, cases: dict[int, Path], *, samples: int = 3,
         games: set[int] | None = None) -> None:
    """Exact CHARACTER cost of the anchor block, plus the CPU cost of selecting it.

    What is MEASURED here: characters, and wall-clock seconds of selection. What is
    ESTIMATED: tokens, and therefore prefill time. The tier-2 deadline is 52s hard and
    this file's own history is a prompt-size regression that took 17 items to 53.9s
    and returned 2 usable estimates, so the estimate is not the gate --
    tools/bench_llm_valuation.py --allow-model-network is, because it records
    latency_seconds per call.
    """
    from c2f.estimate import ensemble

    blocks: list[int] = []
    per_case: list[tuple[int, int, int, int, float]] = []
    for game in sorted(cases):
        if games is not None and game not in games:
            continue
        try:
            items = parsed_items(cases[game])
        except Exception:                                                 # noqa: BLE001
            continue
        pool = pool_for(store, game, "causal")
        if not pool:
            continue
        t0 = time.perf_counter()
        rendered = [anchor_lib.block(it, pool, before_game=game) for it in items]
        select_s = time.perf_counter() - t0
        sizes = [len(b) for b in rendered]
        blocks.extend(s for s in sizes if s)
        # What one item call already carries, measured on the real case, with the
        # digest left out because it is model-generated text we cannot measure offline.
        invoice = "\n".join(ensemble._label(i) for i in items)
        base = len(ensemble._ITEM_PROMPT.format(
            digest="", damage="x" * 1_500, invoice=invoice, anchors="",
            idx=1, description=items[0].description, qty="1", unit=items[0].unit))
        per_case.append((game, len(items), base, sum(sizes), select_s))
    if not blocks:
        print("no rendered blocks -- is the store built?")
        return

    blocks.sort()
    n = len(blocks)
    row = len(anchor_lib._row(anchor_lib.Anchor(1, 1, "x" * 50, 12.5, "m2", "m2",
                                                1190.0, 1000.0, 1)))
    print("MEASURED IN CHARACTERS. Tokens are estimates at "
          f"{CHARS_PER_TOKEN[0]} / {CHARS_PER_TOKEN[1]} / {CHARS_PER_TOKEN[2]} "
          "chars per token; no tokenizer is installed.")
    print(f"  one rendered row          {row:>7,} chars   ~{_tok(row)} tok")
    print(f"  SYSTEM framing paragraph  {len(anchor_lib.ANCHOR_SYSTEM_NOTE):>7,} chars   "
          f"~{_tok(len(anchor_lib.ANCHOR_SYSTEM_NOTE))} tok   "
          "<- rides in SYSTEM behind llm.py's cache_control breakpoint: constant for "
          "the whole\n     tournament, so it is prefill-free after the first call and "
          "is NOT in the per-item numbers below.")
    print(f"  per-item block ({n} items with a non-empty block): "
          f"median {blocks[n // 2]:,}  p90 {blocks[int(n * 0.9)]:,}  max {blocks[-1]:,} chars")
    print(f"  ... i.e. median ~{_tok(blocks[n // 2])} tok, max ~{_tok(blocks[-1])} tok "
          "per item call")

    print(f"\nWORST CASES, at {samples} samples per item "
          "(the anchor block is identical across an item's samples, so it is charged "
          f"{samples}x):")
    print(f"  {'game':>5}{'items':>7}{'calls':>7}{'base chars/call':>17}"
          f"{'anchor chars added':>20}{'added %':>9}{'select CPU':>12}")
    for game, n_items, base, added, sel in sorted(per_case, key=lambda r: -r[1])[:6]:
        calls = n_items * samples
        base_total = base * calls
        add_total = added * samples
        print(f"  {game:>5}{n_items:>7}{calls:>7}{base:>17,}{add_total:>20,}"
              f"{add_total / base_total:>8.1%}{sel * 1000:>10.0f} ms")
    print("  base chars/call EXCLUDES the policy digest, which is model-generated and "
          "cannot be\n  measured offline; at the design's ~250 token estimate the "
          "denominator grows and the\n  added percentage shrinks, so the numbers above "
          "are the PESSIMISTIC bound.")
    biggest = max(per_case, key=lambda r: r[1])
    add_tok = biggest[3] * samples / CHARS_PER_TOKEN[0]
    print(f"\n  LARGEST CASE game {biggest[0]}, {biggest[1]} items: "
          f"+{biggest[3] * samples:,} chars = ~{add_tok:,.0f} added prefill tokens "
          f"across {biggest[1] * samples} calls,\n  and {biggest[4] * 1000:.0f} ms of "
          "CPU to select every block. The calls fan out concurrently, so the wall-clock\n"
          "  cost is one call's extra prefill, not the sum -- but that is an inference, "
          "not a measurement.")


# ---------------------------------------------------------------------------- output

def write(preds: list[Prediction], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            for p in preds:
                fh.write(json.dumps({"game": p.game, "item": p.item,
                                     "median": round(p.median, 2),
                                     "sigma": round(p.sigma, 4)}) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


# ------------------------------------------------------------------------ self-check

def demo() -> None:
    """Hand-computed. No store, no cases, no network."""
    def anc(game, item, desc, u, unit="stk", qty=1.0):
        return anchor_lib.Anchor(game=game, item=item, desc=desc, qty=qty, unit=unit,
                                 unit_class=pricebook.unit_class(unit),
                                 t_lo=u * qty * 1.19, u_lo=u, n_fair=1)

    # An "unknown pcs" line: the book has no keyword for it, so it prices every such
    # line the same. That is the population anchors exist for.
    it = LineItem(idx=3, description="Replacement of the damaged control unit",
                  qty=1.0, unit="pcs")
    book = pricebook.lookup(it)
    pool = (anc(1, 1, "Replacement of damaged control unit", 2000.0),
            anc(2, 1, "Tow truck recovery", 150.0),
            anc(3, 1, "HDMI cable", 10.0))

    b, src = predict(it, pool, before_game=9, mode="book")
    assert src == "book" and b.median == book.median

    b, src = predict(it, pool, before_game=9, mode="nn")
    assert src == "anchor", src
    assert abs(b.median - 2000.0 * 1.19) < 1e-6, b        # qty 1, gross of the net floor
    assert b.sigma == ANCHOR_SIGMA

    b, src = predict(it, pool, before_game=9, mode="floors")
    assert src == "anchor" and b.median > book.median     # the anchor RAISED it
    b, src = predict(it, pool, before_game=9, mode="down")
    assert src == "book:anchor_above", src                # ... so `down` declines

    # quantity is carried through the conversion, both ways
    it10 = LineItem(idx=1, description="Replacement of damaged control unit",
                    qty=10.0, unit="pcs")
    b10, _ = predict(it10, pool, before_game=9, mode="nn")
    assert abs(b10.median - 10 * 2000.0 * 1.19) < 1e-6, b10

    # the gate abstains rather than returning a confident wrong neighbour
    odd = LineItem(idx=1, description="Scaffolding hire for the gable end",
                   qty=1.0, unit="pcs")
    _, src = predict(odd, pool, before_game=9, mode="floors")
    assert src == "book:no_comparable", src

    # an empty pool is the shipped price book, in every mode
    for m in ("nn", "floors", "down"):
        b0, src0 = predict(it, (), before_game=9, mode=m)
        assert src0 == "book" and b0.median == book.median, (m, src0)

    # _drop_self removes exactly one row and only the right one
    assert len(_drop_self(pool, 1, 1)) == 2 and len(_drop_self(pool, 1, 2)) == 3

    # the emitted file is what bench_valuation parses
    import tempfile
    from tools.bench_valuation import charges_from_predictions
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "c.jsonl"
        write([Prediction(4, 1, 1234.5, 0.5, "anchor")], p)
        ch = charges_from_predictions(p)
        assert list(ch) == [(4, 1)], ch
        assert 0.0 < ch[(4, 1)] < 1234.5, ch                # decide() shades below median
    print("anchor_candidate self-check OK: gate abstains to the book, floors only "
          "raises, qty and VAT round-trip, output parses in bench_valuation")


# ------------------------------------------------------------------------------ main

def _games(spec: str | None) -> set[int] | None:
    if not spec:
        return None
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part.lstrip("-"):
            lo, hi = part.split("-", 1)
            out.update(range(int(lo), int(hi) + 1))
        else:
            out.add(int(part))
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--mode", choices=MODES, default="floors")
    p.add_argument("--leak", choices=LEAKS, default="causal",
                   help="NOT for results. 'game' and 'item' reproduce the leak numbers.")
    p.add_argument("--store", type=Path, default=STORE)
    p.add_argument("--cases-dir", type=Path, default=CASES)
    p.add_argument("--games", default=None, help="e.g. 20-31 or 4,8,15")
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--report", action="store_true",
                   help="retrieval diagnostics (bracket / ceiling / dex), no output file")
    p.add_argument("--cost", action="store_true",
                   help="prompt cost of the anchor block, in characters, plus select CPU")
    p.add_argument("--gate", type=float, default=anchor_lib.GATE,
                   help="similarity gate. 0 is the UNGATED control.")
    p.add_argument("--k-comp", type=int, default=K_COMP_PREDICT,
                   help="comparables the DETERMINISTIC predictor averages in log space. "
                        "1 is the default and the measured optimum; the PROMPT shows "
                        f"{anchor_lib.K_COMP} ranked rows and does its own weighting.")
    p.add_argument("--k-ladder", type=int, default=anchor_lib.K_LADDER,
                   help="ladder rungs. --report only.")
    p.add_argument("--report-k-comp", type=int, default=anchor_lib.K_COMP,
                   help="comparables the --report scheme selects (the PROMPT's number)")
    p.add_argument("--samples", type=int, default=3, help="--mode llm ensemble size")
    p.add_argument("--timeout", type=float, default=25.0)
    p.add_argument("--allow-model-network", action="store_true",
                   help="required by --mode llm: a run with no model calls is not evidence")
    p.add_argument("--demo", action="store_true")
    a = p.parse_args(argv)

    if a.demo:
        demo()
        return 0

    cases = case_dirs(a.cases_dir)
    if not cases:
        print(f"no case directories under {a.cases_dir}")
        return 1
    if not a.store.exists():
        print(f"no anchor store at {a.store} -- run tools/build_anchors.py first")
        return 1
    if a.leak != "causal":
        print("*" * 78)
        print(f"*** --leak {a.leak}: THE POOL SEES GAME N WHILE PRICING GAME N. Any number")
        print("*** below is self-prediction, not a result. It exists to prove the causal")
        print("*** filter is load-bearing. Never quote it as a score.")
        print("*" * 78)

    if a.report:
        report(a.store, cases, leak=a.leak, gate=a.gate, k_comp=a.report_k_comp,
               k_ladder=a.k_ladder)
        return 0
    if a.cost:
        cost(a.store, cases, samples=a.samples, games=_games(a.games))
        return 0

    games = _games(a.games)
    t0 = time.time()
    if a.mode == "llm":
        if not a.allow_model_network:
            print("--mode llm needs --allow-model-network (it makes provider calls)")
            return 1
        preds, stats = run_llm(a.store, cases, leak=a.leak, games=games,
                               samples=a.samples, timeout=a.timeout)
    else:
        preds, stats = run_deterministic(a.store, cases, mode=a.mode, leak=a.leak,
                                         games=games, gate=a.gate, k_comp=a.k_comp)
    if not preds:
        print("no predictions produced")
        return 1

    print(f"mode {a.mode}  leak {a.leak}  {stats['items']} items over "
          f"{len({p.game for p in preds})} games  in {time.time() - t0:.2f}s")
    print("  sources: " + ", ".join(f"{k} {v}" for k, v in sorted(stats.items())
                                    if k not in ("items", "pool_rows", "seconds")))
    if a.mode != "llm":
        n_anchor = sum(1 for p in preds if p.source == "anchor")
        print(f"  anchor supplied the median on {n_anchor}/{len(preds)} items "
              f"= {n_anchor / len(preds):.1%}; largest pool {stats['pool_rows']} rows")
    out = a.out or ROOT / "data" / f"cand_{a.mode}_{a.leak}_g{a.gate}_k{a.k_comp}.jsonl"
    write(preds, out)
    print(f"wrote {len(preds)} rows to {out}")
    print("score it:  PYTHONPATH=. .venv/bin/python tools/bench_valuation.py "
          f"--source file --path {out} --vs events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
