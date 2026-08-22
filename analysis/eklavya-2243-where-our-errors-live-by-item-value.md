# Our errors are value-dependent, and the two kinds live at opposite ends

**Written:** 22 Aug 2026, 22:43 UTC · 47 games played · all figures from
`data/c2f.sqlite` and `tools/thresholds.py`, no tournament round spent

For Luis, who is already anchoring on proven floors (`374c18d`, `57db99a`). This is
the same direction, with the euro structure measured, plus the two places I think it
can be sharpened. Nothing here needs an architecture change.

## 1. A wrong rejection costs 2.8x a wrong acceptance, and you are on the right side

Every reviewer decision we have made, classified against proven labels
(rejected-but-paid proves fair; rejected-and-unpaid proves fraud):

| decision | count | cost EUR | share | avoidable |
| --- | ---: | ---: | ---: | ---: |
| accept_fair (correct) | 1,613 | 250,828 | 22% | 0 |
| **accept_fraud** (wrong) | 967 | 195,991 | 17% | 195,991 |
| **reject_fair** (wrong) | 1,210 | **695,222** | **61%** | 231,741 |
| reject_fraud (correct) | 1,733 | 0 | 0% | 0 |

Per error: a wrong rejection costs **574.60**, a wrong acceptance **202.70**. Wrongly
rejecting fair charges is **61% of our entire reviewer cost**.

Your v2 window already reflects this. Per 1,000 labelled decisions:

| window | wrong-reject | buy-fraud | net/item |
| --- | ---: | ---: | ---: |
| ours, games 1-31 | 185 | 183 | -511 |
| games 32-41 (pre-v2) | 279 | 159 | -1,959 |
| **your v2, games 42-47** | **122** | 230 | -593 |

You have the lowest wrong-rejection rate of the three windows, bought with more fraud
purchases. At 574.60 against 202.70 that trade is correct, and it is the single
clearest improvement anyone has made today. 98 items over 6 games is a thin sample, so
treat -593 vs -511 as indistinguishable — the error *profile* is the real result.

## 2. Where each error lives: bucket by the item's proven floor

Our reviewer errors, bucketed by `t_lo` from `tools/thresholds.py`:

| item value (t_lo) | wrong-rejections | their cost | fraud bought | its cost |
| --- | ---: | ---: | ---: | ---: |
| 0-50 | 7 | 259 | **668** | **105,776** |
| 50-150 | 370 | 36,591 | 211 | 35,838 |
| 150-400 | 279 | 73,331 | 48 | 14,685 |
| 400-1200 | 459 | 281,099 | 40 | 39,692 |
| **1200+** | 95 | **303,941** | 0 | 0 |

The two failures are at **opposite ends**. Fraud purchases concentrate on cheap items
(105,776 of 195,991 in the bottom bucket alone). Wrong rejections concentrate on
expensive ones (585,040 of 695,222 in the top two buckets, at ~3,200 per error in the
top bucket).

So the acceptance limit wants to be a **function of item value**, not a global
quantile. Low on cheap items, high on expensive ones. A single global setting is
forced to be wrong at one end or the other, which is what the near-symmetric
185/183 in our own window actually was.

**Caveat, and it is the important one.** The apparent gain from raising `b` on the
1200+ bucket looks like +101,314, but that number priced the fraud we would start
buying at that bucket's observed fraud mean — which is zero, because we have never
accepted fraud there. Zero observations is not zero risk: rejected-fraud charges
record `amount = 0`, so their sizes are invisible. There are 1,079 such rows. That
figure is an **upper bound, not a result**, and any change that raises `b` needs the
`unpriced` count from `tools/score.py` reported next to it.

## 3. Your buy-fraud rate rose to 230/1000 — check which items

This is the one number I would look at next. Given the table above, fraud purchased on
a cheap item is the most expensive kind of mistake available. If your 230 concentrates
below `t_lo` 150, there is a self-contained rule already measured for it.

`rules_user/worthless_accept_guard.py`: when a majority of ensemble samples price an
item at **zero**, keep the charge and set the acceptance limit to zero. Charge high,
accept nothing.

Measured **+22,715 over 22 games, and it is exact rather than a bound** — lowering `b`
only converts acceptances into rejections, so it never runs into the invisible-amount
problem above. It needs `Verdict.accept_ceiling` (caps `b` alone, leaving `a`) and an
invariant that permits `b < a` only when a rule explicitly asks. That last part
matters: `b < a` by accident is what cost us -8,273.70 in game 1.

Two things that made the detector work, both of which cost us a day to find:

- **3 samples, not 1.** At one sample the same item flipped verdicts between runs. At
  three, precision reached 0.91. Cost is ~4.4s on a 39-item case.
- **The policy DIGEST in the item prompt, not the raw policy.** Raw policy text took
  53.9s and recall was 0.50; the digest took 24.5s and recall was 1.00.

## 4. Two facts about the issuer side that a valuation model can get wrong

**The 16x is real and uniform.** Verified across all 43 games at the time of writing:
every fair charge is settled by exactly 16 reviewers, with no variation in any game.
And rejecters genuinely pay — on 188 items where our charge is proven fair, all 16
reviewers paid on all 188, and there is no `(accepted=0, amount=0)` cell anywhere in
that population. One item was rejected by all 16 reviewers and paid by all 16.

So undercharging a fair line is a **16x** loss, and it never surfaces as an error
anywhere. It is the most expensive silent mistake in the game.

**An overcharge is not free, and it is not zero either.** Over 24 games and 25,984
reviewer decisions against proven-fraudulent charges, **17.5% were ACCEPTED at mean
374.69**. So `F(a) ~ 0.18`, not 0. Any scorer that credits zero above `t` will
systematically prefer timid estimates — that assumption is why I killed a three-model
ensemble recommendation earlier today.

But do NOT model income above `t` as growing linearly in `a`: it is capped by
`min(a, c)` with `c >= 4t`, and `F` must fall as `a` rises. I made that mistake this
evening and the optimiser cheerfully demanded 22x our own median.

## 5. How large the mispricing actually is, stated carefully

Comparing our charges to proven floors over all 43 games gives **948,928 EUR** of
foregone income across 188 items (the same method over the games 2-31 window, where
our event log lives, gives 639,330 — verified to the cent by an independent route that
never reads the event log).

Three caveats, because the headline invites two category errors:

- It is an **ex-post oracle bound, not an addressable gap**. The implied counterfactual
  income exceeds every real team's actual income, which is correct for an oracle and
  wrong as a target.
- The **raw per-item mispricing sums to only 39,958 EUR, median 97.47 per item.** The
  large number is that multiplied by 16 opponents. Both are right; quoting the big one
  next to a pricing discussion overstates how large the estimation miss is.
- **Heavy tail.** One item is 17.6% of the total, ten items are 49.1%, fifty are 86.6%.
  The actionable defect is magnitude detection on big-ticket items, not broad
  recalibration. Optimising the median item chases the wrong half.

The worst single case: we charged 199.25 on an item whose proven floor was 7,225.

## Reproduce

```
PYTHONPATH=. .venv/bin/python tools/thresholds.py --jsonl     # the only label source
PYTHONPATH=. .venv/bin/python tools/score.py --actual         # self-validating
```

`tools/thresholds.py` is the only sanctioned source of proven brackets — hand-rolled
SQL against `transactions` has produced an inverted answer twice. `tools/score.py`
reproduces realised scores to the cent; on the full harvested range it lands within one
game of the authoritative leaderboard, so it is trustworthy as long as the harvest is
current. Mine was 14 games stale earlier today and I read -163,687 when the real figure
was -430,982.

Charge and limit **sums are not euro impact** — a higher charge earns 16x when fair and
little when not.
