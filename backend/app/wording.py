"""Wording memory: policy wordings repeat across games. Fingerprint each
case's policy at clause level (content-addressed, like the v1 clause corpus),
match a case to prior games by clause overlap, and surface the PROVEN
outcomes of matched games' items (item_bounds) as precedent evidence:
"under this wording, these items ended worthless / paid".

Motivation (games 79/81): the digest saw the glazing exclusion but the
estimator still priced the labour items around the excluded glass. A proven
precedent from an earlier game with the same wording is a hard fact the
digest can carry.

Analysis-side like bounds.py — the runner does not import this. Leak rule:
all lookups take exclude_game so backtests are leave-one-game-out and live
play (future games) is unaffected.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .anchors import _tokens
from .config import CASES_EXTRACTED
from .db import connect
from .parse import ParseError, load_case

# Proven-worthless boundary from the v1 post-mortem: the proven-worthless
# population never exceeded t < 176 (median ceiling 38). Paid mirror-boundary
# uses the same cut so the two classes cannot overlap.
WORTHLESS_HI = 176.0
PAID_LO = 176.0

_HEADING = re.compile(r"^\s*(?:[0-9]+(?:\.[0-9]+)*\s|PART\s|-{5,}|={5,})", re.I)


def _clauses(text: str) -> list[str]:
    """Split a policy into clause-sized chunks, normalised for hashing."""
    out: list[str] = []
    buf: list[str] = []
    for line in text.splitlines():
        if _HEADING.match(line) or not line.strip():
            if buf:
                out.append(" ".join(" ".join(buf).split()))
                buf = []
            continue
        buf.append(line.strip())
    if buf:
        out.append(" ".join(" ".join(buf).split()))
    return [c for c in out if len(c) >= 60]


def _fp(clause: str) -> str:
    return hashlib.sha1(clause.lower().encode()).hexdigest()[:12]


def policy_fingerprints() -> dict[int, set[str]]:
    """game_id -> set of clause fingerprints, over all extracted cases."""
    fps: dict[int, set[str]] = {}
    for d in sorted(CASES_EXTRACTED.glob("game_*")):
        pol = d / "policy.txt"
        if not pol.is_file():
            continue
        gid = int(d.name.split("_")[1])
        fps[gid] = {_fp(c) for c in _clauses(pol.read_text(errors="replace"))}
    return fps


def match_wordings(gid: int, fps: dict[int, set[str]],
                   min_jaccard: float = 0.5) -> list[tuple[int, float]]:
    """Prior games whose policy shares clauses with gid's, best first."""
    mine = fps.get(gid)
    if not mine:
        return []
    out = []
    for other, theirs in fps.items():
        if other == gid:
            continue
        j = len(mine & theirs) / len(mine | theirs)
        if j >= min_jaccard:
            out.append((other, round(j, 3)))
    return sorted(out, key=lambda t: -t[1])


def _proven_items(con, gid: int) -> list[dict]:
    """Items of one game with a proven verdict and a parsed description."""
    case_dir = CASES_EXTRACTED / f"game_{gid:03d}"
    if not case_dir.is_dir():
        return []
    try:
        case = load_case(gid, case_dir)
    except (ParseError, OSError):
        return []
    desc = {it.idx: it.description for it in case.items}
    out = []
    for r in con.execute("SELECT line_item, t_lo, t_hi FROM item_bounds "
                         "WHERE game_id=?", (gid,)):
        d = desc.get(r["line_item"])
        if not d:
            continue
        verdict = None
        if r["t_hi"] is not None and r["t_hi"] <= WORTHLESS_HI:
            verdict = "worthless"
        elif r["t_lo"] >= PAID_LO:
            verdict = "paid"
        if verdict:
            out.append({"game": gid, "item": r["line_item"], "desc": d,
                        "t_lo": r["t_lo"], "t_hi": r["t_hi"], "verdict": verdict})
    return out


def precedents(gid: int, fps: dict[int, set[str]] | None = None,
               min_jaccard: float = 0.5) -> list[dict]:
    """Proven items from games sharing gid's policy wording (leak-safe)."""
    fps = fps or policy_fingerprints()
    con = connect()
    out: list[dict] = []
    for other, j in match_wordings(gid, fps, min_jaccard):
        for it in _proven_items(con, other):
            out.append({**it, "jaccard": j})
    return out


def _scenario_match(gid: int, damage: str, min_sim: float = 0.6) -> tuple[int, float] | None:
    """Best earlier game whose damage description matches (idf-weighted overlap).
    The organizers recycle scenarios, sometimes verbatim (73<-35, 74<-15, 80<-75)."""
    import math
    descs: dict[int, set[str]] = {}
    for d in CASES_EXTRACTED.glob("game_*"):
        f = d / "description.txt"
        g = int(d.name.split("_")[1])
        if g < gid and f.is_file():
            descs[g] = _tokens(f.read_text(errors="replace"))
    if not descs:
        return None
    mine = _tokens(damage)
    df: dict[str, int] = {}
    for t in descs.values():
        for w in t:
            df[w] = df.get(w, 0) + 1
    n = len(descs) + 1
    best, hit = 0.0, None
    for g, theirs in descs.items():
        den = sum(math.log(n / df.get(w, 1)) for w in mine | theirs)
        num = sum(math.log(n / df.get(w, 1)) for w in mine & theirs)
        s = num / den if den else 0.0
        if s > best:
            best, hit = s, g
    return (hit, round(best, 2)) if hit is not None and best >= min_sim else None


def _precedent_lines(kind: str, gid_other: int, score: float, items: list[dict]) -> str | None:
    worth = [i for i in items if i["verdict"] == "worthless"][:4]
    paid = [i for i in items if i["verdict"] == "paid"][:3]
    if not worth and not paid:
        return None
    parts = [f"- {kind} game (match {score:.2f}), adjudicated outcomes:"]
    for i in worth:
        parts.append(f"    worthless (t<{i['t_hi']:.0f}): {i['desc'][:70]!r}")
    for i in paid:
        parts.append(f"    paid (t>={i['t_lo']:.0f}): {i['desc'][:70]!r}")
    return "\n".join(parts)


def precedent_block(case) -> str:
    """Digest addition for the estimator prompt: proven outcomes of earlier
    games with the same scenario or the same policy wording. '' when none."""
    gid = case.game_id
    con = connect()
    blocks: list[str] = []
    hit = _scenario_match(gid, case.damage)
    if hit:
        items = _proven_items(con, hit[0])
        line = _precedent_lines("Same damage scenario as an earlier", hit[0], hit[1], items)
        if line:
            blocks.append(line)
    fps = policy_fingerprints()
    matches = [(g, j) for g, j in match_wordings(gid, fps) if g < gid]
    if matches and (not hit or matches[0][0] != hit[0]):
        g, j = matches[0]
        line = _precedent_lines("Same policy wording as an earlier", g, j, _proven_items(con, g))
        if line:
            blocks.append(line)
    if not blocks:
        return ""
    return ("\nPROVEN precedents from earlier tournament rounds (the organizers reuse "
            "scenarios and wordings; these are adjudicated results, strong evidence "
            "for what is covered and at what level):\n" + "\n".join(blocks) + "\n")


def _best_sim(desc: str, pool: list[dict]) -> tuple[float, dict | None]:
    t = _tokens(desc)
    best, hit = 0.0, None
    for p in pool:
        pt = _tokens(p["desc"])
        if not t or not pt:
            continue
        j = len(t & pt) / len(t | pt)
        if j > best:
            best, hit = j, p
    return best, hit


def main() -> None:
    fps = policy_fingerprints()
    con = connect()
    print(f"wording corpus: {len(fps)} policies, "
          f"{len(set().union(*fps.values()))} distinct clauses")

    n_match = sum(1 for g in fps if match_wordings(g, fps))
    print(f"games with a matched prior wording (LOGO): {n_match}/{len(fps)}")

    for item_sim in (0.4, 0.5, 0.6):
        tp = fp_ = fn = 0
        for gid in sorted(fps):
            own = _proven_items(con, gid)
            if not own:
                continue
            pool = [p for p in precedents(gid, fps) if p["verdict"] == "worthless"]
            for it in own:
                sim, _hit = _best_sim(it["desc"], pool)
                flagged = sim >= item_sim
                if flagged and it["verdict"] == "worthless":
                    tp += 1
                elif flagged and it["verdict"] == "paid":
                    fp_ += 1
                elif not flagged and it["verdict"] == "worthless":
                    fn += 1
        prec = tp / (tp + fp_) if tp + fp_ else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        print(f"item_sim>={item_sim}: flagged worthless correctly {tp}, "
              f"false-flagged paid {fp_}, missed {fn} "
              f"-> precision {prec:.2f} recall {rec:.2f}")


if __name__ == "__main__":
    main()
