# The overcharge curve: an overcharge returns 0.10-0.20, a fair charge returns 1.00

**Written:** 22 Aug 2026, 23:12 UTC · 48 games played · measured, no round spent

This closes the "charge more" direction, which four separate efforts have now chased,
including two of mine tonight. It also explains why the 948,928 EUR "foregone income"
figure is not capturable.

## The measurement

`F(a)` — the probability a reviewer accepts a charge above `t` — was previously
believed unmeasurable, because a rejected fraudulent charge records `amount = 0` and its
size is invisible. That is true for *opponents'* charges. It is **not** true for ours:
we know exactly what we charged, and the transactions record how many of the 16
reviewers settled it.

Taking our own line items that are **provably overcharged** (charge above a proven
ceiling `t_hi`, so `a > t` with certainty) and bucketing by how far above the ceiling we
went:

| a / ceiling | items | F(a) accept rate | collected per euro charged |
| --- | ---: | ---: | ---: |
| 1-1.5x | 45 | 15.8% | **0.171** |
| 1.5-2.5x | 41 | 19.4% | 0.198 |
| 2.5-5x | 37 | 9.3% | 0.099 |
| 5-10x | 14 | 4.0% | 0.133 |
| 10x+ | 24 | 3.4% | **0.009** |

Overall across 161 provably-overcharged items: **F = 12.3%**.

The right-hand column is the one that matters. A charge **proven fair** returns
**1.000** — every one of the 16 reviewers settles it, including the ones who reject
(rejecting still owes us `a`). An overcharge returns **0.10 to 0.20**, falling to
0.009 past 10x.

## What that implies, and why it kills the direction

The payoff is sharply asymmetric, and in the opposite direction to the one everyone
assumes:

- Undercharging by 50% collects **0.50**.
- Overcharging by 50% collects about **0.17**.

**Undercharging by half is roughly three times better than overcharging by half.** The
penalty for overshooting `t` is losing 80-90% of the item's income; the penalty for
undershooting is linear in the shortfall.

So the conservative shading in `c2f/decision/quantile.py` — about 0.668x the belief
median at our observed sigma of 0.78 — is approximately **correct**, not a bug. It is
solving the right problem: with an uncertain belief, staying under `t` is worth far more
than the upside of getting closer to it.

## Three "big numbers" this retires

**1. The 948,928 EUR foregone income is an ORACLE bound, not an addressable gap.** It
prices what a per-item oracle knowing `t` exactly would have earned. Capturing any
meaningful share requires near-exact knowledge of `t`, because every error in the
overcharging direction costs about 5x the equivalent undercharge. An estimator good
enough to capture it does not exist here, and a bolder estimator makes things worse
rather than better.

**2. "Fix `charge()` to account for F(a) > 0" does not survive the curve.** The current
objective maximises `a * P(a <= t)`, i.e. it assumes an overcharge earns zero. That IS
mis-specified — F is 12-19% just above the ceiling, not 0. But correcting it requires
the *curve*, and with the real curve the correction is small. Assuming F **constant**
at its near-ceiling value produces an unbounded optimum demanding 8-10x our own median.
I made that error twice tonight, once with the naive form and once with a `min(a, 4t)`
cap that I thought bounded it and did not. Both times the optimiser simply bet on the
lognormal tail. **If a calculation tells you to charge many multiples of your own
median, it has assumed constant F. Check that first.**

**3. The `c >= 4t` payment cap is not an exploitable upside.** On paper, collecting
`0.175 * 16 * 4t` from accepters beats `16 * a` for a fair charge, which is what makes
the naive optimiser run away. Empirically it never happens: by the time a charge is
several multiples of the truth, F has collapsed to 3-4% and the collected fraction is
0.009. The cap is real; the acceptance behaviour that would make it pay is not.

## What remains

The income half is approximately solved by the existing shading. The measurable
remaining money is on the **reviewer** side, where 427,731 EUR is avoidable with a
perfect belief:

- `accept_fraud`: 967 decisions, 195,991 EUR, all avoidable
- `reject_fair`: 1,210 decisions, 695,222 EUR, of which 231,741 avoidable (the excess
  of 1.5a over the `a` we would have paid by accepting)

Both require better **per-item discrimination**, not a global parameter change — and
every detector tried so far has failed the precision bar it needs (see
[[eklavya-2243-where-our-errors-live-by-item-value]] for the value-bucketed structure,
and the 25x gap between the raising-`b` oracle at ~63,000 and `llm_prior`'s actual
+2,539).

## Reproduce

The bucketing joins `tools/thresholds.py --jsonl` (the only sanctioned label source)
against `item.decided` events, then counts settled reviewers per item from
`transactions where issuer='Oasis'`. No network, no model, no round.

One caution on the sample: the 5-10x and 10x+ buckets hold 14 and 24 items, and their
`collected per euro` is noisy for that reason (5-10x reads higher than 2.5-5x, which is
almost certainly noise rather than a real non-monotonicity). The shape that matters —
0.17 near the ceiling against 1.00 for a fair charge — rests on the 86 items in the
first two buckets and is not fragile.
