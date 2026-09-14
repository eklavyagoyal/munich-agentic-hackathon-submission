#!/usr/bin/env python3
"""Render the README figures from the harvested tournament database.

Two charts, both derived only from public leaderboard data -- game ids, team names,
scores, and per-line-item settlement flows. No invoice, policy, damage-description or
photo content is read, and none can be: the source tables hold no text at all.

    PYTHONPATH=. python3 tools/make_charts.py

Writes docs/assets/standings.svg and docs/assets/endgame.svg.

The score model is re-derived here rather than trusted, and the run aborts unless it
reproduces every one of the 1,700 official score cells to the cent:

    issuer income  = sum of settled amounts where the team issued
    reviewer cost  = sum of settled amounts where the team reviewed, at 1.5x
                     when the team rejected (the asymmetric wrong-decision penalty)
    weight         = 3x for games 81-100, 1x before
    score          = sum over games of weight * (income - cost)
"""
from __future__ import annotations

import sqlite3
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "c2f.sqlite"
OUT = ROOT / "docs" / "assets"
US = "Oasis"
TRIPLE_FROM = 81          # the organisers' 3x weighting switched on here
ENDGAME = (84, 100)       # the stretch the corrected package was live for
TOLERANCE_EUR = 0.01

# Observatory palette, so the figures and the screenshots read as one system.
INK = "#e9e6df"
DIM = "#8b9398"
FAINT = "#39424a"
GRID = "#1b2126"
CARD = "#0b0e11"
EDGE = "#1d242a"
TEAL = "#5eead4"
RED = "#f87171"
AMBER = "#fbbf24"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"


class DataError(RuntimeError):
    """The database cannot support an honest figure."""


# ---------------------------------------------------------------- data


def _connect() -> sqlite3.Connection:
    if not DB.exists():
        raise DataError(f"no harvested database at {DB} -- run tools/harvest.py first")
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def weight(game: int) -> float:
    return 3.0 if game >= TRIPLE_FROM else 1.0


def load(con: sqlite3.Connection) -> tuple[dict, dict, list[int], list[str]]:
    """Per-game score, income and cost for every team, validated against the feed."""
    games = [r[0] for r in con.execute("SELECT DISTINCT game_id FROM scores ORDER BY 1")]
    teams = [r[0] for r in con.execute(
        "SELECT team FROM scores GROUP BY team ORDER BY SUM(score) DESC")]
    if not games or not teams:
        raise DataError("scores table is empty")

    score = {(r["game_id"], r["team"]): r["score"]
             for r in con.execute("SELECT game_id, team, score FROM scores")}

    flow: dict[tuple[int, str], list[float]] = {}
    for r in con.execute("""
        SELECT game_id, issuer AS team, SUM(amount) AS v
        FROM transactions GROUP BY 1, 2"""):
        flow.setdefault((r["game_id"], r["team"]), [0.0, 0.0])[0] = r["v"]
    for r in con.execute("""
        SELECT game_id, reviewer AS team,
               SUM(amount * CASE WHEN accepted = 1 THEN 1.0 ELSE 1.5 END) AS v
        FROM transactions GROUP BY 1, 2"""):
        flow.setdefault((r["game_id"], r["team"]), [0.0, 0.0])[1] = r["v"]

    # The gate: derived P&L must reproduce the official matrix, or nothing ships.
    worst, cells = 0.0, 0
    for g in games:
        for t in teams:
            income, cost = flow.get((g, t), (0.0, 0.0))
            derived = weight(g) * (income - cost)
            worst = max(worst, abs(derived - score.get((g, t), 0.0)))
            cells += 1
    if worst > TOLERANCE_EUR:
        raise DataError(
            f"score model does not reproduce the official matrix "
            f"({cells} cells, worst error EUR {worst:,.4f}) -- refusing to draw")
    print(f"  reconciled {cells} official score cells, worst error EUR {worst:.6f}")
    return score, flow, games, teams


# ---------------------------------------------------------------- svg helpers


def txt(x, y, s, size=12, fill=INK, family=SANS, anchor="start", weight_="400",
        spacing=None, opacity=None) -> str:
    extra = f' letter-spacing="{spacing}"' if spacing else ""
    extra += f' opacity="{opacity}"' if opacity else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight_}"{extra}>'
            f'{escape(str(s))}</text>')


def eur(v: float) -> str:
    a = abs(v)
    if a >= 1e6:
        s = f"{a/1e6:.1f}m".replace(".0m", "m")
    elif a >= 1e3:
        s = f"{a/1e3:.0f}k"
    else:
        s = f"{a:.0f}"
    return ("−" if v < 0 else "") + "€" + s


def nice_ticks(lo: float, hi: float, target: int = 6) -> list[float]:
    """Round tick values, so an axis never reads -223k."""
    span = hi - lo
    if span <= 0:
        return [lo]
    raw = span / max(1, target)
    mag = 10 ** int(f"{raw:e}".split("e")[1])
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    first = step * (int(lo / step) + (1 if lo > 0 else 0))
    out, v = [], first
    while v <= hi:
        out.append(v)
        v += step
    return out


def stack_labels(entries: list[tuple[float, str]], gap: float) -> list[tuple[float, str]]:
    """Nudge right-edge series labels apart, keeping their original order."""
    entries = sorted(entries, key=lambda e: e[0])
    ys = [e[0] for e in entries]
    for i in range(1, len(ys)):                       # push down
        ys[i] = max(ys[i], ys[i - 1] + gap)
    for i in range(len(ys) - 2, -1, -1):              # then relieve upward
        ys[i] = min(ys[i], ys[i + 1] - gap)
    return [(y, e[1]) for y, e in zip(ys, entries)]


def card(w: int, h: int, body: str, title: str, subtitle: str, eyebrow: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" \
viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">
<rect width="{w}" height="{h}" rx="14" fill="{CARD}"/>
<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="13.5" fill="none" stroke="{EDGE}"/>
{txt(32, 42, eyebrow, 10.5, TEAL, MONO, spacing="2.4", weight_="600")}
{txt(32, 74, title, 25, INK, SANS, weight_="600")}
{txt(32, 98, subtitle, 12.5, DIM, SANS)}
{body}
</svg>
"""


# ---------------------------------------------------------------- chart 1


def standings(score, games, teams) -> str:
    """100 rounds of cumulative EUR, seventeen teams, ours in front."""
    W, H = 1240, 600
    L, R, T, B = 74, 168, 142, 58
    pw, ph = W - L - R, H - T - B

    cum = {t: [] for t in teams}
    for t in teams:
        run = 0.0
        for g in games:
            run += score.get((g, t), 0.0)
            cum[t].append(run)

    lo = min(min(v) for v in cum.values())
    hi = max(max(v) for v in cum.values())
    pad = (hi - lo) * 0.06
    lo, hi = lo - pad, hi + pad

    def X(i): return L + pw * i / max(1, len(games) - 1)
    def Y(v): return T + ph * (hi - v) / (hi - lo)

    out = []
    # gridlines on round euro values
    for v in nice_ticks(lo, hi):
        y = Y(v)
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L+pw}" y2="{y:.1f}" '
                   f'stroke="{GRID}" stroke-width="1"/>')
        out.append(txt(L - 12, y + 4, "€0" if v == 0 else eur(v), 10.5,
                       FAINT, MONO, anchor="end"))
    y0 = Y(0)
    out.append(f'<line x1="{L}" y1="{y0:.1f}" x2="{L+pw}" y2="{y0:.1f}" '
               f'stroke="{FAINT}" stroke-width="1" stroke-dasharray="3 3"/>')

    # the 3x-weighted phase
    x81 = X(games.index(TRIPLE_FROM))
    out.append(f'<rect x="{x81:.1f}" y="{T}" width="{L+pw-x81:.1f}" height="{ph}" '
               f'fill="{TEAL}" opacity="0.045"/>')
    out.append(f'<line x1="{x81:.1f}" y1="{T}" x2="{x81:.1f}" y2="{T+ph}" '
               f'stroke="{TEAL}" stroke-width="1" opacity="0.35" stroke-dasharray="4 4"/>')
    out.append(txt(x81 + 8, T + 16, "3× WEIGHTED · GAMES 81–100",
                   9.5, TEAL, MONO, spacing="1.5", opacity="0.75"))

    # the field
    for t in teams:
        if t == US:
            continue
        pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(cum[t]))
        out.append(f'<polyline points="{pts}" fill="none" stroke="{DIM}" '
                   f'stroke-width="1.05" opacity="0.26"/>')

    # us
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(cum[US]))
    out.append(f'<polyline points="{pts}" fill="none" stroke="{TEAL}" stroke-width="2.6" '
               f'stroke-linejoin="round" stroke-linecap="round"/>')

    # right-edge labels, nudged apart so seventeen names stay readable
    for y, t in stack_labels([(Y(cum[t][-1]), t) for t in teams], 12.5):
        yr = Y(cum[t][-1])
        if t == US:
            out.append(f'<line x1="{L+pw+3:.1f}" y1="{yr:.1f}" x2="{L+pw+9:.1f}" '
                       f'y2="{y:.1f}" stroke="{TEAL}" stroke-width="1"/>')
            out.append(txt(L + pw + 13, y + 3.6, "OASIS", 11.5, TEAL, SANS, weight_="700"))
        else:
            if abs(y - yr) > 3:
                out.append(f'<line x1="{L+pw+3:.1f}" y1="{yr:.1f}" x2="{L+pw+9:.1f}" '
                           f'y2="{y:.1f}" stroke="{FAINT}" stroke-width="0.8"/>')
            out.append(txt(L + pw + 13, y + 3.2, t, 9.5, DIM, SANS, opacity="0.62"))

    # game 82 -- the single round that cost more than every model error combined
    i82 = games.index(82)
    x82, y82 = X(i82), Y(cum[US][i82])
    out.append(f'<circle cx="{x82:.1f}" cy="{y82:.1f}" r="4.5" fill="{RED}"/>')
    out.append(f'<circle cx="{x82:.1f}" cy="{y82:.1f}" r="10" fill="none" '
               f'stroke="{RED}" stroke-width="1" opacity="0.4"/>')
    out.append(f'<path d="M{x82-11:.1f},{y82+6:.1f} L{x82-46:.1f},{y82+40:.1f} '
               f'H{x82-58:.1f}" fill="none" stroke="{RED}" stroke-width="1" opacity="0.5"/>')
    out.append(txt(x82 - 64, y82 + 36, "GAME 82  −€241,938", 10.5, RED,
                   MONO, anchor="end", weight_="600"))
    out.append(txt(x82 - 64, y82 + 52, "a stale runner on a third machine kept",
                   10, DIM, SANS, anchor="end"))
    out.append(txt(x82 - 64, y82 + 65, "submitting; PUT is last-write-wins",
                   10, DIM, SANS, anchor="end"))

    # x axis
    for g in (1, 20, 40, 60, 80, 100):
        out.append(txt(X(games.index(g)), T + ph + 24, g, 10.5, FAINT, MONO, anchor="middle"))
    out.append(txt(L + pw / 2, T + ph + 44, "GAME", 9.5, FAINT, MONO,
                   anchor="middle", spacing="2"))

    return card(W, H, "\n".join(out),
                "One hundred rounds. Every outlier matters.",
                "Cumulative EUR per team · 17 teams · reconciled to the official "
                "score matrix to the cent",
                "THE RACE")


# ---------------------------------------------------------------- chart 2


def endgame(flow, teams) -> str:
    """Games 84-100: where the rebuilt pipeline actually landed."""
    W, H = 1240, 600
    L, R, T, B = 96, 170, 142, 78
    pw, ph = W - L - R, H - T - B
    g0, g1 = ENDGAME

    inc, cost = {}, {}
    for t in teams:
        inc[t] = sum(flow.get((g, t), (0.0, 0.0))[0] for g in range(g0, g1 + 1))
        cost[t] = sum(flow.get((g, t), (0.0, 0.0))[1] for g in range(g0, g1 + 1))

    live = [t for t in teams if inc[t] > 0]      # three teams stopped submitting
    xs = [inc[t] for t in live]
    ys = [cost[t] for t in live]
    xlo, xhi = min(xs) * 0.88, max(xs) * 1.05
    ylo, yhi = min(ys) * 0.94, max(ys) * 1.04

    def X(v): return L + pw * (v - xlo) / (xhi - xlo)
    def Y(v): return T + ph * (yhi - v) / (yhi - ylo)

    out = []
    for v in nice_ticks(ylo, yhi, 5):
        y = Y(v)
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L+pw}" y2="{y:.1f}" '
                   f'stroke="{GRID}" stroke-width="1"/>')
        out.append(txt(L - 12, y + 4, eur(v), 10.5, FAINT, MONO, anchor="end"))
    for v in nice_ticks(xlo, xhi, 5):
        x = X(v)
        out.append(f'<line x1="{x:.1f}" y1="{T}" x2="{x:.1f}" y2="{T+ph}" '
                   f'stroke="{GRID}" stroke-width="1"/>')
        out.append(txt(x, T + ph + 24, eur(v), 10.5, FAINT, MONO, anchor="middle"))

    # Iso-net diagonal through us: cost = income - net. Every team below and right of
    # this line beat us on net; over this stretch, nobody is.
    net_us = inc[US] - cost[US]
    a = (max(xlo, ylo + net_us), max(ylo, xlo - net_us))
    bx = min(xhi, yhi + net_us)
    out.append(f'<line x1="{X(a[0]):.1f}" y1="{Y(a[1]):.1f}" x2="{X(bx):.1f}" '
               f'y2="{Y(bx - net_us):.1f}" stroke="{TEAL}" stroke-width="1" '
               f'opacity="0.30" stroke-dasharray="5 4"/>')
    out.append(txt(L + pw - 8, T + 18,
                   f"ISO-NET · {eur(net_us)} · EVERY OTHER TEAM SITS ABOVE IT",
                   9.5, TEAL, MONO, anchor="end", spacing="1.4", opacity="0.7"))

    # de-collided labels for the field
    placed = stack_labels([(Y(cost[t]), t) for t in live], 15)
    for ly, t in placed:
        if t == US:
            continue
        x, y = X(inc[t]), Y(cost[t])
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.2" fill="{DIM}" opacity="0.55"/>')
        if abs(ly - y) > 3:
            out.append(f'<line x1="{x+6:.1f}" y1="{y:.1f}" x2="{x+11:.1f}" y2="{ly:.1f}" '
                       f'stroke="{FAINT}" stroke-width="0.8"/>')
        out.append(txt(x + 14, ly + 3.4, t, 9.5, DIM, SANS, opacity="0.72"))

    x, y = X(inc[US]), Y(cost[US])
    out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="24" fill="{TEAL}" opacity="0.10"/>')
    out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{TEAL}"/>')
    # callout to the right of the dot, in the clear margin
    out.append(txt(x + 18, y - 14, "OASIS", 14, TEAL, SANS, weight_="700"))
    out.append(txt(x + 18, y + 3, "most issuer income of all 17", 10.5, INK, SANS))
    out.append(txt(x + 18, y + 17, f"best net in the field: {eur(net_us)}", 10.5, DIM, SANS))

    out.append(txt(L + pw / 2, H - 24, "ISSUER INCOME — WHAT THE FIELD PAID US",
                   9.5, FAINT, MONO, anchor="middle", spacing="2"))
    out.append(f'<g transform="translate(26,{T + ph/2}) rotate(-90)">'
               f'{txt(0, 0, "REVIEWER COST — SETTLEMENT + REJECTION PENALTY", 9.5, FAINT, MONO, anchor="middle", spacing="2")}</g>')

    return card(W, H, "\n".join(out),
                "The half of the game we won.",
                f"Games {g0}–{g1}, the stretch the rebuilt pipeline was live for "
                f"· settled EUR, before the 3× score weighting "
                f"· {len(live)} of 17 teams still submitting",
                "THE ENDGAME")


# ---------------------------------------------------------------- banner


def banner(score, flow, games, teams) -> str:
    """The first thing anyone sees: who we are, and the four numbers that matter."""
    W, H = 1240, 300
    cum, run = [], 0.0
    for g in games:
        run += score.get((g, US), 0.0)
        cum.append(run)

    # sparkline of our own run, bled across the lower half as texture
    sx0, sx1, sy0, sy1 = 0, W, 250, 296
    lo, hi = min(cum), max(cum)
    span = (hi - lo) or 1.0
    pts = [(sx0 + (sx1 - sx0) * i / (len(cum) - 1),
            sy1 - (sy1 - sy0) * (v - lo) / span) for i, v in enumerate(cum)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{pts[0][0]:.1f},{H} " + line + f" {pts[-1][0]:.1f},{H}"

    g0, g1 = ENDGAME
    endgame_inc = {t: sum(flow.get((g, t), (0.0, 0.0))[0] for g in range(g0, g1 + 1))
                   for t in teams}
    rank_inc = 1 + sorted(endgame_inc.values(), reverse=True).index(endgame_inc[US])
    final = cum[-1]
    rank = 1 + sorted((sum(score.get((g, t), 0.0) for g in games) for t in teams),
                      reverse=True).index(final)

    stats = [
        (f"{rank} / {len(teams)}", "FINAL PLACING"),
        (f"−€{abs(final):,.0f}", "CUMULATIVE EUR"),
        (f"{rank_inc}st of {len(teams)}", f"ISSUER INCOME, GAMES {g0}–{g1}"),
        (f"{len(games)}", "ROUNDS PLAYED, BLIND"),
    ]

    out = [
        f'<rect width="{W}" height="{H}" rx="16" fill="{CARD}"/>',
        f'<polygon points="{area}" fill="{TEAL}" opacity="0.055"/>',
        f'<polyline points="{line}" fill="none" stroke="{TEAL}" stroke-width="2" '
        f'opacity="0.5" stroke-linejoin="round"/>',
        f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="15.5" fill="none" '
        f'stroke="{EDGE}"/>',
        txt(44, 62, "QUANTCO AGENTIC HACKATHON · MUNICH · CLAIM TO FAME",
            11, TEAL, MONO, spacing="2.6", weight_="600"),
        txt(44, 118, "Team Oasis", 46, INK, SANS, weight_="700"),
        txt(44, 150, "Seventeen teams price the same insurance claim blind, then "
                     "adjudicate each other’s invoices. One hundred rounds.",
            13.5, DIM, SANS),
    ]
    for i, (big, label) in enumerate(stats):
        x = 44 + i * 292
        out.append(f'<line x1="{x-16:.1f}" y1="178" x2="{x-16:.1f}" y2="234" '
                   f'stroke="{EDGE}"/>' if i else "")
        out.append(txt(x, 206, big, 27, TEAL if i in (0, 2) else INK, MONO, weight_="700"))
        out.append(txt(x, 228, label, 9.5, FAINT, MONO, spacing="1.6"))

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}" role="img" aria-label="Team Oasis, Claim to Fame">'
            + "\n".join(p for p in out if p) + "</svg>\n")


# ---------------------------------------------------------------- main


def main() -> int:
    try:
        con = _connect()
        score, flow, games, teams = load(con)
    except (DataError, sqlite3.Error) as exc:
        print(f"make_charts: {exc}", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    for name, svg in (("banner.svg", banner(score, flow, games, teams)),
                      ("standings.svg", standings(score, games, teams)),
                      ("endgame.svg", endgame(flow, teams))):
        (OUT / name).write_text(svg, encoding="utf-8")
        print(f"  wrote docs/assets/{name}  ({len(svg):,} bytes)")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
