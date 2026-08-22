# analysis/

Findings go here. **This folder is the contribution surface for everyone except
Eklavya** — see [CLAUDE.md](../CLAUDE.md) for why.

Nothing in here is imported by the code. You cannot break a round by writing a
file in this folder, which is the point: write freely, during a game, without
checking with anyone.

## One file per finding

Named `<your name>-<time UTC>-<topic>.md`, as set out in [CLAUDE.md](../CLAUDE.md):

```
analysis/luis-1432-flooring-rates.md
analysis/eklavya-1510-who-rejects-what.md
```

After midnight UTC, put the day in front: `luis-0823-0140-overnight-drift.md`.
Never edit someone else's file — write your own and link to theirs.

## What to put in it

Whatever makes the finding checkable. Roughly:

- **What you found**, in one sentence, at the top.
- **The evidence.** Numbers, the query you ran, the game and line item.
- **What it implies we should do** — a rate, a rule, a threshold. If you are not
  sure, say so; a well-evidenced observation with no conclusion is still useful.
- **How confident you are, and from how many games.** Two games is a hint. Twenty
  is a fact. Say which one you have.

**Get threshold targets from `tools/thresholds.py`, never from your own SQL.** The
fair/fraud rule is one line long and inverts silently if you get it backwards: a
lower bound on `t` comes only from a REJECTED-and-paid row, while an ACCEPTED row
with a positive amount can be a fraudulent charge somebody let through, which is an
upper bound. A hand-rolled `MAX(amount)` query that omits `accepted = 0` has already
produced a finding in this folder where 74% of the targets were wrong and one
conclusion was off by 10x. `brackets()` in that module is importable.

**Do not quote invoice, policy or damage-description text.** Refer to a line item
by game and index -- `tools/thresholds.py` identifies any item by its proven
bracket without reproducing a word of it. Checked-in claim data is a ranking
penalty (Discord, 14:35), and this folder is in the repo that goes public. Eleven
verbatim phrases have already had to be redacted from five files.

Say plainly when something is a guess. A finding that turns out to be wrong costs
us one experiment; a guess presented as a measurement costs us trust in the whole
folder.

## Where the data is

The results of every finished game are public and get copied into a local SQLite
file, so you can query them without touching the network:

```bash
PYTHONPATH=. .venv/bin/python tools/harvest.py --once    # catch up
PYTHONPATH=. .venv/bin/python tools/report.py            # last game, post-mortem
PYTHONPATH=. .venv/bin/python tools/thresholds.py        # what t was, per line item
sqlite3 data/c2f.sqlite                                  # or just query it
```

`thresholds.py` applies the label rule below so you do not have to. It prints
`t >= x, t < y` per line item, and `--jsonl` gives you rows to model on. If you
are about to write the rule yourself in a query, use this instead -- one wrong
sign here inverts the conclusion.

Tables: `games`, `scores` (per game per team), and `transactions` — one row per
line item per pairing, with `issuer`, `reviewer`, `accepted` and `amount`.

**`amount` is what the issuer was _paid_, not what they charged.** Getting this
backwards inverts your conclusion, so read §5a of the brief before you query.

> Those two tools currently live on the `analysis-tooling` branch, pending
> review. Until it is merged: `git checkout analysis-tooling -- tools/harvest.py
> tools/report.py`.

## The one thing worth understanding first

Read §5a of [docs/MODEL_BRIEF.md](../docs/MODEL_BRIEF.md) first. It shows that
`rejected AND paid` proves the charge was fair (`a ≤ t`) while `rejected AND
unpaid` proves it was fraud (`a > t`) — an exact label, not an estimate.

`accepted` on its own tells you about that reviewer's limit `b` and nothing about
`t`. Anyone who treats `amount` as a charge and `accepted` as a verdict on
fairness will produce a confident, wrong answer. That has already happened once
in this repo.
