"""Read-only data API for the dashboard. Serves aggregates from SQLite.

    .venv/bin/python -m backend.app.server        # http://127.0.0.1:8000
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .bounds import team_game_net
from .config import CASES_EXTRACTED, OUR_TEAM
from .db import connect

app = FastAPI(title="c2f analysis")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MULT_START = "2026-08-23T06:00:00+00:00"   # 3x scoring from 08:00 local


def q(con, sql: str, *args) -> list[dict]:
    return [dict(r) for r in con.execute(sql, args)]


@app.get("/api/overview")
def overview():
    con = connect()
    teams = q(con, "SELECT * FROM performance ORDER BY net DESC")
    curve = q(con, "SELECT game_id, score FROM scores WHERE team=? AND score IS NOT NULL ORDER BY game_id", OUR_TEAM)
    cum = 0.0
    for c in curve:
        cum += c["score"]
        c["cum"] = round(cum, 2)
    games = q(con, "SELECT id, start_time, status FROM games ORDER BY id")
    now = datetime.now(timezone.utc).isoformat()
    completed = sum(1 for g in games if g["status"] == "completed")
    upcoming = [g for g in games if g["start_time"] > now][:6]
    n_3x = sum(1 for g in games if g["start_time"] >= MULT_START)

    # our error buckets, in euros, per game (for the "where it went wrong" chart)
    buckets = q(con, """
      SELECT t.game_id,
        SUM(CASE WHEN t.accepted=0 AND t.amount>0 THEN t.amount/2.0 ELSE 0 END) AS penalty_surcharge,
        SUM(CASE WHEN t.accepted=1 AND ib.t_hi IS NOT NULL AND t.amount >= ib.t_hi THEN t.amount ELSE 0 END) AS paid_proven_fraud,
        SUM(CASE WHEN t.accepted=1 AND (ib.t_hi IS NULL OR t.amount < ib.t_hi) THEN t.amount ELSE 0 END) AS paid_rest
      FROM transactions t
      LEFT JOIN item_bounds ib ON ib.game_id=t.game_id AND ib.line_item=t.line_item
      WHERE t.reviewer = ?
      GROUP BY t.game_id ORDER BY t.game_id
    """, OUR_TEAM)

    # issuer-side: proven undercharge (t_lo - a) * n_opponents, and burned (proven-fraud charges)
    n_opp = max(len(teams) - 1, 1)
    under = q(con, """
      SELECT ip.game_id, ip.line_item, ip.a, ib.t_lo,
             (ib.t_lo - ip.a) * ? AS foregone
      FROM issuer_prices ip
      JOIN item_bounds ib ON ib.game_id=ip.game_id AND ib.line_item=ip.line_item
      WHERE ip.issuer = ? AND ip.a IS NOT NULL AND ip.a < ib.t_lo
    """, n_opp, OUR_TEAM)
    burned = q(con, """
      SELECT ip.game_id, COUNT(*) AS n
      FROM issuer_prices ip
      WHERE ip.issuer = ? AND ip.n_rejected_zero > 0 AND ip.n_rejected_paid = 0
      GROUP BY ip.game_id
    """, OUR_TEAM)
    totals = {
        "penalty_surcharge": round(sum(b["penalty_surcharge"] or 0 for b in buckets), 2),
        "paid_proven_fraud": round(sum(b["paid_proven_fraud"] or 0 for b in buckets), 2),
        "undercharge_foregone": round(sum(u["foregone"] for u in under), 2),
        "burned_items": sum(b["n"] for b in burned),
    }
    return {"our_team": OUR_TEAM, "teams": teams, "curve": curve, "completed": completed,
            "upcoming": upcoming, "n_3x": n_3x, "mult_start": MULT_START,
            "buckets": buckets, "totals": totals, "now": now}


@app.get("/api/games")
def games_list():
    con = connect()
    rows = q(con, """
      SELECT g.id, g.start_time, g.status, s.score,
             (SELECT COUNT(DISTINCT line_item) FROM transactions t WHERE t.game_id=g.id) AS n_items
      FROM games g LEFT JOIN scores s ON s.game_id=g.id AND s.team=?
      ORDER BY g.id
    """, OUR_TEAM)
    cum = 0.0
    for r in rows:
        if r["score"] is not None:
            cum += r["score"]
        r["cum"] = round(cum, 2)
    return rows


@app.get("/api/games/{gid}")
def game_detail(gid: int):
    con = connect()
    game = q(con, "SELECT * FROM games WHERE id=?", gid)
    if not game:
        raise HTTPException(404)
    items = q(con, """
      SELECT ib.line_item, ib.t_lo, ib.t_hi, ib.n_evidence,
             our.a AS our_a, our.a_source AS our_a_source,
             our.n_accepted AS our_n_acc, our.n_rejected_paid AS our_n_rej_paid,
             our.n_rejected_zero AS our_n_rej_zero
      FROM item_bounds ib
      LEFT JOIN issuer_prices our ON our.game_id=ib.game_id AND our.line_item=ib.line_item AND our.issuer=?
      WHERE ib.game_id=? ORDER BY ib.line_item
    """, OUR_TEAM, gid)
    charges = q(con, """
      SELECT issuer, line_item, a, a_source, n_accepted, n_rejected_paid, n_rejected_zero
      FROM issuer_prices WHERE game_id=? ORDER BY line_item, a DESC
    """, gid)
    our_reviews = q(con, """
      SELECT t.line_item, t.issuer, t.accepted, t.amount,
             ip.a AS issuer_a, ip.a_source
      FROM transactions t
      LEFT JOIN issuer_prices ip ON ip.game_id=t.game_id AND ip.issuer=t.issuer AND ip.line_item=t.line_item
      WHERE t.game_id=? AND t.reviewer=? ORDER BY t.line_item, t.amount DESC
    """, gid, OUR_TEAM)
    docs = {}
    case_dir = Path(str(CASES_EXTRACTED / f"game_{gid:03d}"))
    if case_dir.is_dir():
        for f in sorted(case_dir.rglob("*")):
            if f.is_file() and f.suffix.lower() in (".txt",):
                try:
                    docs[f.name] = f.read_text(errors="replace")[:40000]
                except OSError:
                    pass
    score = q(con, "SELECT team, score FROM scores WHERE game_id=? ORDER BY score DESC", gid)
    return {"game": game[0], "items": items, "charges": charges,
            "our_reviews": our_reviews, "docs": docs, "scores": score}


@app.get("/api/items")
def items_flat():
    con = connect()
    return q(con, """
      SELECT ib.game_id, ib.line_item, ib.t_lo, ib.t_hi,
             our.a AS our_a, our.a_source,
             our.n_rejected_zero AS our_rej_zero, our.n_rejected_paid AS our_rej_paid,
             CASE WHEN our.a IS NOT NULL AND our.a < ib.t_lo THEN (ib.t_lo - our.a) * 16 ELSE 0 END AS foregone
      FROM item_bounds ib
      LEFT JOIN issuer_prices our ON our.game_id=ib.game_id AND our.line_item=ib.line_item AND our.issuer=?
      ORDER BY foregone DESC, ib.game_id, ib.line_item
    """, OUR_TEAM)


@app.get("/api/teams")
def teams_behavior():
    con = connect()
    perf = q(con, "SELECT * FROM performance ORDER BY net DESC")
    # reviewer generosity: how often each team accepts, and the money-weighted accept share
    beh = q(con, """
      SELECT reviewer AS team,
             AVG(accepted) AS accept_rate,
             SUM(CASE WHEN accepted=1 THEN amount ELSE 0 END) AS paid_accepted,
             SUM(CASE WHEN accepted=0 AND amount>0 THEN 1.5*amount ELSE 0 END) AS paid_penalties,
             COUNT(*) AS n
      FROM transactions GROUP BY reviewer
    """)
    behm = {b["team"]: b for b in beh}
    issuer = q(con, """
      SELECT issuer AS team,
             SUM(CASE WHEN n_rejected_paid > 0 THEN 1 ELSE 0 END) AS fair_proven,
             SUM(CASE WHEN n_rejected_zero > 0 AND n_rejected_paid = 0 THEN 1 ELSE 0 END) AS fraud_proven,
             COUNT(*) AS n_items,
             AVG(a) AS avg_a
      FROM issuer_prices GROUP BY issuer
    """)
    issm = {i["team"]: i for i in issuer}
    out = []
    for p in perf:
        t = p["team"]
        out.append({**p, **{f"rev_{k}": v for k, v in (behm.get(t) or {}).items() if k != "team"},
                    **{f"iss_{k}": v for k, v in (issm.get(t) or {}).items() if k != "team"}})
    return out


@app.get("/api/pergame")
def per_game_nets():
    """Official per-game score for every team — the race chart."""
    con = connect()
    return q(con, "SELECT game_id, team, score FROM scores WHERE score IS NOT NULL ORDER BY game_id")


def main() -> None:
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
