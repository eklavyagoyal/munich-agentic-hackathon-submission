"""Bracket the secret threshold `t` for every line item we have results for.

    PYTHONPATH=. .venv/bin/python tools/thresholds.py                # the table
    PYTHONPATH=. .venv/bin/python tools/thresholds.py --jsonl        # rows for modelling
    PYTHONPATH=. .venv/bin/python tools/thresholds.py --game 4       # one game

Reads only `data/c2f.sqlite`, which tools/harvest.py fills. No network, no writes.

WHY THIS EXISTS SEPARATELY FROM harvest.py

harvest.py stores what the API said. This turns that into the one quantity every
model needs, using a rule that is easy to get backwards -- and getting it
backwards produces a confident, inverted answer. So it lives in exactly one place
and both the analysis folder and c2f/calibrate.py read it from here.

THE LABEL RULE (docs/MODEL_BRIEF.md §5a)

`amount` is what the ISSUER was paid, not what it charged. Read against the payoff
matrix, a rejection is therefore an exact classifier:

    rejected AND paid    -> only possible in the fair column (I pays 1.5a, H gets a)
                            => that charge was <= t
    rejected AND unpaid  -> only possible in the fraud column (nothing flows)
                            => that charge was > t
    accepted             -> says a <= b for THAT reviewer. Nothing about t alone.

So per line item:

    t >= max(charges proven fair)
    t <  min(charges proven fraudulent, where we can see their size)

The lower bound is exact: a fair charge is paid by every reviewer, so its `amount`
IS the charge. The upper bound is only visible when somebody ACCEPTED a
fraudulent charge, because a rejected fraud pays nothing and hides its own size.
That asymmetry is why lower bounds are common here and upper bounds are not.

Bounds get tighter as the field bids more aggressively. An item where nobody
rejected anything yields no label at all -- that is expected, not a bug.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "c2f.sqlite"

INF = float("inf")


@dataclass
class Bracket:
    game: int
    item: int
    lo: float = 0.0          # t >= lo, from the largest charge proven fair
    hi: float = INF          # t <  hi, from the smallest fraud charge we can size
    n_fair: int = 0
    n_fraud: int = 0
    fair_charges: list[float] = field(default_factory=list)

    @property
    def labelled(self) -> int:
        return self.n_fair + self.n_fraud

    @property
    def bounded(self) -> bool:
        return self.hi != INF

    def as_row(self) -> dict:
        return {"game": self.game, "item": self.item,
                "t_lo": round(self.lo, 2),
                "t_hi": None if self.hi == INF else round(self.hi, 2),
                "n_fair": self.n_fair, "n_fraud": self.n_fraud,
                "fair_charges": sorted(round(c, 2) for c in self.fair_charges)}


def brackets(con: sqlite3.Connection, game: int | None = None) -> list[Bracket]:
    q = "select game_id,issuer,line_item,accepted,amount from transactions"
    args: tuple = ()
    if game is not None:
        q += " where game_id = ?"
        args = (game,)

    # First decide, per (game, item, issuer), which side of t that issuer's charge
    # fell on. One issuer is reviewed by every other team, so several rows speak
    # about the same charge; a single rejection is enough to classify it.
    @dataclass
    class Charge:
        fair: bool | None = None
        paid: float = 0.0
        accepted_amounts: list[float] = field(default_factory=list)

    per: dict[tuple[int, int, str], Charge] = defaultdict(Charge)
    for game_id, issuer, item, accepted, amount in con.execute(q, args):
        c = per[(game_id, item, issuer)]
        if accepted:
            c.accepted_amounts.append(amount)
        elif amount > 0:
            c.fair = True                     # rejected yet paid => a <= t
            c.paid = max(c.paid, amount)      # and that payment IS the charge
        else:
            c.fair = False                    # rejected, nothing flowed => a > t

    out: dict[tuple[int, int], Bracket] = {}
    for (game_id, item, _issuer), c in per.items():
        b = out.setdefault((game_id, item), Bracket(game_id, item))
        if c.fair is True:
            b.n_fair += 1
            b.fair_charges.append(c.paid)
            b.lo = max(b.lo, c.paid)
        elif c.fair is False:
            b.n_fraud += 1
            # A rejected fraud pays nothing, so its size is invisible. Only an
            # ACCEPTED fraudulent charge reveals how big it was, and since a > t
            # there, it is a genuine upper bound.
            sized = [a for a in c.accepted_amounts if a > 0]
            if sized:
                b.hi = min(b.hi, min(sized))
    # An item whose every charge was accepted yields no label: acceptance speaks
    # about the reviewer's limit, never about t. Drop those rather than print a
    # row of zeros that reads like "t is 0".
    return [out[k] for k in sorted(out) if out[k].labelled]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", type=Path, default=DB)
    p.add_argument("--game", type=int, default=None)
    p.add_argument("--jsonl", action="store_true", help="one JSON row per line item")
    a = p.parse_args()

    if not a.db.exists():
        print(f"no {a.db} -- run tools/harvest.py --once first")
        return 1
    con = sqlite3.connect(a.db)
    bs = brackets(con, a.game)
    if not bs:
        print("no labelled line items yet. A label needs a rejection; if every "
              "charge was accepted, there is nothing to infer.")
        return 0

    if a.jsonl:
        for b in bs:
            print(json.dumps(b.as_row()))
        return 0

    print(f"{'game':>4} {'item':>4} {'t >=':>10} {'t <':>10} {'fair':>5} {'fraud':>6}")
    for b in bs:
        hi = f"{b.hi:10.2f}" if b.bounded else "         -"
        print(f"{b.game:>4} {b.item:>4} {b.lo:>10.2f} {hi} {b.n_fair:>5} {b.n_fraud:>6}")

    both = [b for b in bs if b.bounded and b.lo > 0]
    zeroish = [b for b in bs if b.lo == 0.0 and b.bounded]
    print(f"\n{len(bs)} labelled line items, {len(both)} with both bounds")
    if zeroish:
        print(f"{len(zeroish)} have t below {max(b.hi for b in zeroish):.2f} with no fair "
              f"charge seen -- candidates for t = 0, i.e. not covered by the policy")
    if both:
        widths = [(b.hi - b.lo) / b.lo for b in both]
        print(f"bracket width, median: {sorted(widths)[len(widths)//2]:.0%} of the lower bound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
