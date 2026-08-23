# Claim audit of the submission documents: four claims hold, two overstate

**Written:** 23 Aug 2026, 10:01 UTC · all 100 games in `data/c2f.sqlite` · no round spent

The repo is now a judged artifact rather than a runner, so every number a judge can read
was re-derived from the final database. Four of the load-bearing claims are true and
stronger than they read. Two overstate, and both would be easy for a judge to falsify
from the public transaction feed — which is the reason to fix them rather than leave them.

## Verified true

| claim | where | verified |
| --- | --- | ---: |
| Issuer income since game 84 is **1st of 17** | `pipeline/docs/SUBMISSION.md:52` | **570,843** vs Codacabana 516,654 |
| Lowest reviewer cost paid, games 84–100 | same line | **291,759**, next is Bin busy 293,688 |
| Final rank 9/17, net −356,834 | both docs | exact, `scores` over games 1–100 |
| 13 of 14 positive, +575.5k (games 87–100) | same line | **+575,514**; the one negative is game 94 (−3,296) |

The issuer-income result is the single most defensible thing we have: **1st of 17 over the
triple-weighted stretch**, on the half of the game we spent the whole tournament failing
at. It deserves to be stated more prominently than the two claims below.

## Overstated 1: "PaidRate 63,8 % (Feldbestwert)"

`pipeline/docs/SUBMISSION.md:64`. The **number is right**; the **ranking is not**.

63.8% is our paid-rate over games 87–100 (I measure 64.1% — close enough that this is
clearly the intended window). But it is not the field best in that window, or any window:

| window | Oasis | rank | field best |
| --- | ---: | ---: | --- |
| 87–100 | 64.1% | **5 / 17** | Claims Renaissance 74.1% |
| 84–100 | 59.0% | 5 / 17 | TakeTheMoneyAndRun 68.1% |
| 81–100 | 48.0% | 11 / 17 | TakeTheMoneyAndRun 68.0% |
| 1–100 | 47.9% | 7 / 17 | TakeTheMoneyAndRun 57.3% |

`TakeTheMoneyAndRun` beats us on paid-rate over the whole tournament and over most
sub-windows. Drop the word *Feldbestwert*; the figure survives on its own.

## Overstated 2: "Bestwert bei gekauftem Fraud"

Same line. Bought fraud over games 84–100, joining `tools/thresholds.py --jsonl` (the only
sanctioned label source) against accepted transactions where the charge exceeds a proven
ceiling `t_hi`:

- **Oasis: 8,457 EUR over 107 items — 5th of 17.**
- Three teams score exactly 0 because they accepted *nothing* (OPUSMOPUS, harissa eagles,
  makalu — final net −1.9M, −2.3M, −4.1M). Their zero is a symptom, not an achievement.
- Bin busy is genuinely lower at 5,796.

So the true claim is **"2nd-lowest among the fourteen teams that accept anything, at a
third of the field median"** — still good, and it does not invite the obvious rebuttal
that three teams beat us.

## Also stale in our own top-level doc

`docs/SUBMISSION.md:84` says issuer income *since game 81* is 2nd of 17 at 353,387. Two
problems: the figure predates games 92–100, and game 81 is the wrong boundary — games
81–83 are the rogue-runner rounds where we collected 658 EUR in three triple-weighted
rounds, which drags the window to **4th**. Measured from game 84, where the corrected
package was actually live, we are **1st**. Fixed in that file.

## One claim in the one-pager that contradicts our own measurement

`pipeline/docs/onepager.tex` states the issuer rule as *"never lowered under uncertainty —
a fair charge is paid by all 16 reviewers either way, and **overcharging carries no
penalty**."*

There is no *penalty* term in the scoring, so the sentence is literally true about the
rules. But as a justification for not lowering the charge it inverts our own result: an
overcharge collects **0.10–0.20 per euro** against **1.000** for a fair charge, measured
over 161 provably-overcharged items
([[eklavya-2312-the-overcharge-curve-closes-the-income-lever]]). Overcharging forfeits
roughly 85% of the item's income — which is exactly why the 0.9 multiplier and the
quantile shading are correct, and why undercharging by half beats overcharging by half by
about 3×. As written, a judge who knows the payoff matrix reads it as a misunderstanding
of the game rather than the deliberate calibration it actually is.

This one is in `pipeline/`, which I do not edit under the repo split. Flagged for Luis.

## Reproduce

```
sqlite3 data/c2f.sqlite "select issuer, count(*), sum(case when amount>0 then 1 else 0 end)
  from transactions where game_id between 87 and 100 group by issuer"
```
and for the fraud table, join `tools/thresholds.py --jsonl` on `(game, item)`, keeping rows
with a non-null `t_hi`, and sum `amount` over `accepted=1 and amount > t_hi` per reviewer.
