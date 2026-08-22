"""Reference-price anchors: proven t-bands from played games, retrieved by
similarity and injected into the estimator prompt.

The single biggest error source is model spread (44% underestimates x1.67,
plus 3-5x overestimates on rental gear). Real adjudicated prices from THIS
tournament pin the scale. Retrieval is plain token overlap + a unit-class
bonus — no embeddings, no deps, fully deterministic.

Leak rule: exclude_game removes the game being estimated, so backtests are
leave-one-game-out and live play (future games) is unaffected.
"""
from __future__ import annotations

import re

from .db import connect
from .parse import ParseError, load_case
from .config import CASES_EXTRACTED

_WORD = re.compile(r"[a-zäöüß0-9²]+")
_STOP = {"the", "of", "and", "for", "to", "in", "a", "an", "with", "from", "und", "der", "die", "das"}


def _tokens(s: str) -> set[str]:
    return {w for w in _WORD.findall(s.lower()) if w not in _STOP and len(w) > 2}


_CACHE: list[dict] | None = None
_CACHE_TS: float = 0.0
_TTL = 600.0  # reload every 10 min so a long-lived runner sees new games


def load_anchors() -> list[dict]:
    """All items with a proven band, joined with their parsed description."""
    global _CACHE, _CACHE_TS
    import time
    if _CACHE is not None and time.monotonic() - _CACHE_TS < _TTL:
        return _CACHE
    con = connect()
    bands = {(r["game_id"], r["line_item"]): (r["t_lo"], r["t_hi"])
             for r in con.execute("SELECT * FROM item_bounds WHERE t_lo > 0 OR t_hi IS NOT NULL")}
    anchors: list[dict] = []
    games = sorted({g for g, _ in bands})
    for gid in games:
        case_dir = CASES_EXTRACTED / f"game_{gid:03d}"
        if not case_dir.is_dir():
            continue
        try:
            case = load_case(gid, case_dir)
        except (ParseError, OSError):
            continue
        for it in case.items:
            band = bands.get((gid, it.idx))
            if band is None:
                continue
            lo, hi = band
            anchors.append({"game": gid, "desc": it.description, "qty": it.qty,
                            "unit": it.unit, "t_lo": lo, "t_hi": hi,
                            "toks": _tokens(it.description)})
    _CACHE = anchors
    _CACHE_TS = time.monotonic()
    return anchors


def _fmt(a: dict) -> str:
    lo, hi = a["t_lo"], a["t_hi"]
    if lo and hi:
        band = f"approved ceiling between {lo:.0f} and {hi:.0f} EUR"
    elif lo:
        # lo is the highest charge PROVEN fair — the true ceiling sits above it.
        band = f"{lo:.0f} EUR was still approved (true ceiling is HIGHER than this)"
    else:
        band = f"charging {hi:.0f} EUR was rejected as inflated (ceiling is below this)"
    return f"- \"{a['desc']}\" ({a['qty']:g} {a['unit']}): {band}"


def anchors_for_case(case, exclude_game: int | None = None,
                     per_item: int = 2, max_total: int = 24) -> str:
    """Prompt block only (back-compat)."""
    return anchors_for_case_full(case, exclude_game, per_item, max_total)[0]


def anchors_for_case_full(case, exclude_game: int | None = None,
                          per_item: int = 2, max_total: int = 24) -> tuple[str, list[dict]]:
    """(prompt_block, structured list) of the most similar adjudicated items."""
    pool = [a for a in load_anchors() if a["game"] != exclude_game]
    if not pool:
        return "", []
    chosen: list[tuple[float, dict]] = []
    seen: set[tuple] = set()
    for it in case.items:
        toks = _tokens(it.description)
        if not toks:
            continue
        scored = []
        for a in pool:
            inter = len(toks & a["toks"])
            if inter == 0:
                continue
            score = inter / len(toks | a["toks"])
            if a["unit"].lower() == it.unit.lower():
                score += 0.15
            scored.append((score, a))
        scored.sort(key=lambda x: -x[0])
        for score, a in scored[:per_item]:
            key = (a["game"], a["desc"])
            if key not in seen:
                seen.add(key)
                chosen.append((score, a))
    chosen.sort(key=lambda x: -x[0])
    top = chosen[:max_total]
    lines = [_fmt(a) for _, a in top]
    if not lines:
        return "", []
    struct = [{"game": a["game"], "desc": a["desc"], "qty": a["qty"], "unit": a["unit"],
               "t_lo": a["t_lo"], "t_hi": a["t_hi"], "score": round(sc, 3)} for sc, a in top]
    block = ("\nAdjudicated evidence from earlier cases in THIS tournament about the "
             "approved-price ceiling for similar items. IMPORTANT: 'was still approved' "
             "amounts are proven FLOORS — the fair ceiling lies above them, so estimate "
             "above such amounts, and below any rejected amount:\n"
             + "\n".join(lines) + "\n")
    return block, struct
