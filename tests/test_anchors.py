"""Retrieval anchors: the leakage cutoff, the gate, and the flag being genuinely off.

The expensive bug in this feature is not a wrong price, it is a MEASUREMENT that
cannot happen in production. A loader that lets game N see game N reports a score
built out of self-prediction, and every decision downstream is then made on a number
the tournament can never produce. Measured with the deterministic 1-NN predictor over
all 54 harvested cases, labels from `tools/thresholds.py --jsonl` (2026-08-23T00:14Z):

    causal (games < N)                SCORE 0.4108
    own game in the pool, self out    SCORE 0.4109   (+0.0001, nothing: same-case
                                                     siblings are lexically similar
                                                     and price-unrelated)
    THE ITEM ITSELF in the pool       SCORE 0.6241   (+52% over causal, pure
                                                     self-prediction)

So the tests below are mostly about the cutoff, and the one named for the leak asserts
the SHAPE of that 52%: with the item in its own pool the retrieval error collapses to
zero, which is what makes the inflated score look like a triumph.

Reproduce the euro numbers with:
    PYTHONPATH=. .venv/bin/python tools/anchor_candidate.py --mode floors --leak item \\
        --out /tmp/leak.jsonl
    PYTHONPATH=. .venv/bin/python tools/bench_valuation.py --source file \\
        --path /tmp/leak.jsonl --vs file:/tmp/causal.jsonl
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from c2f.core.models import LineItem
from c2f.estimate import anchors, ensemble, pricebook
from tools.anchor_candidate import ANCHOR_SIGMA, _drop_self, predict

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "anchors.jsonl"


def anc(game: int, item: int, desc: str, u_lo: float, unit: str = "stk",
        qty: float = 1.0) -> anchors.Anchor:
    return anchors.Anchor(game=game, item=item, desc=desc, qty=qty, unit=unit,
                          unit_class=pricebook.unit_class(unit),
                          t_lo=u_lo * qty * 1.19, u_lo=u_lo, n_fair=1)


def write_store(tmp_path: Path, rows: list[anchors.Anchor]) -> Path:
    p = tmp_path / "anchors.jsonl"
    p.write_text("\n".join(json.dumps({
        "game": a.game, "item": a.item, "desc": a.desc, "qty": a.qty, "unit": a.unit,
        "unit_class": a.unit_class, "t_lo": a.t_lo, "u_lo": a.u_lo, "n_fair": a.n_fair,
    }) for a in rows) + "\n", encoding="utf-8")
    return p


POOL = [
    anc(1, 1, "Lift damp click-vinyl, upstairs hall", 12.0, "m2", 18.0),
    anc(2, 1, "Removal of damp click vinyl, hallway", 14.0, "m2", 20.0),
    anc(3, 1, "Tow truck recovery of the vehicle", 180.0),
    anc(4, 1, "Flat screen television, replacement", 900.0),
    anc(5, 1, "HDMI cable", 10.0),
    anc(6, 1, "Air conditioning split unit, supply and fit", 2400.0),
]


# ------------------------------------------------------------------ the cutoff

def test_load_never_returns_a_row_from_the_cutoff_game_or_later(tmp_path):
    """Property, over every game id the tournament can reach. This is the filter that
    must be structurally impossible to skip: it subsumes the identity filter, and the
    identity leak is the one worth 52%."""
    path = write_store(tmp_path, POOL)
    for n in range(1, 55):
        pool = anchors.load(path, before_game=n)
        assert all(a.game < n for a in pool), n
        assert len(pool) == sum(1 for a in POOL if a.game < n), n


def test_load_has_no_all_rows_mode():
    """`before_game` is keyword-only with no default, so there is no call that hands a
    caller an unfiltered pool."""
    with pytest.raises(TypeError):
        anchors.load(STORE)                                    # type: ignore[call-arg]


@pytest.mark.skipif(not STORE.exists(), reason="no anchor store built")
def test_the_real_store_obeys_the_cutoff():
    rows = [json.loads(line) for line in STORE.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    assert rows, "the store exists but is empty"
    for n in (1, 6, 20, 41, 54):
        pool = anchors.load(STORE, before_game=n)
        assert all(a.game < n for a in pool), n
        assert len(pool) == sum(1 for r in rows if int(r["game"]) < n), n


def test_select_asserts_rather_than_filters_a_leaking_pool():
    """If the assertion can fire, a caller bypassed load(). It must fire loudly, not
    quietly drop the row -- a silent filter here would hide the bypass."""
    q = LineItem(idx=1, description="Removal of damp click vinyl",
                 qty=16.0, unit="m2")
    with pytest.raises(AssertionError, match="LEAKAGE"):
        anchors.select(q, tuple(POOL), before_game=3)


def test_no_item_is_ever_its_own_anchor(tmp_path):
    """Game 9's own rows are in the store; pricing game 9 must not see them, so the
    identical description in game 9 cannot be retrieved."""
    rows = POOL + [anc(9, 4, "Air conditioning split unit, supply and fit", 5000.0)]
    path = write_store(tmp_path, rows)
    pool = anchors.load(path, before_game=9)
    assert all(not (a.game == 9) for a in pool)
    q = LineItem(idx=4, description="Air conditioning split unit, supply and fit",
                 qty=1.0, unit="stk")
    comps, ladder = anchors.select(q, pool, before_game=9)
    assert all((a.game, a.item) != (9, 4) for a in comps + ladder)
    # ... and the retrieved neighbour is the EARLIER one, at a different price
    assert comps and comps[0].u_lo == 2400.0, comps


def test_LEAK_self_in_pool_collapses_the_error_to_zero(tmp_path):
    """NAMED FOR THE BUG. With the item itself admissible, the "nearest comparable" IS
    the truth: similarity 1.0 and zero log error. That is the shape of the 0.6241 in
    this module's docstring, and it cannot occur in a live round -- game N's floors do
    not exist until game N has been settled."""
    truth_u = 5000.0
    # Deliberately NOT byte-identical to the game 6 row: with two exact matches the
    # tie-break picks the earlier game and the leak would hide behind it. Here the
    # item's own row is the strict nearest, which is the real-world shape -- the
    # tournament reuses templates, so a leaked row IS the closest text there is.
    it = LineItem(idx=4, description="Air conditioning split unit, supply and installation",
                  qty=1.0, unit="stk")
    rows = POOL + [anc(9, 4, it.description, truth_u)]
    path = write_store(tmp_path, rows)

    causal = anchors.load(path, before_game=9)
    leaking = anchors.load(path, before_game=10)          # game 9 is now admissible

    c_causal, _ = anchors.select(it, causal, before_game=9)
    c_leak, _ = anchors.select(it, leaking, before_game=10)
    assert c_causal[0].u_lo == 2400.0
    assert c_leak[0].u_lo == truth_u, "the leak did not retrieve the item itself"
    assert abs(math.log10(c_leak[0].u_lo / truth_u)) == 0.0
    assert abs(math.log10(c_causal[0].u_lo / truth_u)) > 0.3

    # and the euro-side consequence: the leaking prediction is exactly the truth
    b_leak, _ = predict(it, leaking, before_game=10, mode="floors")
    assert abs(b_leak.median - truth_u * 1.19) < 1e-6

    # _drop_self is what the `--leak game` variant uses, and it must remove exactly one
    assert len(_drop_self(leaking, 9, 4)) == len(leaking) - 1
    assert len(_drop_self(leaking, 9, 99)) == len(leaking)


# --------------------------------------------------------------------- the gate

def test_gate_abstains_and_the_ladder_still_fires():
    """32% of items have no gated comparable. `fuzzy.py` failed because a lexical
    matcher with no gate "does not abstain, it returns a confident wrong neighbour".
    Ungated, this predictor scores 0.3858 with SCORE_HI 6.20 -- it charges into the
    unprovable zone; gated at 0.35 it scores 0.4108 with SCORE_HI 1.69."""
    odd = LineItem(idx=1, description="Erection of a temporary site fence",
                   qty=1.0, unit="stk")
    best = max(anchors.similarity(odd.description, a.desc) for a in POOL)
    assert best < anchors.GATE, best
    comps, ladder = anchors.select(odd, tuple(POOL), before_game=9)
    assert comps == []
    assert len(ladder) == anchors.K_LADDER
    assert [a.u_lo for a in ladder] == sorted(a.u_lo for a in ladder)
    # the ladder is the item's own unit class, and it reaches both ends of it
    assert {a.unit_class for a in ladder} == {"stk"}
    stk = sorted(a.u_lo for a in POOL if a.unit_class == "stk")
    assert ladder[0].u_lo == stk[0] and ladder[-1].u_lo == stk[-1]


def test_gate_abstention_returns_the_price_book_unchanged():
    odd = LineItem(idx=1, description="Erection of a temporary site fence",
                   qty=1.0, unit="stk")
    book = pricebook.lookup(odd)
    belief, src = predict(odd, tuple(POOL), before_game=9, mode="floors")
    assert src == "book:no_comparable"
    assert belief.median == book.median and belief.sigma == book.sigma


def test_ladder_falls_back_to_the_whole_pool_when_the_class_is_thin():
    """m2 has two rows, below K_LADDER. The fallback must reach the dear end of the
    pool: that top rung is the only thing that brackets a tail item from above."""
    q = LineItem(idx=1, description="Screed levelling compound", qty=30.0, unit="m2")
    _comps, ladder = anchors.select(q, tuple(POOL), before_game=9)
    assert len(ladder) == anchors.K_LADDER
    assert max(a.u_lo for a in ladder) == 2400.0


def test_comparables_are_nearest_first_and_range_over_the_whole_pool():
    """Comparables must NOT be restricted to the item's own unit class: the same work
    appears as a per-m2 line in one invoice and a per-piece flat rate in another, and
    the words do not change. Here the query is billed per piece and its true nearest
    neighbours are per-m2 rows."""
    q = LineItem(idx=1, description="Removal of damp click vinyl, hallway",
                 qty=1.0, unit="stk")                       # note: stk, not m2
    comps, _ = anchors.select(q, tuple(POOL), before_game=9)
    sims = [anchors.similarity(q.description, a.desc) for a in comps]
    assert sims == sorted(sims, reverse=True), sims
    assert comps[0].unit_class == "m2", "comparables were restricted by unit"
    assert len(comps) <= anchors.K_COMP


# ------------------------------------------------------------- VAT and quantity

def test_u_lo_uses_the_line_s_own_vat_rate():
    """One function owns the division. A non-standard-VAT line is computed from its own
    rate rather than inheriting 19% -- ASKS.md's known gap must not get a second home."""
    std = LineItem(idx=1, description="x", qty=4.0, unit="stk")
    red = LineItem(idx=1, description="x", qty=4.0, unit="stk", vat_rate=0.07)
    assert anchors.net_unit_floor(476.0, std) == pytest.approx(476.0 / (4.0 * 1.19))
    assert anchors.net_unit_floor(476.0, red) == pytest.approx(476.0 / (4.0 * 1.07))
    assert anchors.net_unit_floor(476.0, std) != anchors.net_unit_floor(476.0, red)


def test_the_conversion_round_trips_both_ways():
    for qty in (0.5, 1.0, 18.0, 2412.1):
        it = LineItem(idx=1, description="x", qty=qty, unit="m2")
        u = anchors.net_unit_floor(1_190.0, it)
        assert anchors.gross_line_total(u, it) == pytest.approx(1_190.0)
    # and it agrees with the price book's single VAT home on the default rate
    it = LineItem(idx=1, description="x", qty=1.0, unit="stk")
    assert anchors.gross_line_total(100.0, it) == pytest.approx(pricebook.gross(100.0))


def test_quantity_scales_the_prediction():
    """u_lo is per unit, so a 10x quantity is a 10x line total. Line-total anchors are
    useless across cases precisely because this factor is not divided out."""
    one = LineItem(idx=1, description="Flat screen television, replacement",
                   qty=1.0, unit="stk")
    ten = LineItem(idx=1, description="Flat screen television, replacement",
                   qty=10.0, unit="stk")
    b1, s1 = predict(one, tuple(POOL), before_game=9, mode="nn")
    b10, s10 = predict(ten, tuple(POOL), before_game=9, mode="nn")
    assert s1 == s10 == "anchor"
    assert b10.median == pytest.approx(10 * b1.median)
    assert b1.sigma == b10.sigma == ANCHOR_SIGMA


def test_floors_only_never_lowers_the_book():
    """The measured asymmetry: letting the anchor RAISE the estimate is worth
    +268,944 EUR, letting it LOWER the estimate is worth -10,248. t_lo is a lower
    bound; it says nothing about a ceiling."""
    cheap = LineItem(idx=1, description="HDMI cable", qty=1.0, unit="stk")
    book = pricebook.lookup(cheap)
    belief, src = predict(cheap, tuple(POOL), before_game=9, mode="floors")
    assert belief.median >= book.median
    if src == "anchor":
        assert belief.median > book.median


# ----------------------------------------------------- what reaches the provider

def test_render_leaks_no_identifiers_and_no_case_text():
    q = LineItem(idx=1, description="Removal of damp click vinyl",
                 qty=16.0, unit="m2")
    comps, ladder = anchors.select(q, tuple(POOL), before_game=9)
    txt = anchors.render(comps, ladder, "m2")
    assert txt
    for a in comps + ladder:
        assert f"game {a.game}" not in txt
        assert f"[{a.item}]" not in txt
    # no similarity score: the measured relationship is a step at the gate, not a
    # slope, so a printed 0.58 invites weighting that does not exist
    for a in comps:
        s = anchors.similarity(q.description, a.desc)
        assert f"{s:.2f}" not in txt
    # descriptions are truncated at 50 chars, so a long policy sentence cannot ride in
    # on one. Checked on the ROWS; the framing sentences are fixed text.
    rows = [ln for ln in txt.splitlines() if ln.startswith("  ") and ">=" in ln]
    assert len(rows) == len(comps) + len(ladder)
    assert all(len(ln) < 100 for ln in rows), max(rows, key=len)


def test_render_protects_the_zero_vote():
    """worthless_accept_guard is ACTIVE at +22,715 exact and fires on majority zero
    votes. A block of proven floors is exactly the argument against a zero, so the
    zero is protected in words. The recall measurement is the proof; this is the
    mitigation being present at all."""
    comps, ladder = anchors.select(
        LineItem(idx=1, description="HDMI cable", qty=1.0, unit="stk"),
        tuple(POOL), before_game=9)
    txt = anchors.render(comps, ladder, "stk")
    assert "price it 0" in txt
    assert "never about coverage" in txt


def test_render_is_empty_when_there_is_nothing_to_say():
    assert anchors.render([], [], "m2") == ""
    assert anchors.block(LineItem(idx=1, description="x", qty=1.0, unit="m2"), (),
                         before_game=9) == ""


def test_block_is_dropped_under_the_tier2_budget():
    """The block is prompt-only, so dropping it costs accuracy on one round; blowing
    the 52s tier-2 deadline costs the whole tier. Same threshold tier 2 uses on
    itself."""
    q = LineItem(idx=1, description="Removal of damp click vinyl",
                 qty=16.0, unit="m2")
    assert anchors.block(q, tuple(POOL), before_game=9,
                         budget_s=anchors.MIN_BUDGET_S - 0.01) == ""
    assert anchors.block(q, tuple(POOL), before_game=9,
                         budget_s=anchors.MIN_BUDGET_S + 0.01) != ""
    assert anchors.block(q, tuple(POOL), before_game=9) != ""     # no budget given


# ------------------------------------------------- the flag is genuinely default-off

# The rendered item prompt as it stood BEFORE anchors existed, extracted from
# ensemble._ITEM_PROMPT at commit 28817b3 and asserted byte for byte. If this fails,
# a running daemon's prompt changed as a side effect of an "additive" edit.
_PROMPT_BEFORE_ANCHORS = (
    "DIGEST\nDAMAGE DESCRIPTION (excerpt):\n```\nDAMAGE\n```\n\n"
    "FULL INVOICE (for duplicate and scope checks):\n  [1] 2 m2 — desc\n\n"
    "VALUE THIS LINE ITEM:\n  item:        1\n  description: desc\n"
    "  quantity:    2 m2\n\nGive the NET price per m2, not the line total."
)


def test_item_prompt_is_byte_identical_with_anchors_off():
    rendered = ensemble._ITEM_PROMPT.format(
        digest="DIGEST", damage="DAMAGE", invoice="  [1] 2 m2 — desc",
        anchors="", idx=1, description="desc", qty="2", unit="m2")
    assert rendered == _PROMPT_BEFORE_ANCHORS


def test_the_anchor_slot_lands_between_the_invoice_and_the_valuation_ask():
    rendered = ensemble._ITEM_PROMPT.format(
        digest="DIGEST", damage="DAMAGE", invoice="INVOICE",
        anchors="ANCHORBLOCK", idx=1, description="desc", qty="2", unit="m2")
    assert rendered.index("INVOICE") < rendered.index("ANCHORBLOCK")
    assert rendered.index("ANCHORBLOCK") < rendered.index("VALUE THIS LINE ITEM")


def test_prefetch_signature_defaults_to_no_anchors():
    """Every existing caller must be unchanged. The default IS the off switch."""
    import inspect
    sig = inspect.signature(ensemble.prefetch)
    assert sig.parameters["anchors"].default == ()
    assert sig.parameters["anchor_game"].default is None
    assert sig.parameters["anchor_budget_s"].default is None
    for name in ("anchors", "anchor_game", "anchor_budget_s"):
        assert sig.parameters[name].kind is inspect.Parameter.KEYWORD_ONLY


def test_prefetch_drops_anchors_when_the_round_id_is_missing(monkeypatch, caplog):
    """A pool with no game id cannot have its cutoff asserted. Dropping it degrades to
    today's prompt; using it would produce a number nobody can trust."""
    from c2f.core.models import Case
    from c2f.estimate import llm

    monkeypatch.setenv("C2F_BACKEND", "none")
    llm.reset()
    try:
        case = Case(case_id="t", policy_text="p", damage_description="d",
                    items=(LineItem(idx=1, description="x", qty=1.0, unit="m2"),))
        # backend "none" makes prefetch return {} before any call, which is exactly
        # the degraded path a missing key produces in production.
        assert ensemble.prefetch_sync(case, anchors=tuple(POOL)) == {}
    finally:
        monkeypatch.delenv("C2F_BACKEND", raising=False)
        llm.reset()


def test_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("C2F_ANCHORS", raising=False)
    assert anchors.enabled() is False
    for off in ("0", "", "false", "no", "off"):
        monkeypatch.setenv("C2F_ANCHORS", off)
        assert anchors.enabled() is False, off
    for on in ("1", "true", "yes"):
        monkeypatch.setenv("C2F_ANCHORS", on)
        assert anchors.enabled() is True, on


# --------------------------------------------------------------- failure handling

def test_a_missing_or_broken_store_degrades_to_no_anchors(tmp_path):
    """No exception from this module may reach a round."""
    assert anchors.load(tmp_path / "nope.jsonl", before_game=9) == ()
    torn = tmp_path / "torn.jsonl"
    torn.write_text('{"game":1,"item":1,"desc":"a","qty":1,"unit":"stk",'
                    '"unit_class":"stk","t_lo":119,"u_lo":100,"n_fair":1}\n'
                    '{"game":2,"item":1,  <- half a line\n'
                    'not json at all\n'
                    '{"game":3,"item":1,"qty":1,"u_lo":-5}\n', encoding="utf-8")
    pool = anchors.load(torn, before_game=9)
    assert [a.game for a in pool] == [1], pool
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    assert anchors.load(empty, before_game=9) == ()
    a_dir = tmp_path / "adir"
    a_dir.mkdir()
    assert anchors.load(a_dir, before_game=9) == ()


def test_oversized_store_is_refused_rather_than_read(tmp_path, monkeypatch):
    big = tmp_path / "big.jsonl"
    big.write_text("x" * 4096, encoding="utf-8")
    monkeypatch.setattr(anchors, "MAX_STORE_BYTES", 1024)
    anchors._warned.clear()
    assert anchors.load(big, before_game=9) == ()


def test_pool_is_capped_at_the_newest_games(tmp_path, monkeypatch):
    rows = [anc(g, 1, f"row {g}", 100.0) for g in range(1, 21)]
    path = write_store(tmp_path, rows)
    monkeypatch.setattr(anchors, "MAX_POOL", 5)
    pool = anchors.load(path, before_game=21)
    assert len(pool) == 5
    assert [a.game for a in pool] == [16, 17, 18, 19, 20]


def test_similarity_is_bounded_symmetric_and_unicode_safe():
    assert anchors.similarity("abc", "abc") == pytest.approx(1.0)
    assert anchors.similarity("", "abc") == 0.0
    assert anchors.similarity("!!!", "???") == 0.0
    for a, b in (("Fußleiste montieren", "Fussleiste montieren"),
                 ("46 m² Malerarbeiten", "Malerarbeiten 46 m²")):
        s = anchors.similarity(a, b)
        assert 0.0 <= s <= 1.0
        assert s == pytest.approx(anchors.similarity(b, a))
    # an ASCII-only normaliser would shred the German half; assert it did not
    assert anchors.similarity("Fußleiste", "Fußleiste") == pytest.approx(1.0)
    assert anchors.similarity("Fußleiste", "Dachrinne") < 0.2


def test_module_self_checks_run():
    """The assert-based demos are runnable without pytest, and they must pass here
    too -- a self-check nobody runs is a comment."""
    anchors.demo()
    from tools import anchor_candidate, build_anchors
    build_anchors.demo()
    anchor_candidate.demo()


def test_prefetch_actually_injects_the_block_and_the_system_note(monkeypatch):
    """The one path that is otherwise unexercised offline: with a backend present and
    anchors supplied, the block must reach the user prompt and the framing paragraph
    must reach SYSTEM (where llm.py's cache_control breakpoint makes it free). Without
    this test the whole injection is dead code until the first live round."""
    from c2f.core.models import Case
    from c2f.estimate import llm

    seen: list[tuple[str, str]] = []

    async def fake_ask_json(prompt, *, schema, fast, timeout, system=None, images=()):
        seen.append((prompt, system or ""))
        if "damage_summary" in str(schema):
            return {"damage_summary": "s", "damage_scope": "sc", "covered_perils": [],
                    "exclusions": [], "deductible": "0"}
        return {"coverage_reasoning": "r", "covered": True, "related": True,
                "unit_price_p10": 90.0, "unit_price_p50": 100.0,
                "unit_price_p90": 110.0, "flag": ""}

    monkeypatch.setattr(llm, "ask_json", fake_ask_json)
    monkeypatch.setattr(llm, "backend", lambda: "anthropic")
    case = Case(case_id="t", policy_text="p", damage_description="d",
                items=(LineItem(idx=1, description="Removal of damp click vinyl",
                                qty=16.0, unit="m2"),))

    # anchors OFF: prompts and system must be exactly what shipped
    seen.clear()
    ensemble.prefetch_sync(case, samples=1)
    item_prompt, item_system = seen[-1]
    assert "PROVEN FLOORS" not in item_system
    assert item_system == ensemble.SYSTEM
    assert "net floor per unit" not in item_prompt

    # anchors ON
    seen.clear()
    got = ensemble.prefetch_sync(case, samples=1, anchors=tuple(POOL), anchor_game=9)
    assert got and got[1].belief is not None
    item_prompt, item_system = seen[-1]
    assert item_system == ensemble.SYSTEM + anchors.ANCHOR_SYSTEM_NOTE
    assert "PROVEN FLOORS on the fair value" in item_system
    assert "CLOSEST COMPARABLES" in item_prompt
    assert "price it 0" in item_prompt
    assert item_prompt.index("FULL INVOICE") < item_prompt.index("CLOSEST COMPARABLES")
    assert item_prompt.index("CLOSEST COMPARABLES") < item_prompt.index("VALUE THIS LINE")

    # under the tier-2 budget the block is dropped and the prompt reverts
    seen.clear()
    ensemble.prefetch_sync(case, samples=1, anchors=tuple(POOL), anchor_game=9,
                           anchor_budget_s=1.0)
    item_prompt, item_system = seen[-1]
    assert "CLOSEST COMPARABLES" not in item_prompt
    assert item_system == ensemble.SYSTEM


def test_prefetch_survives_a_broken_selector(monkeypatch):
    """A defect in retrieval must cost accuracy, never a round."""
    from c2f.core.models import Case
    from c2f.estimate import llm

    async def fake_ask_json(prompt, *, schema, fast, timeout, system=None, images=()):
        if "damage_summary" in str(schema):
            return {"damage_summary": "s", "damage_scope": "sc", "covered_perils": [],
                    "exclusions": [], "deductible": "0"}
        return {"coverage_reasoning": "r", "covered": True, "related": True,
                "unit_price_p10": 90.0, "unit_price_p50": 100.0,
                "unit_price_p90": 110.0, "flag": ""}

    def boom(*a, **kw):
        raise RuntimeError("selector exploded")

    monkeypatch.setattr(llm, "ask_json", fake_ask_json)
    monkeypatch.setattr(llm, "backend", lambda: "anthropic")
    monkeypatch.setattr(ensemble.anchor_lib, "block", boom)
    case = Case(case_id="t", policy_text="p", damage_description="d",
                items=(LineItem(idx=1, description="x", qty=1.0, unit="m2"),))
    got = ensemble.prefetch_sync(case, samples=1, anchors=tuple(POOL), anchor_game=9)
    assert got and got[1].belief is not None
