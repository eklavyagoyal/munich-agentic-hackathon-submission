"""RETRIEVAL ANCHORS: proven price floors from games already played, per line item.

WHY THIS EXISTS

The price book carries no magnitude information on the population that holds the
money. Of the twelve largest proven floors in the store, EIGHT are quantity-1 "pcs"
lines that match no price-book keyword, so `pricebook.lookup` returns the identical
244.95 net per unit for every one of them while their true net-per-unit floors are
1,796 / 1,851 / 1,951 / 2,521 / 6,071 / 7,249 / 7,867 / 9,354. That is not a
calibration error to shade away, it is the absence of a signal, and no amount of
recalibrating a constant makes it carry magnitude.

The tournament, however, REUSES line templates. Measured on the store this module
reads (441 proven floors over 48 games): only 244 distinct (description, unit) pairs,
88 of which appear in more than one game and together cover 276 of the 441 rows, and
50.0% of rows have an EARLIER-GAME neighbour at lexical similarity >= 0.70. So for
half the population a price we have already PROVEN is sitting in the log, and nothing
was reading it.

This module retrieves it. Two sections per item, both expressed as NET FLOOR PER UNIT
(`u_lo = t_lo / (qty * (1 + vat_rate))`) because that is the exact quantity the
valuation prompt asks the model to output, and dividing out qty removes the quantity
variance that makes line-total anchors useless across cases:

  COMPARABLES  up to 3 nearest by lexical similarity of the line description against
               the WHOLE pool (not restricted to unit class), gated at sim >= 0.35,
               nearest first. They carry the LEVEL.
  LADDER       exactly 3 rungs at rank quantiles p0/p50/p100 of the item's own
               `pricebook.unit_class`, whole pool when that class is too thin. It
               carries the RANGE.

Both are load-bearing and the ablation says so (413 floored items, games >= 6, priced
from games < N only):

  sections selected         bracket  ceiling  best-anchor      what it is for
  comparables x3 only         0.284    0.511    0.173 dex      31.7% of items get NO
  comparables x6 only         0.443    0.642    0.141 dex      comparable at all, so
                                                              this cannot bracket
  ladder x3 only              0.920    0.956    0.317 dex      brackets, localises
                                                              badly
  comparables x3 + ladder x3  0.923    0.959    0.164 dex      <- what this module does

The comparables halve the localisation error the ladder alone achieves (0.317 -> 0.164
dex); the ladder supplies essentially all of the bracketing. Neither is optional.

WHAT IS EXACT AND WHAT IS A BOUND

EXACT: that a floor is a floor. `t_lo` comes from `tools/thresholds.py --jsonl` and
means a charge at that level was rejected by a reviewer and still PAID, which is only
possible in the fair column -- so the true fair value of THAT item was at least that
much. Nothing here is a model. The arithmetic from `t_lo` to `u_lo` is exact too,
given the printed quantity and the line's VAT rate.

A BOUND, and only ever DOWNWARD: `t_hi` is null on most rows, so a floor says nothing
about a ceiling. The pool is therefore systematically BELOW the truths it describes.
That is the profitable direction here -- undershooting `t` by half collects 0.50 per
euro charged while overshooting by half collects about 0.17 -- but it means this module
can only ever argue a price UP toward a number somebody already proved, never toward
the unknown real `t`. It is also why `bench_valuation`'s BEST POSSIBLE (built from
t_lo) understates, and every SCORE below overstates in absolute terms while remaining
a fair comparison between candidates.

MEASURED HERE, not copied from a design note. Labels from `tools/thresholds.py --jsonl`
and nowhere else (hand-rolled SQL has produced an inverted answer twice). Snapshot
2026-08-23T00:14Z: 645 labelled rows, 441 with a proven floor, 54 parsed cases.
Reproduce the retrieval half with `tools/anchor_candidate.py --report`.

RETRIEVAL, 413 items in games >= 6 with a proven floor, each priced from games < N:

  population                      items   bracket  ceiling  best-anchor   the book
  all floored items                 413     0.923    0.959    0.164 dex   0.428 dex
  tail    t_lo >= 1200               17     0.706    0.706    0.236 dex   0.721 dex
  mid     50 <= t_lo < 1200         340     0.956    0.971    0.143 dex   0.342 dex
  cheap   t_lo < 50                  56     0.786    0.964    0.273 dex   0.861 dex

  "bracket" = the truth's u_lo lies between the smallest and largest selected anchor.
  "ceiling" = the largest selected anchor is >= the truth; that is the direction that
  matters, given the asymmetry above. "best-anchor dex" = mean over items of the log10
  distance of the CLOSEST selected anchor. "the book" is the price book's own per-unit
  estimate on the same items, so anything above that column is worse than doing
  nothing. On the tail, where a third of all achievable income sits, the anchors cut
  the error 3.1x (0.236 vs 0.721 dex).

  68.3% of items got a gated comparable. Mean anchor-set width 2.83 dex. The set's log
  CENTROID -- where a model that quietly AVERAGES the six rows lands -- is 0.369 dex
  from truth: slightly better than the book's 0.428, but 2.2x worse than the best
  single anchor's 0.164. Averaging the block throws away most of what the block knows,
  which is why the prompt says "nearest description first" and labels the ladder a
  RANGE rather than a menu.

EUROS, through the sanctioned bench (`tools/bench_valuation.py`; charges derived by
`c2f.decision.quantile.decide` exactly as the tournament does; 645-item universe over
54 games; every game priced from games < N only):

  price book alone on this universe        SCORE 0.3120   proven   849,164
  nearest gated comparable REPLACES it     SCORE 0.4071   proven 1,107,859  +258,695
  anchor may only RAISE the book (FLOORS)  SCORE 0.4108   proven 1,118,108  +268,944
  anchor may only LOWER the book           SCORE 0.3082   proven   838,916   -10,248

  All of the value is UPWARD, which is what the label means. Both bounds move up on
  the floors variant (SCORE 0.3120 -> 0.4108, SCORE_HI 1.5613 -> 1.6931), so it is
  proven in bench_valuation's own sense, and the gain is 4.5x the knife-edge exposure
  the same report prints (59,625 EUR), so it is not rounding.

  THE GAIN IS ALL IN THE RECENT GAMES, because the pool IS the feature:
    games 2-31   (pool <= 30 games)   0.3562 -> 0.3671    +13,560 EUR
    games 32-54  (pool <= 53 games)   0.2678 -> 0.4450   +255,384 EUR
  This method cannot price a magnitude it has never seen. Game 10 item 3 -- charged
  199.25 against a proven floor of 7,225 gross -- is unfixable by any selection
  scheme, because at game 10 the largest floor in the pool was about 1,036 net per
  unit. The corollary is that every backtest of this feature UNDERSTATES what it does
  today, and that a measurement restricted to early games says almost nothing.

LEAKAGE. `load()` takes `before_game` as a REQUIRED keyword and filters inside, so no
caller can hold an unfiltered pool, and `select()` ASSERTS the cutoff on every row it
returns. This is not cosmetic. Same predictor, same universe, three pools:

  causal, games < N                 SCORE 0.4108   the only admissible setting
  games <= N, the item itself out   SCORE 0.4109   +0.0001: nothing. Same-case siblings
                                                   are lexically similar and
                                                   price-unrelated.
  games <= N, THE ITEM INCLUDED     SCORE 0.6241   +52% over causal, pure
                                                   self-prediction

The dangerous leak is IDENTITY, not the sibling, and the game filter subsumes the
identity filter -- which is why the game filter is the one that must be structurally
impossible to skip. `tests/test_anchors.py` has a test named for it.

This module is pure and offline: stdlib plus `c2f.core.models` and
`c2f.estimate.pricebook`. No network, no clock-dependent behaviour in selection, and
no exception escapes `load()` -- a missing or corrupt store degrades to no anchors,
which leaves the prompt byte-identical to a run without this feature.
"""
from __future__ import annotations

import json
import logging
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path

from c2f.core.models import LineItem
from c2f.estimate import pricebook

log = logging.getLogger("c2f")

# The gate IS the abstention. `fuzzy.py`'s post-mortem names why a lexical matcher
# fails in this codebase -- "lexical similarity to a taxonomy that lacks the answer
# does not abstain, it returns a confident wrong neighbour" -- and the gate is the
# answer to it. Swept on the sanctioned bench, floors mode, 1 comparable
# (`--gate X`, reproducible):
#     0.00  0.3858  but SCORE_HI 6.20: it charges wildly into the unprovable zone
#     0.20  0.3946
#     0.35  0.4108  <- the peak, and the tightest bound (SCORE_HI 1.69)
#     0.45  0.4049
#     0.55  0.4012
#     0.65  0.3694
# The gate is worth +0.025 SCORE (about +68,000 EUR) over ungated, and it collapses
# the unprovable exposure from SCORE_HI 6.20 to 1.69 -- which matters more than the
# score, because a candidate can inflate SCORE_HI without ever being right.
GATE = 0.35

# Comparables cap at 3, and the prompt tells the model the FIRST row is the closest,
# so it sees a ranked shortlist rather than a set to average. LEVEL accuracy peaks at
# ONE neighbour: the deterministic predictor, averaging its top k in log space,
# scores k=1 0.4108, k=2 0.3911, k=3 0.3910, k=5 0.3973, k=8 0.3967 (`--k-comp X`).
# Every k above 1 is worse, by about 0.02 SCORE = 50,000 EUR. Three rows is a
# compromise: the model needs to see that alternatives exist in order to reject the
# nearest one when the units or the scope disagree, and 3 is where the marginal row
# stops being informative. The DETERMINISTIC rule uses 1
# (`tools/anchor_candidate.K_COMP_PREDICT`); these are different jobs.
K_COMP = 3
# Ladder rungs. HONEST CAVEAT: unlike everything else here, this default is NOT the
# measured optimum. Retrieval metrics keep improving past 3 rungs --
#     rungs   bracket  ceiling  best-anchor
#         2     0.918    0.954    0.339 dex
#         3     0.923    0.959    0.164 dex
#         4     0.927    0.964    0.124 dex
#         6     0.944    0.978    0.089 dex
# -- so the design's claim that bracketing saturates at 3 does not reproduce on this
# store. 3 is kept because the only euro measurement available (the deterministic
# predictor) does not consult the ladder at all, so a larger ladder buys prompt
# tokens against an unmeasured benefit, and more rows is exactly the direction that
# risks the model averaging. Raising this is a real candidate for the model-in-the-
# loop bench, not a change to make on retrieval metrics alone.
K_LADDER = 3

# A stale store is a strict SUBSET of a fresh one, so it is safe to use; silence is
# not. Warn past this age and keep going.
STALE_S = 4 * 3600.0
# Bounded read. The store is one small line per proven floor; anything larger is a
# different file and must not be loaded into a round.
MAX_STORE_BYTES = 8 * 1024 * 1024
# Keep the NEWEST games when the pool grows past this. Selection over the full pool
# is cheap: measured worst case is 101 ms to select for all 31 items of game 46
# against a 348-row pool, i.e. ~3.3 ms per item, so this is a guard against a
# pathological file rather than a performance knob.
MAX_POOL = 2000

# Below this many seconds of round budget, do not render the block at all. Same
# threshold `c2f.runner.RoundConfig.min_tier2_budget_s` uses to skip tier 2: the
# anchor block is prompt-only, so dropping it is always safe.
MIN_BUDGET_S = 10.0

# Quantity floor for the per-unit conversion. `build_anchors.py` drops rows with a
# non-positive quantity, so on a well-formed store this never fires; it exists so a
# hand-edited row cannot produce inf.
QTY_FLOOR = 0.01

DEFAULT_STORE = Path(__file__).resolve().parents[2] / "data" / "anchors.jsonl"

# The FIXED framing paragraph. It goes in the SYSTEM string, which llm.py already
# marks with a cache_control breakpoint, so it is constant for the whole tournament
# and costs zero marginal prefill after the first call. Five framing rules are baked
# into these five sentences, each earned by a number (see the module docstring):
# "lower bound" never "price" (a floor invites "at least", a benchmark invites
# "about"); nearest-first, said out loud, because averaging destroys the level; the
# ladder labelled as a RANGE because its centroid is worse than the price book; no
# instruction to prefer the high end, because extra context makes models bolder
# rather than better and overshooting collects 3x less than undershooting; and
# explicit permission to go below a floor with a stated reason, which is a licence to
# be conservative rather than to inflate.
ANCHOR_SYSTEM_NOTE = """

PROVEN FLOORS on the fair value, from claims already settled in this tournament.
Each line is a LOWER BOUND: a charge at that level was rejected by a reviewer and
still paid, so the true fair value of THAT item was at least that much. A floor is
not a target and not a ceiling. Use it to place the order of magnitude; you may go
below a floor only when this item is genuinely smaller work than the one quoted."""

# worthless_accept_guard is ACTIVE and worth +22,715 exact, and it fires when a
# MAJORITY of ensemble samples price an item at zero. A block of proven floors is
# precisely the context that could talk the model out of a zero, so the zero is
# protected in words. This is a mitigation, not a proof: zero-vote recall with and
# without anchors is a promotion blocker, not a note.
ZERO_VOTE_NOTE = (
    "If this line is not covered by this policy, or not related to this damage, "
    "price it 0 regardless of any floor above — a floor is evidence about price, "
    "never about coverage."
)

_COMP_HEADER = "CLOSEST COMPARABLES (nearest description first) - net floor per unit:"
_NO_COMP = "  none close enough to quote"
_LADDER_HEADER_UNIT = (
    "FLOORS SEEN ON OTHER {unit} ITEMS, cheapest to dearest - the range this\n"
    "tournament actually pays, NOT a menu to pick the middle of:"
)
_LADDER_HEADER_ANY = (
    "FLOORS SEEN ACROSS ALL UNITS, cheapest to dearest - the range this\n"
    "tournament actually pays, NOT a menu to pick the middle of:"
)

# Short function words in both languages. Stripped from the token half of the
# similarity so "removal of the damaged laminate" and "laminate removal" are not
# separated by their glue.
_STOPWORDS = frozenset(
    """
    the and for with per and are was from into out off its
    der die das den dem des ein eine einer eines und von vom fur fuer für mit
    auf aus bei nach als bzw sowie oder zur zum inkl incl plus pro etc
    """.split()
)

_warned: set[str] = set()


def _warn_once(key: str, msg: str, *args: object) -> None:
    """One warning per distinct failure, not one per item. A per-item warning on a
    39-item case with 3 samples is 117 identical lines in the round log."""
    if key in _warned:
        return
    _warned.add(key)
    log.warning(msg, *args)


def enabled() -> bool:
    """C2F_ANCHORS, default OFF. The kill switch is this variable: reverting needs no
    code change. Note the ensemble's own default is already no-anchors, so this flag
    only gates whichever caller chooses to consult it."""
    return os.environ.get("C2F_ANCHORS", "0").strip().lower() not in ("", "0", "false", "no", "off")


# --------------------------------------------------------------------------- the row

@dataclass(frozen=True)
class Anchor:
    """One proven floor, carried as a NET FLOOR PER UNIT.

    `game` and `item` are bookkeeping and never reach a prompt: they exist so the
    leakage cutoff can be asserted on every row that is returned.
    """

    game: int
    item: int
    desc: str
    qty: float
    unit: str
    unit_class: str
    t_lo: float          # the proven floor as a GROSS LINE TOTAL, straight from thresholds.py
    u_lo: float          # ... divided by qty and VAT: NET per unit, what the model outputs
    n_fair: int


# ------------------------------------------------------------------------ VAT, once

def net_unit_floor(gross_line_floor: float, item: LineItem) -> float:
    """GROSS LINE TOTAL floor -> NET floor per unit. The ONLY place this divides.

    `t_lo` is a gross total for the whole line (that is what `charge_price` is), and
    the valuation prompt asks for a NET price per unit, so the conversion is
    `t_lo / (qty * (1 + vat))`. The rate comes from the LINE, not from a module
    constant, so a non-standard-VAT invoice is computed from its own rate instead of
    inheriting 19% -- the known gap in ASKS.md must not acquire a second home here.
    """
    if not math.isfinite(gross_line_floor) or gross_line_floor <= 0:
        return 0.0
    qty = max(float(item.qty), QTY_FLOOR)
    return gross_line_floor / (qty * (1.0 + float(item.vat_rate)))


def gross_line_total(net_per_unit: float, item: LineItem) -> float:
    """The exact inverse of `net_unit_floor`, so a retrieved anchor can be turned back
    into a belief about the same quantity the tournament scores."""
    if not math.isfinite(net_per_unit) or net_per_unit <= 0:
        return 0.0
    qty = max(float(item.qty), QTY_FLOOR)
    return net_per_unit * qty * (1.0 + float(item.vat_rate))


# ------------------------------------------------------------------------ similarity

def _norm(text: str) -> str:
    """Lowercase, non-alphanumerics collapsed to spaces, whitespace squeezed.

    `str.isalnum` is Unicode-aware on purpose: an ASCII-only character class turns
    "für" into "f r" and "m²" into "m", which is most of the German half of the
    invoice text.
    """
    flat = "".join(c if c.isalnum() else " " for c in text.lower())
    return " ".join(flat.split())


def _grams(text: str, n: int = 3) -> frozenset[str]:
    if len(text) < n:
        return frozenset([text]) if text else frozenset()
    return frozenset(text[i:i + n] for i in range(len(text) - n + 1))


def _tokens(text: str) -> frozenset[str]:
    return frozenset(t for t in text.split() if len(t) >= 3 and t not in _STOPWORDS)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def similarity(a: str, b: str) -> float:
    """0.6 * Jaccard(char 3-grams) + 0.4 * Jaccard(tokens >= 3 chars, stopwords out).

    Two halves because they fail differently: 3-grams survive inflection and
    compounding ("Laminatboden" vs "Laminat"), tokens survive reordering ("removal of
    laminate" vs "laminate removal"). The relationship to accuracy is a STEP at the
    gate, not a slope, which is why the score is never shown to the model.
    """
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    return 0.6 * _jaccard(_grams(na), _grams(nb)) + 0.4 * _jaccard(_tokens(na), _tokens(nb))


# ----------------------------------------------------------------------------- store

def _row_to_anchor(r: dict) -> Anchor | None:
    try:
        game, item = int(r["game"]), int(r["item"])
        qty, u_lo = float(r["qty"]), float(r["u_lo"])
    except (KeyError, TypeError, ValueError):
        return None
    if game <= 0 or item <= 0 or not math.isfinite(u_lo) or u_lo <= 0:
        return None
    desc = str(r.get("desc", ""))[:200]
    unit = str(r.get("unit", ""))[:24]
    return Anchor(
        game=game,
        item=item,
        desc=desc,
        qty=qty if math.isfinite(qty) and qty > 0 else 1.0,
        unit=unit,
        unit_class=str(r.get("unit_class", "") or pricebook.unit_class(unit))[:12],
        t_lo=float(r.get("t_lo", 0.0) or 0.0),
        u_lo=u_lo,
        n_fair=int(r.get("n_fair", 0) or 0),
    )


def load(path: Path | str = DEFAULT_STORE, *, before_game: int) -> tuple[Anchor, ...]:
    """Every proven floor from a game STRICTLY EARLIER than `before_game`.

    `before_game` is keyword-only and has NO default, and the filter runs inside this
    function, so no caller can end up holding an unfiltered pool. In production
    `before_game` is the round being played and every stored game is older, so the
    filter is a no-op; its whole purpose is that backtest, `bench_valuation` and
    `bench_all` replay games 2..N with the store that exists TODAY, which contains
    all of them. Take the game id from the case being priced -- never from the store's
    own maximum game, and never from the clock.

    Never raises. A missing, oversized, unreadable or malformed store logs once and
    returns (), which leaves the prompt byte-identical to a run without anchors.
    """
    p = Path(path)
    try:
        st = p.stat()
    except OSError as e:
        _warn_once(f"stat:{p}", "anchor store unavailable (%s) — valuing without anchors", e)
        return ()
    if st.st_size > MAX_STORE_BYTES:
        _warn_once(f"size:{p}", "anchor store is %d bytes (cap %d) — refusing to load it",
                   st.st_size, MAX_STORE_BYTES)
        return ()
    age = max(0.0, time.time() - st.st_mtime)
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        _warn_once(f"read:{p}", "anchor store unreadable (%s) — valuing without anchors", e)
        return ()

    rows: list[Anchor] = []
    bad = 0
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            r = json.loads(line)
        except ValueError:
            bad += 1
            continue
        a = _row_to_anchor(r) if isinstance(r, dict) else None
        if a is None:
            bad += 1
        elif a.game < before_game:
            rows.append(a)
    if bad:
        _warn_once(f"bad:{p}", "anchor store: %d malformed rows skipped", bad)
    if age > STALE_S:
        # A stale store is a strict SUBSET, which is safe. Say so anyway: a feature
        # whose input silently stopped updating is a feature that silently stops
        # paying, and nothing else in the pipeline would announce it.
        _warn_once(f"stale:{p}", "anchor store is %.0fs old (%d rows) — using it anyway",
                   age, len(rows))
    if len(rows) > MAX_POOL:
        rows.sort(key=lambda a: (a.game, a.item))
        rows = rows[-MAX_POOL:]
    return tuple(rows)


# ------------------------------------------------------------------------- selection

def _rank_quantiles(rows: list[Anchor], k: int) -> list[Anchor]:
    """`k` rungs at rank quantiles p0 .. p100 of u_lo.

    Rank spacing rather than log spacing, for a structural reason rather than a fitted
    one: the p0 and p100 rungs are the class MINIMUM and MAXIMUM, actual prices that
    were actually proven, so the range statement the prompt makes is true by
    construction. A log-uniform grid interpolates points nobody ever charged.
    """
    rows = sorted(rows, key=lambda a: (a.u_lo, a.game, a.item))
    if len(rows) <= k:
        return rows
    n = len(rows)
    if k == 1:
        return [rows[n - 1]]
    picks = sorted({round(i * (n - 1) / (k - 1)) for i in range(k)})
    return [rows[i] for i in picks]


def select(
    item: LineItem,
    pool: tuple[Anchor, ...],
    *,
    before_game: int,
    gate: float = GATE,
    k_comp: int = K_COMP,
    k_ladder: int = K_LADDER,
) -> tuple[list[Anchor], list[Anchor]]:
    """(comparables nearest-first, ladder cheapest-first) for one line item.

    Comparables range over the WHOLE pool on purpose, because the nearest description
    is frequently billed in a different unit than this line is: the same work appears
    as a per-m2 line in one invoice and a per-piece flat rate in another, and the
    words do not change. Restricting the lexical half by unit throws that away and
    also starves the tail, where the pool is thinnest to begin with.

    The ladder is the item's own `pricebook.unit_class`, and falls back to the whole
    pool only when that class is too thin or unknown. The fallback is DEGENERATE and
    deliberately not the default: a unit-blind span of the whole pool brackets almost
    everything, because a set spanning nearly three decades contains something near
    any truth by construction. It is a statement about the range of the tournament,
    not about this item, and it is kept for the case where we genuinely have nothing
    item-specific to say.

    `before_game` is required so the cutoff can be ASSERTED, not merely trusted. The
    assertions are assertions and not filters deliberately: if one can fire, a caller
    bypassed `load()`, and the number that comes out of a bypassed loader (0.6241
    against the causal 0.4108) is pure self-prediction.
    """
    if not pool:
        return [], []

    scored: list[tuple[float, int, int, Anchor]] = []
    for a in pool:
        s = similarity(item.description, a.desc)
        if s >= gate:
            scored.append((-s, a.game, a.item, a))
    scored.sort(key=lambda t: (t[0], t[1], t[2]))
    comps = [t[3] for t in scored[:max(0, k_comp)]]

    cls = pricebook.unit_class(item.unit)
    same = [a for a in pool if cls and a.unit_class == cls]
    rungs_from = same if len(same) >= k_ladder else list(pool)
    taken = {(a.game, a.item) for a in comps}
    ladder = _rank_quantiles([a for a in rungs_from if (a.game, a.item) not in taken], k_ladder)

    for a in comps + ladder:
        assert a.game < before_game, (
            f"LEAKAGE: anchor from game {a.game} selected for game {before_game}"
        )
        assert not (a.game == before_game and a.item == item.idx), (
            f"LEAKAGE: item {before_game}/{item.idx} selected as its own anchor"
        )
    return comps, ladder


# ------------------------------------------------------------------------- rendering

def _row(a: Anchor) -> str:
    return f"  {a.qty:>6g} {(a.unit_class or a.unit):<8} >= {a.u_lo:>8,.0f}  {a.desc[:50]}"


def render(comps: list[Anchor], ladder: list[Anchor], unit_class: str) -> str:
    """The two labelled sections plus the zero-vote sentence. "" when there is nothing.

    Carries no similarity score (it is an internal ranking quantity with no units the
    model can calibrate, and showing it invites weighting 0.58 twice as heavily as
    0.29 when the measured relationship is a step at the gate), and no game or item
    identifiers (noise to the model, and our own bookkeeping leaking into a prompt
    that is retained provider-side by default -- see `llm.store_logs`).
    """
    if not comps and not ladder:
        return ""
    out = [_COMP_HEADER]
    out.extend(_row(a) for a in comps) if comps else out.append(_NO_COMP)
    if ladder:
        out.append(
            _LADDER_HEADER_UNIT.format(unit=unit_class.upper()) if unit_class
            else _LADDER_HEADER_ANY
        )
        out.extend(_row(a) for a in ladder)
    out.append(ZERO_VOTE_NOTE)
    return "\n".join(out)


def block(
    item: LineItem,
    pool: tuple[Anchor, ...],
    *,
    before_game: int,
    budget_s: float | None = None,
) -> str:
    """select + render in one call. "" whenever anchors must not be spent.

    `budget_s` is the round's REMAINING seconds. Below `MIN_BUDGET_S` the block is
    dropped and the drop is logged: the anchors are prompt-only, so losing them costs
    accuracy on one round, while blowing the tier-2 deadline costs the whole tier.
    """
    if not pool:
        return ""
    if budget_s is not None and budget_s < MIN_BUDGET_S:
        _warn_once("budget", "anchor block skipped: %.1fs of round budget left", budget_s)
        return ""
    comps, ladder = select(item, pool, before_game=before_game)
    return render(comps, ladder, pricebook.unit_class(item.unit))


# ------------------------------------------------------------------------ self-check

def demo() -> None:
    """Assert-based self-check. Fails loudly if selection, the gate, the per-unit
    conversion, the rendering discipline or the leakage cutoff breaks."""
    def anc(game: int, item: int, desc: str, u: float, unit: str = "stk",
            qty: float = 1.0) -> Anchor:
        return Anchor(game=game, item=item, desc=desc, qty=qty, unit=unit,
                      unit_class=pricebook.unit_class(unit), t_lo=u * qty * 1.19,
                      u_lo=u, n_fair=1)

    # --- VAT and quantity live in one function, and it reads the LINE's rate -------
    it = LineItem(idx=1, description="remove laminate", qty=20.0, unit="m2")
    assert abs(net_unit_floor(238.0, it) - 238.0 / (20.0 * 1.19)) < 1e-9
    assert abs(gross_line_total(net_unit_floor(238.0, it), it) - 238.0) < 1e-9
    reduced = LineItem(idx=1, description="x", qty=2.0, unit="stk", vat_rate=0.07)
    assert abs(net_unit_floor(214.0, reduced) - 214.0 / (2.0 * 1.07)) < 1e-9
    assert net_unit_floor(214.0, reduced) != net_unit_floor(214.0,
        LineItem(idx=1, description="x", qty=2.0, unit="stk")), "vat_rate is ignored"
    assert net_unit_floor(-1.0, it) == 0.0 and gross_line_total(0.0, it) == 0.0

    # --- similarity: identical > near > unrelated, and it is symmetric -------------
    assert similarity("Lift click-vinyl flooring", "Lift click-vinyl flooring") == 1.0
    near = similarity("Lift click-vinyl flooring", "Removal of click-vinyl flooring")
    far = similarity("Lift click-vinyl flooring", "Tow truck recovery of the vehicle")
    assert 0.35 < near < 1.0, near
    assert far < 0.15, far
    assert abs(similarity("a b c", "c b a") - similarity("c b a", "a b c")) < 1e-12
    assert similarity("", "anything") == 0.0
    # Unicode survives normalisation: an ASCII class would shred the German half.
    assert similarity("Fußleiste montieren", "Fußleiste montieren") == 1.0

    # --- selection: gate abstains, ladder still fires ------------------------------
    pool = tuple(
        [anc(1, 1, "Lift damp click-vinyl, upstairs hall", 12.0, "m2", 18.0),
         anc(2, 1, "Removal of damp click vinyl, hallway", 14.0, "m2", 20.0),
         anc(3, 1, "Tow truck recovery", 180.0),
         anc(4, 1, "Flat screen television replacement", 900.0),
         anc(5, 1, "HDMI cable", 12.0),
         anc(6, 1, "Air conditioning split unit", 2400.0)]
    )
    q = LineItem(idx=7, description="Lifting of damp click vinyl, hallway",
                 qty=16.0, unit="m2")
    comps, ladder = select(q, pool, before_game=9)
    assert [a.game for a in comps] == [1, 2] or [a.game for a in comps] == [2, 1], comps
    assert len(ladder) == K_LADDER, ladder
    assert [a.u_lo for a in ladder] == sorted(a.u_lo for a in ladder)
    # m2 has only 2 rows, below K_LADDER, so the ladder falls back to the whole pool
    # and must reach the dear end -- that top rung is what brackets the tail.
    assert max(a.u_lo for a in ladder) == 2400.0, ladder
    # ... and the ladder never repeats a comparable.
    assert not ({(a.game, a.item) for a in comps} & {(a.game, a.item) for a in ladder})

    unrelated = LineItem(idx=1, description="Scaffolding hire for the gable end",
                         qty=1.0, unit="stk")
    comps2, ladder2 = select(unrelated, pool, before_game=9)
    assert comps2 == [], comps2                      # gate abstained
    assert len(ladder2) == K_LADDER, ladder2          # ... and the range still arrives
    assert {a.unit_class for a in ladder2} == {"stk"}, ladder2

    # --- the leakage cutoff is an assertion, not a hope ----------------------------
    try:
        select(q, pool, before_game=3)               # pool holds games 3..6
    except AssertionError as e:
        assert "LEAKAGE" in str(e)
    else:                                            # pragma: no cover
        raise AssertionError("select() accepted an anchor from a later game")

    # --- rendering: no scores, no ids, no policy or damage text --------------------
    txt = render(comps, ladder, "m2")
    assert _COMP_HEADER in txt and "FLOORS SEEN ON OTHER M2 ITEMS" in txt
    assert "price it 0" in txt, "the zero vote must stay protected"
    for a in comps + ladder:
        assert f"game {a.game}" not in txt and f"[{a.item}]" not in txt
    assert "0.6" not in txt.split("\n")[0]           # no similarity score in the header
    assert render([], [], "m2") == ""
    empty = render([], ladder, "")
    assert _NO_COMP in empty and "ACROSS ALL UNITS" in empty

    # --- block(): budget guard and the empty-pool short circuit -------------------
    assert block(q, (), before_game=9) == ""
    assert block(q, pool, before_game=9, budget_s=MIN_BUDGET_S - 0.1) == ""
    assert block(q, pool, before_game=9, budget_s=MIN_BUDGET_S + 0.1) != ""

    # --- load(): never raises, and filters inside ---------------------------------
    assert load(Path("/nonexistent/anchors.jsonl"), before_game=5) == ()

    print("anchors self-check OK: VAT once, gate abstains, ladder holds the range, "
          "leakage asserted, prompt carries no ids")


if __name__ == "__main__":
    demo()
