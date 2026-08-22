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


---

## Checked against the transactions (Eklavya, 16:17 UTC)

**The negative holds. Two of the numbers behind it do not, and one of them would
close the most valuable direction we have.**

**`floors()` is inverted.** It takes `MAX(amount) GROUP BY game_id, line_item
HAVING MAX(amount) > 0` without filtering on `accepted`. A lower bound on `t` comes
only from a **rejected-and-paid** row; an **accepted** row with a positive amount is
a charge somebody let through, and when that charge was fraudulent it proves
`a > t` -- an *upper* bound. So upper bounds are being fed in as lower bounds.
Measured: 217 rows, of which only 142 are correct floors; 75 items take their target
purely from accepted rows and 86 more are inflated above their true floor. 161 of 217
(74%) carry a wrong target, and the contamination is one-directional, which is why
the percentiles read 108/200/410 against the true 58/130/357.

Your caveat -- both arms scored against the same biased target -- does rescue the
*ranking*, so "clause retrieval loses to the price book on the level of `t`" stands
and nothing here contradicts it. But 0.632, 0.485, 44%, 0.677 and 40% are not
measurements of anything and should not be quoted.

**The "3%" is a set-difference artifact, and it is wrong by 10x.** 221 is
`tools/thresholds.py`'s labelled count; 215 was `floors()`'s. Subtracting two
incompatible item sets is what produced 6. `HAVING MAX(amount) > 0` silently drops
exactly the zero-value items, so they read as absent rather than as `t = 0`.

Ground truth, straight from the tool's own summary line:

```
221 labelled line items, 86 with both bounds
75 have t below 176.00 with no fair charge seen -- candidates for t = 0
```

79 of 221 items (36%) have `t_lo == 0`, 75 of them bounded, with a hard ceiling of
`t < 176` and a median ceiling of 38.25. Coverage is about a third of the labelled
items, not 3%.

That matters because the worthless class is currently our best measured lever:
keeping the charge and zeroing the acceptance limit on those items is **+14,575.16**
over 15 games, exactly measured. Please do not let the 3% paragraph close it.

**What your work does give us, and it is genuinely useful:** those 75 items are a
labelled validation set for the worthless-item detector, from the opposite direction
to the one I had. My evidence was game 8 -- items the model priced at zero had
proven `t < 84, < 1, < 1, < 1` while items it priced were all `t >= 400`. Your set
says the proven-worthless population never exceeds 176. Two independent reads of the
same boundary.

**Reproduce is broken too:** `luismodel/eval.py` hardcodes `data/open/game-NNN`,
which does not exist here (`data/cases/case-NN`), so `items_for()` returns empty and
the published command exits at "need at least three parseable games".

**Suggested edit:** keep the negative and its conclusion, strike the percentile table
and the 3% paragraph, and change `floors()` to `WHERE accepted = 0 AND amount > 0`
before any of its numbers are cited again.

Your own closing line is the right one -- "I should have run that query before
building the retriever." The sting is that the query already existed and was already
correct in `tools/thresholds.py`; a second hand-rolled SQL target was written instead
of calling `brackets()`, and that is exactly where the inversion got in.
