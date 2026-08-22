# Recommendation: three models in parallel, median, text only

**Written:** 22 Aug 2026, 17:25 UTC · 21 finished games, 272 line items with a
proven interval · code on branch `luis-model`, nothing wired into `c2f/`

Ready to implement and test. One thing in it goes against what was asked, and the
numbers for both are below so the call is yours.

---

## The configuration I recommend

Three models, **called in parallel**, take the **median** of their three
estimates per line item.

| | model | median call |
| --- | --- | ---: |
| 1 | `gpt-4.1-mini` | 3.9 s |
| 2 | `gpt-5.4-mini` | 2.1 s |
| 3 | `gpt-5.6-terra` | 3.5 s |

Parallel, so wall clock is the slowest call, not the sum: **about 6 s of a
60-second window**, worst observed 11.2 s.

Prompt: damage description + the parsed invoice lines. Ask for `t`, the fair
value, and nothing else — the bid follows from `t` by arithmetic the rule engine
already does correctly.

### What it buys

| | above ceiling | expected EUR | burned |
| --- | ---: | ---: | ---: |
| price book today | 145 | 383,332 | 4,847,882 |
| best single model | 47 | 392,928 | 156,400 |
| **ensemble, median** | **48** | **420,720** | 228,640 |
| ensemble, min | 21 | 279,904 | 69,440 |

**+9.8% expected revenue over the price book, with 97 fewer line items priced
above a proven ceiling.**

`min` is the other sensible choice if the appetite is different: it cuts items
above a ceiling from 145 to 21 — a sixth of the risk — at a third less expected
revenue. That trade is a judgement call, not a measurement.

---

## The part that contradicts the brief

I was asked to include everything: policy, invoice, description, photo. I built
the photo path and tested the full combination. **It is worse on every axis.**

| ensemble, median | above | expected EUR | burned |
| --- | ---: | ---: | ---: |
| description + invoice only | **48** | **420,720** | **228,640** |
| + policy + photo | 63 | 398,608 | 448,544 |

Fifteen more items above a ceiling, 22k less expected revenue, nearly twice the
volume staked on charges that earn nothing.

Every extra input tested did the same thing, individually and together:

| variant | expected EUR | burned |
| --- | ---: | ---: |
| base | 392,928 | 156,400 |
| + calibration anchors in the prompt | — | 252,960 |
| + policy text | — | 249,440 |
| + photo | — | 304,272 |

They make the model **bolder, not better**. It bids higher, collects a little
more where it was right, and stakes far more where it was wrong. My reading: the
extra context reads as licence to be generous rather than as evidence, and the
task does not actually need it — the invoice line already says what the work is,
and the policy governs *whether* something is paid rather than *what a trade
charges*.

So my recommendation is text only. If you want the photo in anyway, `--image`
exists and the numbers above are what to expect.

---

## Why the ensemble beats a better model

It is not averaging away noise. The payoffs are asymmetric: a charge at or below
`t` is paid by **every** opponent, and a charge above `t` is paid by nobody. So a
disagreement between models is a warning, and the lower estimate is the one that
still earns. The median exploits that; `min` exploits it harder.

That is also why a newer model did not help. Benchmarked across the current
families:

| model | above | expected EUR | burned | sec |
| --- | ---: | ---: | ---: | ---: |
| gpt-4.1-mini | 47 | 392,928 | 156,400 | 3.9 |
| gpt-5.4-mini | 52 | 378,320 | 339,264 | 2.1 |
| gpt-5.6-terra | 61 | 349,688 | 401,840 | 3.5 |
| gpt-5.6-luna | 75 | — | 565,488 | 3.5 |
| gpt-5.4-nano | 110 | — | 821,680 | 1.9 |

`gpt-4.1-mini` is the oldest of these and the best at this. `gpt-5.6-luna` burns
3.6× as much. `gpt-5` at `medium` effort takes ~33 s per game and is out on
latency regardless.

---

## How to wire it in

It belongs at `PRIOR`, above `pricebook_prior`, abstaining when the call fails
or returns nothing — then the price book takes over exactly as it does today.

The call must happen **off the hot path**, in the prefetch that `Context.prefetch`
already exists for, so the rule stays a pure lookup and the 50 ms sandbox timeout
is never in danger.

```
rules_user/luis_ensemble_prior.py   the rule: pure lookup into prefetch
luismodel/price.py                  one call per invoice, structured output
luismodel/ensemble.py               the combination rules and their scoring
luismodel/bench.py                  scoring against proven intervals
```

Degradation is already the same shape as the rest of the system: no key, a failed
call or an empty response all abstain, and the price book answers. Nothing here
can raise into a round.

---

## Caveats

- **`expected` is the column to read, and my earlier claims overstated.** On
  `proven` the model looked 51% better than the price book; `proven` counts only
  certainties and the book's high estimates land in the undecided middle far more
  often. On expected revenue the single-model gain is +2.5%, and the ensemble's
  is +9.8%. The large, real difference is risk, not revenue.
- Items between floor and ceiling are counted at **0.5**. That is an admission
  that we do not know, not a measurement.
- 21 games. Enough to rank these options, not enough to trust the third digit.
- The estimates are cached per model and game under `data/luismodel/bench`, so
  re-scoring a different combination rule costs nothing and needs no API calls.

## Reproduce

```bash
PYTHONPATH=. .venv/bin/python -m luismodel.bench \
    --models gpt-4.1-mini,gpt-5.4-mini,gpt-5.6-terra
PYTHONPATH=. .venv/bin/python -m luismodel.ensemble
```

Needs `OPENAI_API_KEY` in `.env` and `pip install openai`.
