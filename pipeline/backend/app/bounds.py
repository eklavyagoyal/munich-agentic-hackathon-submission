"""Derived layer: reconstruct charges, bound the secret threshold t per item,
attribute every lost euro to an error class — and VALIDATE the interpretation
against the official matrix before trusting any of it.

Evidence rules — VALIDATED against the official performance endpoint:
  `amount` is what the ISSUER receives.
  rejected & amount>0  -> the charge was FAIR: a = amount, H got a, I paid 1.5*amount. t >= amount.
  rejected & amount=0  -> the charge was FRAUD: a > t (size unknown from this row alone)
  accepted             -> H got amount = min(a, c); proves nothing about fairness alone,
                          but reconstructs a (exactly, unless the cap bit: then amount=c>=4t,
                          and t < amount still holds, so it stays a valid upper bound).
  Cross-check: income(team) == sum(amount) over its issuer rows,
               costs(team)  == sum(accepted amount) + 1.5*sum(rejected-paid amount) as reviewer.

    .venv/bin/python -m backend.app.bounds
"""
from __future__ import annotations

from collections import defaultdict

from .config import OUR_TEAM
from .db import connect


def reconstruct(con) -> None:
    """Fill issuer_prices and item_bounds from transactions."""
    con.execute("DELETE FROM issuer_prices")
    con.execute("DELETE FROM item_bounds")

    # (game, issuer, item) -> evidence
    acc: dict[tuple, dict] = defaultdict(lambda: {
        "n_acc": 0, "n_rej_paid": 0, "n_rej_zero": 0, "a_pen": 0.0, "a_acc": 0.0})
    for r in con.execute("SELECT game_id, issuer, line_item, accepted, amount FROM transactions"):
        e = acc[(r["game_id"], r["issuer"], r["line_item"])]
        if r["accepted"]:
            e["n_acc"] += 1
            e["a_acc"] = max(e["a_acc"], r["amount"])
        elif r["amount"] > 0:
            e["n_rej_paid"] += 1
            e["a_pen"] = max(e["a_pen"], r["amount"])
        else:
            e["n_rej_zero"] += 1

    rows = []
    for (g, issuer, item), e in acc.items():
        if e["n_rej_paid"]:
            a, src = e["a_pen"], "penalty"       # exact: fair charge, amount=a
        elif e["n_acc"] and e["a_acc"] > 0:
            a, src = e["a_acc"], "accepted"      # min(a, c)
        elif e["n_rej_zero"]:
            a, src = None, "unknown"             # fraud, size unknown
        else:
            a, src = 0.0, "zero"                 # charged nothing / defaulted
        rows.append((g, issuer, item, a, src, e["n_acc"], e["n_rej_paid"], e["n_rej_zero"]))
    con.executemany("INSERT INTO issuer_prices VALUES (?,?,?,?,?,?,?,?)", rows)

    # t bounds per (game, item)
    bounds: dict[tuple, dict] = defaultdict(lambda: {"lo": 0.0, "hi": None, "n": 0})
    for (g, issuer, item), e in acc.items():
        b = bounds[(g, item)]
        fair = e["n_rej_paid"] > 0
        fraud = e["n_rej_zero"] > 0 and not fair   # on conflict, the penalty evidence wins
        if fair:
            b["lo"] = max(b["lo"], e["a_pen"])
            b["n"] += 1
        elif fraud:
            a_hat = e["a_pen"] if e["n_rej_paid"] else (e["a_acc"] or None)
            if a_hat:
                b["hi"] = a_hat if b["hi"] is None else min(b["hi"], a_hat)
                b["n"] += 1
    con.executemany("INSERT INTO item_bounds VALUES (?,?,?,?,?)",
                    [(g, item, b["lo"], b["hi"], b["n"]) for (g, item), b in bounds.items()])
    con.commit()
    n_ip = con.execute("SELECT COUNT(*) c FROM issuer_prices").fetchone()["c"]
    n_ib = con.execute("SELECT COUNT(*) c FROM item_bounds").fetchone()["c"]
    inverted = con.execute(
        "SELECT COUNT(*) c FROM item_bounds WHERE t_hi IS NOT NULL AND t_hi < t_lo").fetchone()["c"]
    print(f"issuer_prices: {n_ip} · item_bounds: {n_ib} · inverted bounds: {inverted}")


def team_game_net(con) -> dict[tuple, float]:
    """Reconstruct net per (team, game) from transactions.
    amount is what the issuer receives:
      accepted:            H +amount, I -amount
      rejected, amount>0:  H +amount, I -1.5*amount (charge + lawyer penalty)
      rejected, amount=0:  nothing flows
    """
    net: dict[tuple, float] = defaultdict(float)
    for r in con.execute("SELECT game_id, issuer, reviewer, accepted, amount FROM transactions"):
        g, amt = r["game_id"], r["amount"]
        if r["accepted"]:
            net[(r["issuer"], g)] += amt
            net[(r["reviewer"], g)] -= amt
        elif amt > 0:
            net[(r["issuer"], g)] += amt
            net[(r["reviewer"], g)] -= 1.5 * amt
    return net


# Games 81+ carry the 3x multiplier: official cells are exactly 3x the
# transaction net (proven on game 81, all 5 nonzero cells; game 80 still
# validated at 1x). The API exposes no multiplier field, so the boundary
# is pinned here.
FIRST_3X_GAME = 81


def multiplier(game_id: int) -> int:
    return 3 if game_id >= FIRST_3X_GAME else 1


def validate(con) -> bool:
    """Reconstructed nets (x multiplier) must reproduce the official matrix."""
    net = team_game_net(con)
    worst = 0.0
    n = 0
    for r in con.execute("SELECT game_id, team, score FROM scores WHERE score IS NOT NULL"):
        got = net.get((r["team"], r["game_id"]), 0.0) * multiplier(r["game_id"])
        worst = max(worst, abs(got - r["score"]))
        n += 1
    ok = worst < 1.0
    print(f"validation: {n} matrix cells, max |reconstructed - official| = {worst:.4f} "
          f"-> {'OK' if ok else 'MISMATCH — interpretation wrong, do not trust derived numbers'}")
    return ok


def main() -> None:
    con = connect()
    reconstruct(con)
    ok = validate(con)
    # Headline: our provably-lost euros by error class
    q = """
    WITH ours AS (
      SELECT t.game_id, t.line_item, t.accepted, t.amount,
             ip.a_source, ib.t_lo, ib.t_hi
      FROM transactions t
      LEFT JOIN issuer_prices ip ON ip.game_id=t.game_id AND ip.issuer=t.issuer AND ip.line_item=t.line_item
      LEFT JOIN item_bounds ib ON ib.game_id=t.game_id AND ib.line_item=t.line_item
      WHERE t.reviewer = ?
    )
    SELECT
      SUM(CASE WHEN accepted=0 AND amount>0 THEN amount/2.0 ELSE 0 END) AS penalty_surcharge,
      SUM(CASE WHEN accepted=1 AND a_source='unknown' THEN 0 ELSE 0 END) AS _x,
      SUM(CASE WHEN accepted=1 AND t_hi IS NOT NULL AND amount >= t_hi THEN amount ELSE 0 END) AS paid_proven_fraud
    FROM ours
    """
    r = con.execute(q, (OUR_TEAM,)).fetchone()
    print(f"{OUR_TEAM} as reviewer: penalty surcharge (avoidable 0.5a) = {r['penalty_surcharge']:,.0f} · "
          f"paid on proven-fraud charges = {r['paid_proven_fraud']:,.0f}")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
