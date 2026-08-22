# Retrieval over the policies does not predict `t`

**Written:** 22 Aug 2026, 16:07 UTC · leave-one-policy-out over 15 games, 215 line
items with a proven threshold · code on branch `luis-model`

I built a clause-level retriever over the policies to see whether the contract
wording could price a line item better than the price book. It cannot. Posting
the negative so nobody spends a day rediscovering it.

---

## The result

Corpus built **without** the policy under test, retrieve per line item, predict
`t` from the proven thresholds of training items that retrieved the same clauses:

| | median log error | closer on |
| --- | ---: | ---: |
| price book | **0.485** | 56% |
| clause retrieval | 0.632 | 44% |

Worse than the book, and worse than a coin flip. Stable across `k ∈ {1,3,5}` and
minimum clause support `∈ {2,3,5}`: retrieval lands between 0.57 and 0.68 and
never reaches 0.485.

**The split that was supposed to rescue it kills it instead.** Where the price
book has no rate for the trade — the long tail a new signal exists to serve —
retrieval scores 0.677 against the book's 0.485 and wins 40% of the time. It is
worst exactly where it was meant to help.

There is no clause-level signal hiding under the average either. `7.1.8 Outlay
that is not a repair cost` is retrieved for catering and for hand tools, which is
correct, and the median threshold of items retrieving it is 150 against 200
overall — 0.75×, on nine items. Not a lever.

Error is in log space because `t` spans 100×; absolute error would be dominated
by the large items.

---

## Why, and this is the part worth keeping

**The premise was wrong, and the data said so before the experiment did.**

`t = 0` on **6 of 221 line items — 3%.** Coverage is almost the whole of what a
policy decides, and it is 3% of the problem. What `t` actually does is spread:

| p10 | p25 | p50 | p75 | p90 | p99 | max |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 63 | 108 | 200 | 410 | 703 | 2,094 | 7,225 |

A policy does not say what a square metre of laminate costs. It says whether
something is paid and on what basis — and almost everything is paid. The task is
the *level*, and the level lives in the trade, the quantity and the market, none
of which are in the contract.

I should have checked the 3% before building the retriever, not after. The query
is four lines of SQL against `data/c2f.sqlite`.

---

## What this says about where effort goes

The interval model over observed thresholds is the right lever and it is already
being built. Nothing here competes with it.

Two things from this work are worth keeping, and both are cheap:

- **The clause corpus.** 591 distinct clauses across 15 policies, content-addressed,
  so identical wording in nine policies is one entry that remembers all nine. It is
  the only structure that links policies across games. It converges, though less
  smoothly than I first claimed: games 4, 6 and 15 added nothing, game 10 added 84,
  and the last five policies averaged 14 new.
- **Coverage is still 3% worth having.** Retrieval finds the right clause for
  catering and hand tools. It just cannot price them.

Both are on `luis-model` in `luismodel/`. Nothing is wired into the rule engine
and nothing in `c2f/` was touched.

---

## Caveat I do not want buried

The target is a **lower bound** on `t`, never `t` itself — we can only prove
`t >= floor`. Both methods are scored against the same biased target, so the
comparison between them is fair. The absolute numbers are not accuracy, and
should not be quoted as such.

## Reproduce

```bash
git checkout luis-model
PYTHONPATH=. .venv/bin/python -m luismodel.ingest --build
PYTHONPATH=. .venv/bin/python -m luismodel.eval -k 3 --min-support 3
```
