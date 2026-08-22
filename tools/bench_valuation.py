"""Score a valuation candidate against the PROVEN brackets on `t`. Offline, no API.

    PYTHONPATH=. .venv/bin/python tools/bench_valuation.py --source events
    PYTHONPATH=. .venv/bin/python tools/bench_valuation.py --source file --path cand.jsonl
    PYTHONPATH=. .venv/bin/python tools/bench_valuation.py --source events --vs file:cand.jsonl
    PYTHONPATH=. .venv/bin/python tools/bench_valuation.py --demo        # self-check

WHY THIS EXISTS

Three research tracks are trying to beat the price book, and each one has started by
rebuilding the same join in a scratchpad: our charges from the event log, the proven
brackets from tools/thresholds.py, count the unders. That join has a trap in it (the
event log carries BOTH tiers per round, so a naive dict silently scores tier 2) and a
subtler one in the metric (an item can look bad because we were wrong, or because
nobody ever proved anything about it, and those are not the same result). Three
scratchpads will disagree by the afternoon. Once, in the repo, with a self-check.

Labels come from `tools/thresholds.py --jsonl` and nowhere else -- this file contains
no SQL. Hand-rolled SQL against `transactions` has produced a confidently INVERTED
answer twice. Charges for a candidate come from `c2f.decision.quantile.decide`, so a
median/sigma pair is scored through the same shading the tournament actually applies,
not through its own median.

THE METRIC (docs/MODEL_BRIEF.md 1: as issuer we are H)

A fair charge is paid by all 16 opponents, including the ones who reject it. A
fraudulent charge that everybody rejects pays nothing. So per labelled item:

    a <= t_lo                 CERTAINLY FAIR   -> income 16 * a
    t_hi known and a > t_hi   CERTAINLY FRAUD  -> income 0
    otherwise                 UNPROVABLE       -> excluded from income

    PROVEN INCOME = sum of the above over every labelled item
    BEST POSSIBLE = sum of 16 * t_lo over every labelled item
    SCORE         = PROVEN INCOME / BEST POSSIBLE

WHAT IS EXACT AND WHAT IS A BOUND

Exact: the three classes. `t >= t_lo` because a charge that was rejected and still
PAID can only sit in the fair column, and `t < t_hi` because an ACCEPTED charge that
paid nothing to its issuer can only sit in the fraud column. Nothing here is a model.

A BOUND, and only ever downward:

  * BEST POSSIBLE uses t_lo, a floor. The real ceiling on achievable income is at the
    unknown `t >= t_lo`, so BEST POSSIBLE understates and SCORE overstates. Both
    sources in a `--vs` are measured against the same floor, so the comparison is
    still fair; the absolute number is not a percentage of anything real.
  * UNPROVABLE items earn 0 in the numerator but keep their full 16 * t_lo in the
    denominator. A candidate that charges into the unprovable zone therefore looks
    worse than it might be. This is deliberate and it is the reason SCORE is the
    headline: crediting unprovable items would let a candidate erase any penalty by
    charging absurdly high on the 23% of scored items that have no t_hi at all. To keep that
    conservatism visible rather than silent, every report also prints
      - the UNPROVABLE count and its share of BEST POSSIBLE, beside the score, and
      - SCORE_HI, the same number with every unprovable charge credited as if fair.
    SCORE and SCORE_HI bracket the truth. A change that raises one and lowers the
    other is NOT proven, in either direction. (Same discipline as score.py's
    `unpriced_risk`: a number that silently assumes the invisible rows are free is
    worse than no number.)
  * t_lo is the largest charge SEEN to be fair, and on 23 of our 149 fair items that
    charge is OUR OWN. `a <= t_lo` is then true by construction and one cent more
    makes the item UNPROVABLE, dropping the whole 16 * a from the numerator. Between
    the submitted `a` and the same belief re-run through decide(), sub-euro rounding
    alone moved 8 items across that line and 21,126 EUR with them. So the report
    prints how much proven income sits within 1% of its floor: a knife edge is not a
    margin, and a candidate that beats the baseline by less than that is noise.
  * t_lo == 0 with no fair charge ever seen is NOT a proven price of zero, it is the
    absence of a floor. Those items contribute 0 to both halves of the score, so they
    move nothing -- but they are 94 of our 161 "overcharges", which is why they are
    counted out separately in the diagnostics instead of inflating a headline.

DIAGNOSTICS

The three classes are exactly the ad-hoc scripts' under / over / indeterminate:
`a <= t_lo` IS undercharging, `a > t_hi` IS proven overcharging. FOREGONE EUR is
reported as those scripts defined it, `sum of 16 * (t_lo - a)` over the unders -- a
proven lower bound on money left on the table by undercharging ALONE. It is not the
gap to BEST POSSIBLE, which also contains the proven-fraud and unprovable items.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from c2f.core.models import Belief          # noqa: E402
from c2f.decision.quantile import decide    # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EVENTS = ROOT / "data" / "events" / "tournament.jsonl"
THRESHOLDS = ROOT / "tools" / "thresholds.py"

OPPONENTS = 16          # 17 teams; a fair charge is paid by every other one
AT_FLOOR_FRACTION = 0.99   # "a is essentially AT t_lo", for the knife-edge warning
LABEL_TIMEOUT_S = 180.0

FAIR, FRAUD, UNPROVABLE = "fair", "fraud", "unprovable"

Key = tuple[int, int]   # (game, item)


# --------------------------------------------------------------------------- labels

@dataclass(frozen=True)
class Bracket:
    """One row of `tools/thresholds.py --jsonl`. t_hi None means no ceiling proven."""

    game: int
    item: int
    t_lo: float
    t_hi: float | None
    n_fair: int = 0
    n_fraud: int = 0

    @property
    def has_floor(self) -> bool:
        """A floor somebody actually proved, as opposed to the trivial t >= 0."""
        return self.n_fair > 0 and self.t_lo > 0.0


def load_brackets(games: set[int] | None = None) -> dict[Key, Bracket]:
    """Run the sanctioned label tool and parse its JSONL. The only label source."""
    if not THRESHOLDS.exists():
        raise RuntimeError(f"missing {THRESHOLDS}")
    proc = subprocess.run(
        [sys.executable, str(THRESHOLDS), "--jsonl"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=LABEL_TIMEOUT_S,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"thresholds.py failed ({proc.returncode}): "
                           f"{proc.stderr.strip()[:400]}")
    out: dict[Key, Bracket] = {}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue                      # the human table, when --jsonl was ignored
        r = json.loads(line)
        if games is not None and r["game"] not in games:
            continue
        out[(r["game"], r["item"])] = Bracket(
            game=r["game"], item=r["item"], t_lo=float(r["t_lo"]),
            t_hi=None if r["t_hi"] is None else float(r["t_hi"]),
            n_fair=int(r.get("n_fair", 0)), n_fraud=int(r.get("n_fraud", 0)),
        )
    if not out:
        raise RuntimeError("thresholds.py produced no labelled rows -- "
                           "run tools/harvest.py --once first")
    return out


# --------------------------------------------------------------------- belief sources

def charges_from_event_lines(lines: Iterable[str],
                            from_belief: bool = False) -> dict[Key, float]:
    """(game,item) -> our charge `a`, from tournament.jsonl lines.

    LAST write wins, exactly as tools/score.py does it: both tiers emit
    `item.decided` per round, and tier 2 is the submission that stood. Keying on
    (round, idx) without knowing that scores tier 2 by accident rather than by
    choice, which is the same answer for the wrong reason.

    `from_belief` re-derives the charge from the logged belief through decide()
    instead of reading the submitted `a`. The submitted `a` is what we actually did
    (guards, clamps and all) and is the honest baseline; the re-derived one is the
    apples-to-apples comparison against a candidate file, which has no guards. On
    the current log the two differ by at most 0.62 EUR on any item.
    """
    charges: dict[Key, float] = {}
    beliefs: dict[Key, tuple[float, float]] = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue                      # a torn last line mid-append is not an error
        kind = e.get("type")
        if kind not in ("item.decided", "item.belief"):
            continue
        p = e.get("payload") or {}
        try:
            key = (int(e["round"]), int(p["idx"]))
        except (KeyError, TypeError, ValueError):
            continue
        if kind == "item.decided" and "a" in p:
            charges[key] = float(p["a"])
        elif kind == "item.belief" and "median" in p and "sigma" in p:
            beliefs[key] = (float(p["median"]), float(p["sigma"]))
    if not from_belief:
        return charges
    out: dict[Key, float] = {}
    for key in charges:                   # only items we actually submitted
        mb = beliefs.get(key)
        if mb is None:
            continue
        out[key] = decide(Belief(mb[0], mb[1]), True)[0]
    return out


def charges_from_events(path: Path, from_belief: bool = False) -> dict[Key, float]:
    if not path.exists():
        raise RuntimeError(f"no event log at {path}")
    with path.open(encoding="utf-8") as fh:
        return charges_from_event_lines(fh, from_belief=from_belief)


def charges_from_predictions(path: Path) -> dict[Key, float]:
    """Candidate file: one {"game","item","median","sigma"} object per line.

    The charge is decide()'s, never the candidate's median: a valuation is a belief,
    and the tournament turns a belief into a charge by Mills shading. Scoring the
    median directly would credit a candidate for a charge we would never submit.
    """
    if not path.exists():
        raise RuntimeError(f"no prediction file at {path}")
    out: dict[Key, float] = {}
    with path.open(encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                r = json.loads(line)
            except ValueError as exc:
                raise RuntimeError(f"{path}:{n} is not JSON: {exc}") from exc
            try:
                key = (int(r["game"]), int(r["item"]))
                median, sigma = float(r["median"]), float(r["sigma"])
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"{path}:{n} needs game, item, median, sigma -- {exc}") from exc
            try:
                belief = Belief(median, sigma)
            except ValueError as exc:
                # Belief guards median >= 0 and 0 < sigma <= 3. Say which line, so a
                # 40k-row candidate file is one edit away from running.
                raise RuntimeError(f"{path}:{n} game {key[0]} item {key[1]}: {exc}") from exc
            out[key] = decide(belief, True)[0]
    return out


def label_for(spec: str) -> str:
    """A short column heading. A full path in a table header destroys the layout, so
    the header prints the mapping once and the columns stay narrow."""
    if spec == "events":
        return "events"
    return Path(spec[len("file:"):]).stem[:20] or "candidate"


def load_source(spec: str, from_belief: bool = False) -> dict[Key, float]:
    """spec is "events" or "file:PATH"."""
    if spec == "events":
        return charges_from_events(EVENTS, from_belief=from_belief)
    if spec.startswith("file:"):
        return charges_from_predictions(Path(spec[len("file:"):]).expanduser())
    raise RuntimeError(f"source must be 'events' or 'file:PATH', got {spec!r}")


# --------------------------------------------------------------------------- scoring

def classify(a: float, br: Bracket) -> str:
    """FAIR / FRAUD / UNPROVABLE. Exclusive and exhaustive, in that order."""
    if a <= br.t_lo:
        return FAIR                        # proven: t >= t_lo >= a, so all 16 pay
    if br.t_hi is not None and a > br.t_hi:
        return FRAUD                       # proven: t < t_hi < a, so nobody pays
    return UNPROVABLE


@dataclass
class Tally:
    """One game, or the total. EUR fields are already multiplied by OPPONENTS."""

    n_items: int = 0
    n_fair: int = 0
    n_fraud: int = 0
    n_unprovable: int = 0
    n_no_floor: int = 0                    # t_lo == 0 with no fair charge ever seen
    proven_income: float = 0.0
    best_possible: float = 0.0
    best_classified: float = 0.0           # best over FAIR|FRAUD items only
    best_unprovable: float = 0.0
    optimistic_income: float = 0.0         # unprovable charges credited as if fair
    foregone: float = 0.0                  # sum 16*(t_lo - a) over the unders
    n_at_floor: int = 0                    # fair items sitting within 1% of t_lo
    income_at_floor: float = 0.0           # ... and the income riding on that cent

    def add(self, other: "Tally") -> None:
        for f in self.__dataclass_fields__:
            setattr(self, f, getattr(self, f) + getattr(other, f))

    def _ratio(self, num: float) -> float:
        return num / self.best_possible if self.best_possible > 0 else 0.0

    @property
    def scoreable(self) -> bool:
        """False when every t_lo in scope is 0: no floor was ever proven, so there is
        no denominator and a printed 0.000 would read as a failure."""
        return self.best_possible > 0

    @property
    def score(self) -> float:
        """The spec. A downward-biased lower bound; see the module docstring."""
        return self._ratio(self.proven_income)

    @property
    def score_hi(self) -> float:
        """Upper bound: every unprovable charge assumed fair. May exceed 1.0."""
        return self._ratio(self.proven_income + self.optimistic_income)

    @property
    def score_classified(self) -> float:
        """Score with unprovable items out of the denominator too. Gameable -- a
        candidate can shrink this denominator by charging into the unprovable zone --
        so it is a diagnostic, never a ranking."""
        return (self.proven_income / self.best_classified
                if self.best_classified > 0 else 0.0)

    @property
    def unprovable_share(self) -> float:
        return self._ratio(self.best_unprovable)


@dataclass
class Result:
    per_game: dict[int, Tally] = field(default_factory=dict)
    total: Tally = field(default_factory=Tally)
    n_no_charge: int = 0                   # labelled items this source never priced
    n_no_label: int = 0                    # priced items with no proven bracket
    games: tuple[int, ...] = ()


def score(charges: dict[Key, float], brackets: dict[Key, Bracket]) -> Result:
    """Score every labelled item this source priced. Pure -- no I/O, so demo() can
    hand it three hand-computed rows."""
    res = Result()
    per: dict[int, Tally] = defaultdict(Tally)
    for key in sorted(set(charges) & set(brackets)):
        a, br = charges[key], brackets[key]
        t = per[br.game]
        t.n_items += 1
        best = OPPONENTS * br.t_lo
        t.best_possible += best
        if not br.has_floor:
            t.n_no_floor += 1
        cls = classify(a, br)
        if cls == FAIR:
            t.n_fair += 1
            t.proven_income += OPPONENTS * a
            t.best_classified += best
            t.foregone += OPPONENTS * (br.t_lo - a)
            if br.t_lo > 0 and a >= AT_FLOOR_FRACTION * br.t_lo:
                # Often t_lo IS this charge: a floor is the largest charge seen to be
                # fair, and ours qualifies whenever a reviewer rejected and still
                # paid. The class is exact, but it is exact about a cliff -- one cent
                # more and the whole 16*a leaves the numerator for UNPROVABLE. Count
                # it so nobody reads a knife-edge as a margin.
                t.n_at_floor += 1
                t.income_at_floor += OPPONENTS * a
        elif cls == FRAUD:
            t.n_fraud += 1
            t.best_classified += best      # income 0: we collected nothing
        else:
            t.n_unprovable += 1
            t.best_unprovable += best
            t.optimistic_income += OPPONENTS * a
    res.per_game = dict(sorted(per.items()))
    for t in res.per_game.values():
        res.total.add(t)
    played = {g for g, _ in charges}
    res.n_no_charge = sum(1 for k in brackets if k not in charges and k[0] in played)
    res.n_no_label = sum(1 for k in charges if k not in brackets)
    res.games = tuple(res.per_game)
    return res


def common_universe(sources: dict[str, dict[Key, float]]) -> set[Key]:
    """Items every compared source priced. Comparing a source on items another one
    never saw measures coverage, not valuation, and hides cherry-picking; the items
    each source drops are reported instead."""
    keys: set[Key] | None = None
    for ch in sources.values():
        keys = set(ch) if keys is None else keys & set(ch)
    return keys or set()


# --------------------------------------------------------------------------- report

def _fmt_score(t: Tally) -> str:
    return f"{t.score:.3f}" if t.scoreable else "-"


def _headline(name: str, r: Result) -> str:
    t = r.total
    return (f"  {name:<22} SCORE {t.score:6.4f}   [lo {t.score:6.4f} .. hi {t.score_hi:6.4f}]\n"
            f"  {'':<22} proven {t.proven_income:>12,.0f} of best {t.best_possible:>12,.0f} EUR\n"
            f"  {'':<22} UNPROVABLE {t.n_unprovable:>4} items = "
            f"{t.unprovable_share:6.2%} of best possible"
            + ("   (uncertain, not wrong)" if t.n_unprovable else "")
            + f"\n  {'':<22} labelled items it did not price: {r.n_no_charge}"
              f"    items it priced with no label: {r.n_no_label}")


def report(scored: dict[str, Result], universe: int,
           specs: dict[str, str] | None = None) -> None:
    names = list(scored)
    print(f"labels: tools/thresholds.py --jsonl     scored universe: {universe} items "
          f"priced by every source")
    for name, spec in (specs or {}).items():
        if spec != name:
            print(f"  {name:<22} = {spec}")
    print()
    for n in names:
        print(_headline(n, scored[n]))
        print()

    games = sorted({g for r in scored.values() for g in r.per_game})
    print("  " + "".join(f"{n:>46}" for n in names))
    print(f"{'game':>4}" + "".join(
        f"{'items':>7}{'proven':>12}{'best':>12}{'score':>8}{'unprv':>7}" for _ in names))
    for g in games:
        line = f"{g:>4}"
        for n in names:
            t = scored[n].per_game.get(g, Tally())
            line += (f"{t.n_items:>7}{t.proven_income:>12,.0f}{t.best_possible:>12,.0f}"
                     f"{_fmt_score(t):>8}{t.n_unprovable:>7}")
        print(line)
    line = f"{'TOT':>4}"
    for n in names:
        t = scored[n].total
        line += (f"{t.n_items:>7}{t.proven_income:>12,.0f}{t.best_possible:>12,.0f}"
                 f"{_fmt_score(t):>8}{t.n_unprovable:>7}")
    print(line)

    print("\nDIAGNOSTICS (the three classes ARE under / over / indeterminate)")
    print(f"  {'':<22}{'under':>8}{'over':>8}{'indet':>8}{'no-floor':>10}"
          f"{'foregone EUR':>16}{'gap to best':>14}")
    for n in names:
        t = scored[n].total
        print(f"  {n:<22}{t.n_fair:>8}{t.n_fraud:>8}{t.n_unprovable:>8}{t.n_no_floor:>10}"
              f"{t.foregone:>16,.0f}{t.best_possible - t.proven_income:>14,.0f}")
    print("  under = a <= t_lo (proven fair, all 16 pay).  over = a > t_hi (proven "
          "fraud, nobody pays).")
    print("  no-floor = t_lo 0 with no fair charge ever seen: NOT a proven price of "
          "zero, and 0 in both\n           halves of the score. Counted here because "
          "it inflates 'over' without evidence of\n           a mispriced price.")
    print("  foregone = sum 16*(t_lo - a) over the unders ONLY. The gap to best also "
          "holds the\n           proven-fraud and unprovable items, so it is the "
          "larger and more honest number.")
    print(f"  knife edge: fair items charging within {1 - AT_FLOOR_FRACTION:.0%} of t_lo, "
          f"and the income riding on that cent:")
    for n in names:
        t = scored[n].total
        share = t.income_at_floor / t.proven_income if t.proven_income else 0.0
        print(f"  {n:<22}{t.n_at_floor:>8} items{t.income_at_floor:>16,.0f} EUR "
              f"= {share:.1%} of proven income. One cent more and each becomes "
              f"UNPROVABLE.")
    print("  score_classified (unprovable out of the denominator too): "
          + "  ".join(f"{n} {scored[n].total.score_classified:.4f}" for n in names)
          + "\n           reported for the audit, not for ranking: a candidate shrinks "
            "that denominator by\n           charging into the unprovable zone.")

    if len(names) == 2:
        a, b = names
        da = scored[a].total.score - scored[b].total.score
        dh = scored[a].total.score_hi - scored[b].total.score_hi
        print(f"\n  {a} minus {b}: score {da:+.4f}, score_hi {dh:+.4f}")
        if (da > 0) != (dh > 0):
            print("  THE BOUNDS DISAGREE. This comparison is not proven in either "
                  "direction --\n  one source moved charges into the unprovable zone. "
                  "Do not ship on it.")


# ------------------------------------------------------------------------ self-check

def demo() -> None:
    """Hand-computed rows. Fails loudly if the scoring or the parsing drifts."""
    brs = {
        (1, 1): Bracket(1, 1, 100.0, None, n_fair=2),      # floor 100, no ceiling
        (1, 2): Bracket(1, 2, 200.0, 300.0, n_fair=1, n_fraud=1),
        (1, 3): Bracket(1, 3, 0.0, 50.0, n_fair=0, n_fraud=1),   # no floor at all
        (2, 4): Bracket(2, 4, 500.0, None, n_fair=3),
    }
    charges = {(1, 1): 80.0, (1, 2): 400.0, (1, 3): 10.0, (2, 4): 600.0}
    # 1/1 a=80  <= 100        -> FAIR,       income 16*80=1280, foregone 16*20=320
    # 1/2 a=400 >  t_hi 300   -> FRAUD,      income 0
    # 1/3 a=10, no floor, 10 <= 50 -> UNPROVABLE, best 0
    # 2/4 a=600 >  floor 500, no ceiling -> UNPROVABLE, best 8000
    assert classify(80.0, brs[(1, 1)]) == FAIR
    assert classify(100.0, brs[(1, 1)]) == FAIR             # a == t_lo is still proven
    assert classify(400.0, brs[(1, 2)]) == FRAUD
    assert classify(300.0, brs[(1, 2)]) == UNPROVABLE        # a == t_hi proves nothing
    assert classify(10.0, brs[(1, 3)]) == UNPROVABLE
    assert classify(600.0, brs[(2, 4)]) == UNPROVABLE

    r = score(charges, brs)
    t = r.total
    assert (t.n_items, t.n_fair, t.n_fraud, t.n_unprovable) == (4, 1, 1, 2), t
    assert t.n_no_floor == 1, t.n_no_floor
    assert abs(t.proven_income - 1280.0) < 1e-9, t.proven_income
    assert abs(t.best_possible - 16 * 800.0) < 1e-9, t.best_possible
    assert abs(t.best_classified - 16 * 300.0) < 1e-9, t.best_classified
    assert abs(t.foregone - 320.0) < 1e-9, t.foregone
    # 80 is 80% of the floor 100, so it is NOT on the knife edge; 99.5 would be
    assert t.n_at_floor == 0, t.n_at_floor
    edge = score({(1, 1): 99.5}, brs).total
    assert edge.n_at_floor == 1 and abs(edge.income_at_floor - 16 * 99.5) < 1e-9
    assert abs(t.score - 1280.0 / 12800.0) < 1e-12, t.score
    # score_hi credits both unprovable charges as if fair: (1280 + 160 + 9600)/12800
    assert abs(t.score_hi - 11040.0 / 12800.0) < 1e-12, t.score_hi
    assert abs(t.score_classified - 1280.0 / 4800.0) < 1e-12, t.score_classified
    assert abs(t.unprovable_share - 8000.0 / 12800.0) < 1e-12, t.unprovable_share
    # the gap to best exceeds the foregone-EUR figure, always
    assert t.best_possible - t.proven_income > t.foregone
    assert r.per_game[1].n_items == 3 and r.per_game[2].n_items == 1
    # per-game tallies must sum to the total
    assert abs(sum(g.proven_income for g in r.per_game.values()) - t.proven_income) < 1e-9

    # coverage bookkeeping: a source that skips a labelled item is reported, never
    # silently dropped, because skipping the hard items is how a candidate cheats.
    partial = score({(1, 1): 80.0, (9, 9): 5.0}, brs)
    assert partial.n_no_charge == 2, partial.n_no_charge      # 1/2 and 1/3, game 1 played
    assert partial.n_no_label == 1, partial.n_no_label        # 9/9 has no bracket
    assert common_universe({"a": charges, "b": {(1, 1): 1.0}}) == {(1, 1)}

    # the event log's two tiers: LAST write wins, i.e. tier 2.
    lines = [
        json.dumps({"round": 7, "type": "item.belief",
                    "payload": {"idx": 1, "median": 1000.0, "sigma": 0.30}}),
        json.dumps({"round": 7, "type": "item.decided", "payload": {"idx": 1, "a": 11.0}}),
        json.dumps({"round": 7, "type": "item.decided", "payload": {"idx": 1, "a": 22.0}}),
        "not json at all",
        json.dumps({"round": 7, "type": "round.scheduled", "payload": {}}),
    ]
    assert charges_from_event_lines(lines) == {(7, 1): 22.0}
    a_belief = charges_from_event_lines(lines, from_belief=True)[(7, 1)]
    assert 0.0 < a_belief < 1000.0, a_belief   # Mills shading always charges below median
    assert abs(a_belief - decide(Belief(1000.0, 0.30), True)[0]) < 1e-12

    assert Tally().scoreable is False and Tally(best_possible=1.0).scoreable is True
    assert _fmt_score(Tally()) == "-"
    assert label_for("events") == "events"
    assert label_for("file:/a/b/cand_v3.jsonl") == "cand_v3"

    print("self-check OK: 4 hand-computed items, both tiers, coverage bookkeeping, "
          "and the decide() path")


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
    p.add_argument("--source", choices=("events", "file"), default="events")
    p.add_argument("--path", type=Path, default=None,
                   help="candidate JSONL, required with --source file")
    p.add_argument("--vs", default=None,
                   help="second source: 'events' or 'file:PATH'")
    p.add_argument("--games", default=None,
                   help="restrict to games, e.g. 20-31 or 4,8,15. Hold games out here "
                        "when the candidate was fit on these same labels.")
    p.add_argument("--events-from-belief", action="store_true",
                   help="re-derive our charge from the logged belief through decide() "
                        "instead of reading the submitted a")
    p.add_argument("--demo", action="store_true", help="run the self-check and exit")
    a = p.parse_args(argv)

    if a.demo:
        demo()
        return 0
    if a.source == "file" and a.path is None:
        p.error("--source file needs --path")

    first = "events" if a.source == "events" else f"file:{a.path}"
    specs = [first] + ([a.vs] if a.vs else [])
    if len(set(specs)) != len(specs):
        p.error("--vs must name a different source than --source")

    names: dict[str, str] = {}
    for spec in specs:
        name = label_for(spec)
        while name in names:
            name += "'"
        names[name] = spec

    keep_games = _games(a.games)
    try:
        brackets = load_brackets(keep_games)
        sources = {n: load_source(sp, from_belief=a.events_from_belief)
                   for n, sp in names.items()}
    except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(f"cannot score: {exc}")
        return 1

    if keep_games is not None:
        # Drop out-of-scope charges too, not just out-of-scope labels: otherwise
        # every held-out game shows up as "priced with no label" and the coverage
        # number stops meaning anything.
        sources = {n: {k: v for k, v in ch.items() if k[0] in keep_games}
                   for n, ch in sources.items()}
    keep = common_universe(sources)
    scored = {n: score({k: v for k, v in ch.items() if k in keep}, brackets)
              for n, ch in sources.items()}
    if not any(r.total.n_items for r in scored.values()):
        print("no labelled item is priced by every source -- nothing to score. "
              "Check --games and the candidate file's game numbering.")
        return 1
    report(scored, universe=sum(1 for k in keep if k in brackets), specs=names)
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 1:
        demo()                             # bare invocation self-checks, then reports
    raise SystemExit(main())
