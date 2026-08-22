# The whole error is the `unknown` bucket, and it is provably 3x too high

**Written:** 22 Aug 2026, 16:58 UTC · 15 opened games, thresholds from
`tools/thresholds.py`, estimates from `c2f.estimate.pricebook.lookup`

Asked whether a stronger model would price better. I cannot test that here — no
model key on this machine — so instead: where is the error, and is there room?

Both answers are sharp.

## Where the price book is good, it is very good

Median absolute log error against the proven lower bound, by matched trade:

| trade | n | median log error |
| --- | ---: | ---: |
| leak | 8 | 0.086 |
| generic | 14 | 0.169 |
| services | 13 | 0.366 |
| electronics | 6 | 0.414 |
| drying | 12 | 0.843 |
| **unknown** | **89** | **0.938** |

`unknown` is 63% of the items that have a proven bound and carries roughly eleven
times the error of `leak`. Everything else is a rounding difference next to it.

## And in that bucket we are provably overcharging

Not inferred from the lower bound — measured against the **ceilings**, which come
from rejected-and-unpaid rows and prove `a > t`:

```
estimate above the proven ceiling   85     median 3.0x too high, max 694x
estimate below the proven floor     29
inside the proven interval           4
```

Eighty-five items where being too high is a fact, not a suspicion. A charge above
`t` is paid by nobody, so each of those earned exactly zero.

## Why a price book cannot fix this

Eighty-nine `unknown` items carry **eighty-one distinct descriptions**. There is
almost no repetition, and each new game brings new ones:

```
Clean / dry conservatory rug
Inspect plant-room electrical systems
Restore wall surfaces
Replacement copper pipe section and transition fittings
Floor console (equivalent stand for the living-room ...)
```

Enumerating rates for an open vocabulary is not a maintenance task anyone wins.
This is the case a language model is actually for: read the line, estimate the
job. So yes — there is real headroom for a better model, and it is 63% of the
items rather than a long thin tail.

## But there is a free fix first, and it needs no model at all

The overcharge is systematic, not random: 85 above the ceiling against 29 below
the floor. Dividing the `unknown` fallback by about 3 would move most of those
85 items inside their proven interval, at the cost of some of the 29.

Worth doing before spending anything on inference. It is also the honest reading
of what the numbers support: they prove the current level is too high, they do not
prove any particular replacement is right.

## What I got wrong on the way here, and the check that caught it

My first pass measured against `t_lo` alone and concluded "1.5x too high". `t_lo`
is a **lower** bound; sitting above it can be perfectly correct. That is the same
error Eklavya corrected in my retrieval note an hour ago, so I checked against the
ceilings before writing anything down. The conclusion survived and got stronger —
3.0x rather than 1.5x — but it survived because it was checked, not because the
first number was right.

## Caveats

- `drying` at 0.843 on twelve items is nearly as bad as `unknown` and is a matched
  trade. Worth a separate look; a rate that exists is not a rate that is right.
- The 694x outlier is one item and may be a parse artefact rather than a pricing
  error. The median of 3.0x is the number to act on.
- Ceilings exist only for items somebody was rejected-and-unpaid on. Items nobody
  ever overcharged carry no ceiling and are absent from the 85/29/4 split.

## Reproduce

```bash
PYTHONPATH=. .venv/bin/python tools/thresholds.py --jsonl
```

Join to `c2f.estimate.pricebook.lookup` per line item from `data/open/game-NNN/`,
group by `match_rate(item).trade`.


---

## Priced, and it inverts (Eklavya, 17:00 UTC)

**Do not ship this. Lowering the unknown band measures -83,647.37 over 17 games.**

Your arithmetic is exact -- I reproduced all six trade medians and the 85/29/4 split
to three decimals. The problem is the metric: every number here is a count or an
unweighted median, so a 57.30 charge on an item worth 620 counts the same as a 21.98
charge on an item worth 9. Euro-weighted, the band is **too low**, not 3x too high.

Two things the item-count view hides:

**48 of the 85 "above the ceiling" items (56%) have `t_lo == 0`**, median ceiling
26.00. Those are worth nothing, so *any* positive price is above their ceiling and no
band can fix them -- they belong to the worthless-item work, not to band tuning. Your
headline 694x outlier is one of them: game 17 item 10, `t < 1.26`. Not a parse
artefact, just t = 0. Strip those and it is 37 above vs 29 below: a wash.

**The tail runs the other way.** Proven un-earned income in the unknown bucket at the
CURRENT band is `16 x sum(t_lo - a)` = **+289,627**. The best conceivable recovery
from the too-high side is 75,542, and only if each item could be priced at its own
ceiling, which one global band cannot do.

Measured, `tools/backtest.py --promote` with the band patched in memory, scored with
`tools/score.py`:

| | insurer | handyman (proven) | combined |
| --- | ---: | ---: | ---: |
| game 8 | -3,004 | -10,112 | -13,117 |
| game 15 | -3,715 | -20,448 | -24,163 |
| game 17 | -6,856 | -27,694 | -34,551 |
| all 17 games | **-16,554** | **-67,093** | **-83,647** |

Games 17, 15 and 8 are 86% of the loss. The handyman side is exact in this direction:
lowering `a` cannot move a proven-fair charge off the proven-fair side, so there are
no indeterminate rows and no offsetting upside.

**On the tail specifically.** Game 10 item 3, 92% of that round's cost, `t >= 7,225`,
with 12 of 16 issuers making provably-fair charges summing 40,818. At today's band we
accept 1 of 12. At your band we accept 0 of 12, and our own charge on work worth at
least 7,225 falls from 176.75 to 58.92. Monotonically wrong on both sides at once.

**What survives, and it is the useful half.** `drying` at 0.843 over 12 items is a
MATCHED trade almost as bad as the fallback -- that is a real finding and not about
the band. And your open-vocabulary point is right: 142 unknown items across 122
distinct descriptions, so no keyword table closes this. "A model should read the line"
is the correct conclusion. Only "the free fix first" is wrong.

**Direction, for the record:** band x2 measures +19,229 insurer-side and +37,670
handyman-side. Not shippable as measured -- raising `b` puts 706 invisible
rejected-fraud charges in play, which `tools/score.py` reports as `unpriced` and which
makes any positive figure an upper bound. But the gradient points UP. The `pauschal`
band is where I would look first: 54 unmatched items all priced at 57.30 with qty 1,
against proven `t` of 620, 508.72, 460 and 150 in game 17 alone.
