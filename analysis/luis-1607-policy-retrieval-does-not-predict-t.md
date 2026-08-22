# Retrieval over the policies does not predict `t` on its own

> **Corrected 16:31 UTC.** The first version of this measured BM25 alone
> and called it hybrid. With embeddings added the answer changes: retrieval
> still loses to the price book by itself, but **combining the two beats
> either alone.** The revised numbers are below; the original lexical-only
> ones are kept so the correction is legible.

**Written:** 22 Aug 2026, 16:07 UTC · leave-one-policy-out over 15 games, 215 line
items with a proven threshold · code on branch `luis-model`

I built a clause-level retriever over the policies to see whether the contract
wording could price a line item better than the price book. It cannot. Posting
the negative so nobody spends a day rediscovering it.

---

## The result

Corpus built **without** the policy under test, retrieve per line item, predict
`t` from the proven thresholds of training items that retrieved the same clauses.

Retrieval improves a lot once the dense half exists — `bge-small-en-v1.5`,
normalised cosine, no vector database because 591 clauses is a 591×384 matrix and
brute force finishes in under a millisecond:

| retriever | median log error |
| --- | ---: |
| BM25 only | 0.643 |
| BM25 + embeddings, α=0.5 | 0.632 |
| embeddings only | **0.564** |

**On its own it still loses to the price book. Combined with it, it wins:**

| | median | mean |
| --- | ---: | ---: |
| price book | 0.537 | 0.761 |
| dense retrieval | 0.564 | 0.751 |
| **both combined** | **0.528** | **0.669** |

The mean is where it shows — a 12% cut — so the gain is on the tail, not the
typical item. Modest, and real.

**The split inverted, against the hypothesis I argued for twice.** Retrieval wins
where the price book *knows* the trade (0.541 vs 0.558, 54% of items) and loses
badly where it does not (0.669 vs 0.516). It is not a long-tail signal. It is a
correction to a rate we already have.

Reading the sweep: the scored subset changes between configurations, because
which items have enough clause support changes with the retriever. Book against
retrieval *within one row* is on identical items and is fair; comparing a number
in one row to one in another is not.

There is no clause-level signal hiding under the average either. `7.1.8 Outlay
that is not a repair cost` is retrieved for catering and for hand tools, which is
correct, and the median threshold of items retrieving it is 150 against 200
overall — 0.75×, on nine items. Not a lever.

Error is in log space because `t` spans 100×; absolute error would be dominated
by the large items.

---

## Why, and this is the part worth keeping

**The original premise was still wrong, and the data said so before any of this.**

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

The interval model over observed thresholds is the bigger lever and it is already
being built. This does not compete with it — a 12% cut on the mean is worth
having, and it is an ADJUST-stage correction to an existing estimate, not a
replacement for one.

If anyone wires this in, the shape suggested by the split is: leave the price
book to set the level where it knows the trade, and let retrieval nudge it. Do
not let it price the long tail, which is where it is worst.

Two things from this work are worth keeping, and both are cheap:

- **The clause corpus.** 591 distinct clauses across 15 policies, content-addressed,
  so identical wording in nine policies is one entry that remembers all nine. It is
  the only structure that links policies across games. It converges, though less
  smoothly than I first claimed: games 4, 6 and 15 added nothing, game 10 added 84,
  and the last five policies averaged 14 new.
- **Coverage is still 3% worth having.** Retrieval finds the right clause for
  catering and hand tools. It just cannot price them.

All of it is on `luis-model` in `luismodel/`: `ingest.py`, `lexicon.py`,
`index.py`, `dense.py`, `eval.py`. Nothing is wired into the rule engine and
nothing in `c2f/` was touched. `sentence-transformers` is installed in the local
venv only and is deliberately not in `requirements.txt`.

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
PYTHONPATH=. .venv/bin/python -m luismodel.eval -k 3 --min-support 3            # lexical
PYTHONPATH=. .venv/bin/python -m luismodel.eval -k 3 --min-support 3 --dense --alpha 1.0
```

The second needs `pip install sentence-transformers`; the first needs nothing
beyond the project's own requirements.
