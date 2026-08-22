# Leaderboard Math & The Trick

_Derived from live API data, 2026-08-22, after game 17 of 100._

---

## Current standings (17/100 games)

| Rank | Team | Net |
|---|---|---|
| 1 | error404 ai | +$92,905 |
| 2 | OPUSMOPUS | +$81,112 |
| 3 | TakeTheMoneyAndRun | +$66,637 |
| 4 | Non Deterministic | +$45,210 |
| **5** | **eyay (us)** | **+$33,048** |
| 6 | harissa eagles | −$5,834 |
| … | … | … |
| 17 | makalu | −$434,036 |

83 games remain. 52 of them run overnight (21:00–08:00 UTC).

---

## The payoff matrix

For every `(issuer H, reviewer I, line item)` triple each round:

```
                     a ≤ t  (fair price)            a > t  (fraud)
a ≤ b  (accepted)    I pays a,    H gets a           I pays min(a,c),  H gets min(a,c)
a > b  (rejected)    I pays 1.5a, H gets a           I pays 0,         H gets 0
                     ↑ wrongful rejection penalty
```

- **`a`** — your charge price (as handyman)
- **`b`** — your acceptance limit (as insurer)
- **`t`** — secret fair-value threshold per line item
- **`c`** — secret payment cap, `c ≥ 4t` (prevents one lucky charge winning everything)

**Net = Income − Costs**, ranked descending.

---

## The rule almost everyone misses

> **If your charge is fair (`a ≤ t`), you get paid whether the reviewer accepts or not.**

- Accepted → reviewer pays `a`, you get `a`
- Wrongfully rejected → reviewer pays `1.5a`, **you still get `a`**

The 0.5a penalty lands on the reviewer, not on you. So the only scenario where you earn zero as issuer is: your charge is **fraud** AND the reviewer rejects it. Otherwise, money flows to you.

---

## The trick — proved from game 10, item 3

Game 10 was the highest-variance round so far. OPUSMOPUS made **+$82,604** in a single game.

### What OPUSMOPUS did

| Role | Action |
|---|---|
| Issuer | Charged **$7,225** to all 16 teams |
| Reviewer | Accepted **everyone** — including $6,120, $5,777, $4,500, $4,264, $3,482, … |

All 16 teams rejected OPUSMOPUS's $7,225 charge. Since `t > 7225` (this was a large legitimate job), every single rejection was **wrongful**:

```
Income as issuer:    16 wrongful rejectors × $7,225   = $115,600
Costs as reviewer:   paid all fair claims accepted      ≈ $33,800
                     zero wrongful rejection penalties  =      $0
──────────────────────────────────────────────────────────────────
Net game 10:                                           ≈ +$81,800
                                             (actual:  +$82,604)
```

OPUSMOPUS earned **from rejections, not acceptances**. Because the charge was fair, the 16 teams that rejected it all owed $7,225 anyway — plus a $3,612 penalty each.

### What eyay did in the same game, same item

eyay charged $3,482.37 and set b ≈ $2,000:

```
Income as issuer:    16 teams × $3,482.37             = $55,718
  (all rejections were wrongful — eyay's charge was fair)

Costs as reviewer:
  accepted fair claims:                               ≈  $3,949
  wrongful rejections (b too low):
    rejected $7,225  → 1.5 × 7,225                  = $10,838
    rejected $6,120  → 1.5 × 6,120                  =  $9,180
    rejected $5,778  → 1.5 × 5,778                  =  $8,667
    rejected $4,500  → 1.5 × 4,500  (×2 teams)      = $13,500
    rejected $4,264  → 1.5 × 4,264                  =  $6,396
    rejected $1,200  → 1.5 × 1,200                  =  $1,800
  total wrongful rejection costs:                    ≈ $50,381
──────────────────────────────────────────────────────────────────
Net game 10 (item 3 only):                           ≈  +$1,389
                                             (actual:  +$1,649)
```

eyay charged correctly (fair price, got paid by everyone). Then **gave it all back** in penalties by setting b too low on the review side.

---

## The two-sided symmetric trick

### Side 1 — charge price `a`: aim for `t` from below

Charging exactly `t` maximises income because:
- Teams with `b ≥ t` accept → they pay you `a`
- Teams with `b < t` reject wrongfully → they still owe you `a`

Either way you collect. The only risk: overshoot (`a > t`) and every rejection is rightful — you earn zero.

### Side 2 — acceptance limit `b`: set `b = your estimate of t`

With `b ≥ t`:
- You accept all fair claims → pay face value, no penalty
- You reject fraud → pay nothing

With `b < t`:
- Every fair claim above your `b` triggers a **1.5x penalty**
- The penalty scales with the issuer's charge, not yours — you can't control it

The asymmetry:  
Accepting fraud costs at most `min(a, c)`.  
Wrongfully rejecting costs `1.5a` with no cap on `a`.

Setting `b` too low is strictly worse than setting it too high.

---

## eyay's performance data (from `/api/performance`)

```
income:                $418,541
costs:                 $385,493
net:                   +$33,048

as issuer:             3,888 transactions,  1,984 accepted  (51%)
as reviewer:           3,888 transactions
  correct accepts:     1,776  ✓
  wrong accepts:         103  (paid for some fraud — small cost)
  correct rejections:  1,112  ✓
  wrongful rejections:   897  ✗  ← the number to drive to zero
```

**897 wrongful rejections** at an average fair-charge value of roughly $280 each:  
`897 × 0.5 × $280 ≈ $125,580` in avoidable penalties over 17 games.  
That's 3.8× eyay's current net profit — sitting on the table.

---

## How to fix it: use the transactions API as your calibration set

`GET /leaderboard/api/transactions?game_id=<id>&team=eyay`

For every round where eyay **rejected** something (`accepted=false, amount > 0`):
- `amount` = the issuer's charge price `a`
- If the issuer's `a ≤ t` (verifiable from your pricebook), that was a wrongful rejection
- The next time you see that line item type, `b` must be at least that `amount`

The rejection history is a direct lower bound on `t` for each item category. Every game you've played gives you data. The calibration loop should be reading these bounds and raising `b` accordingly.

---

## The gap to close

| Source | Approximate value |
|---|---|
| Wrongful rejection penalties (897 events) | ~$125k avoidable |
| Charge undershoot vs OPUSMOPUS (item 3: $3,482 vs $7,225) | ~$62k per similar round |
| Missed income from a = 0 in games 1–6 | already sunk |

The b calibration is the highest-leverage fix. Raising b to match t eliminates the penalty entirely at the cost of occasionally paying for a capped fraudulent claim — a trade that is nearly always worth it.
