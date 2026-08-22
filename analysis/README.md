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

Say plainly when something is a guess. A finding that turns out to be wrong costs
us one experiment; a guess presented as a measurement costs us trust in the whole
folder.

## Where the data is

The results of every finished game are public and get copied into a local SQLite
file, so you can query them without touching the network:

```bash
PYTHONPATH=. .venv/bin/python tools/harvest.py --once    # catch up
PYTHONPATH=. .venv/bin/python tools/report.py            # last game, post-mortem
sqlite3 data/c2f.sqlite                                  # or just query it
```

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
