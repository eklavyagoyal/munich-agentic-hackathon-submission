"""Offline policy optimizer on proven bands — no LLM calls.

Income model (per estimated item with a two-sided band, per opponent x16):
  P(fair)  = P(a <= t), t ~ Uniform[t_lo, t_hi]  -> pays a
  P(fraud) = 1 - P(fair)                          -> pays F_HAT * a  (measured
             acceptance rate on proven-fraud charges; capped amounts ignored,
             a <= 4t in our range)

Reviewer model (against real reconstructed opponent charges):
  accept (a_opp <= b): pay a_opp
  reject: pay 1.5*a_opp with probability the charge was fair (band-uniform)

b policy: value-dependent multiplier on t_hat, then clamped by anchor evidence
(best similar item's proven band), mirroring what decide() can do live.

    .venv/bin/python -m backend.app.opt
"""
from __future__ import annotations

from .anchors import anchors_per_item
from .config import CASES_EXTRACTED, OUR_TEAM
from .db import connect
from .parse import ParseError, load_case

F_HAT = 0.186   # measured: acceptance rate on proven-fraud charges (n=54k)
N_OPP = 16
VARIANT = "anchored2"


def load_data():
    con = connect()
    est = {(r["game_id"], r["line_item"]): r["t_hat"] for r in con.execute(
        "SELECT * FROM estimates_v WHERE variant=?", (VARIANT,))}
    bands = {(r["game_id"], r["line_item"]): (r["t_lo"], r["t_hi"]) for r in con.execute(
        "SELECT * FROM item_bounds WHERE t_lo > 0 AND t_hi IS NOT NULL")}
    charges = [(r["game_id"], r["line_item"], r["a"]) for r in con.execute(
        "SELECT game_id, line_item, a FROM issuer_prices "
        "WHERE issuer != ? AND a IS NOT NULL AND a > 0", (OUR_TEAM,))]
    # per-item anchor evidence, leave-one-game-out
    anchor_info: dict[tuple, list[dict]] = {}
    games = sorted({g for g, _ in bands})
    for gid in games:
        d = CASES_EXTRACTED / f"game_{gid:03d}"
        if not d.is_dir():
            continue
        try:
            case = load_case(gid, d)
        except (ParseError, OSError):
            continue
        for idx, lst in anchors_per_item(case, exclude_game=gid).items():
            anchor_info[(gid, idx)] = lst
    return est, bands, charges, anchor_info


def b_policy(t_hat: float, anchors: list[dict], p: dict) -> float:
    if t_hat < p["b_split_lo"]:
        b = p["b_low"] * t_hat
    elif t_hat < p["b_split_hi"]:
        b = p["b_mid"] * t_hat
    else:
        b = p["b_high"] * t_hat
    top = [a for a in anchors if a["score"] >= p["anchor_min_score"]]
    if top:
        a0 = top[0]
        if a0["t_hi"] is not None:
            b = min(b, p["cap_mult"] * a0["t_hi"])     # proven-fraud ceiling nearby
        if a0["t_lo"]:
            b = max(b, p["floor_mult"] * a0["t_lo"])   # proven-fair floor nearby
    return b


def evaluate(est, bands, charges, anchor_info, p) -> tuple[float, float, float]:
    keys = [k for k in est if k in bands]
    income = 0.0
    for k in keys:
        lo, hi = bands[k]
        a = p["A"] * est[k]
        p_fair = 1.0 if a <= lo else 0.0 if a >= hi else (hi - a) / (hi - lo)
        income += N_OPP * a * (p_fair + (1 - p_fair) * F_HAT)
    cost = 0.0
    kset = set(keys)
    for g, i, a_opp in charges:
        if (g, i) not in kset:
            continue
        lo, hi = bands[(g, i)]
        p_fair = 1.0 if a_opp <= lo else 0.0 if a_opp >= hi else (hi - a_opp) / (hi - lo)
        b = b_policy(est[(g, i)], anchor_info.get((g, i), []), p)
        cost += a_opp if a_opp <= b else 1.5 * a_opp * p_fair
    return income, cost, income - cost


def main() -> None:
    est, bands, charges, anchor_info = load_data()
    print(f"items {len([k for k in est if k in bands])} · charges "
          f"{len([c for c in charges if (c[0], c[1]) in bands])} · anchored items {len(anchor_info)}")

    base = {"A": 0.85, "b_low": 1.5, "b_mid": 1.5, "b_high": 1.5,
            "b_split_lo": 150, "b_split_hi": 400,
            "anchor_min_score": 9.9, "cap_mult": 1.0, "floor_mult": 1.0}  # no anchor use
    inc, cost, net = evaluate(est, bands, charges, anchor_info, base)
    print(f"\ncurrent policy (global B=1.5, no anchor clamp, F-term on): "
          f"income {inc:,.0f} cost {cost:,.0f} NET {net:,.0f}")

    # A sweep with F-term
    print("\nA sweep (F=0.186):")
    for A in (0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.2):
        p = dict(base, A=A)
        inc, cost, net = evaluate(est, bands, charges, anchor_info, p)
        print(f"  A={A:<5} income {inc:>10,.0f}  NET {net:>10,.0f}")

    # value-dependent B + anchor clamp grid
    print("\npolicy grid (A fixed at best from above):")
    best = None
    for A in (0.9, 0.95, 1.0):
        for b_low in (0.9, 1.1, 1.3):
            for b_high in (1.5, 2.0, 2.5):
                for ams, capm, flom in ((0.5, 1.2, 1.0), (0.5, 1.0, 1.0), (9.9, 1.0, 1.0)):
                    p = dict(base, A=A, b_low=b_low, b_mid=1.5, b_high=b_high,
                             anchor_min_score=ams, cap_mult=capm, floor_mult=flom)
                    inc, cost, net = evaluate(est, bands, charges, anchor_info, p)
                    if best is None or net > best[0]:
                        best = (net, p, inc, cost)
    net, p, inc, cost = best
    print(f"  BEST: NET {net:,.0f} (income {inc:,.0f}, cost {cost:,.0f})")
    print(f"  params: A={p['A']} b_low={p['b_low']} b_mid={p['b_mid']} b_high={p['b_high']} "
          f"anchor_min_score={p['anchor_min_score']} cap={p['cap_mult']} floor={p['floor_mult']}")


if __name__ == "__main__":
    main()
