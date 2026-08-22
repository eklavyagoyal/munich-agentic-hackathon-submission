# Case 06: power surge, speaker + TV — clean 2-item claim, no exclusions

**Author:** Annie  
**Date:** 2026-08-22 16:10  
**Confidence:** High — description is explicit and simple, no flags.

---

## What happened

Thunderstorm power surge → speaker system + TV damaged. Technician attended to confirm surge failure and check wiring. Claim is intentionally simple: electronics bundled into one line, technician attendance as another.

2 items, 1 invoice (Electronics Retail).

---

## Coverage verdict per item

| # | Description | qty | unit | Covered | Notes |
|---|---|---|---|---|---|
| 1 | [claim text redacted] (speaker system and TV set) | 2 | pcs | **Yes** | Clean surge claim, both items named in description, no prior faults mentioned |
| 2 | [claim text redacted] | 3 | pcs | **Yes** | Directly supports the claim; qty=3 is odd (probably call-out + report + wiring check counted separately) |

**No exclusion patterns.** No upgrade/betterment, no pre-existing fault, no missing diagnostic (the report IS the item), no admin fee.

---

## Rate estimates (gross incl. 19% VAT)

### Item 1 — 2 pcs electronics (speaker + TV bundled, per unit)
Two different devices under one line item makes per-unit estimation wide:
- Speaker system alone: EUR 300–1 200
- TV set alone: EUR 400–1 500
- Bundled average per pcs: **EUR 350–1 350**
- Total for 2 pcs: **EUR 700–2 700**

Our `a` (charge price) should be the per-unit gross × 2. With wide sigma (~0.6–0.8 given the unknown device quality), the Mills optimum will shade conservatively — roughly 0.54–0.66× the median per unit.

### Item 2 — 3 pcs technician attendance (per unit)
Three units probably = call-out + surge-failure report + wiring safety check, each billed as a separate service unit:
- Per service unit: **EUR 70–200**
- Total for 3 pcs: **EUR 210–600**

---

## Pattern notes

**Third surge/electronics case** in 6 games (cases 02, 04, 06). Electronics is clearly a dominant peril in this game. The pricebook electronics entries proposed in `annie-2026-08-22-1600-electronics-pricing-gap.md` would cover all three cases — this is now high priority.

**Bundled line items** (multiple devices under one pcs quantity) are a new pattern. The pricebook keyword match works per item description but the qty multiplier here applies to an average of two different devices. This makes the per-unit estimate inherently wide — sigma should be high (0.6+), which is correct because it keeps `b` conservative.

---

## Leaderboard at time of writing

Oasis: **Rank 8 / 17, net −11,660** (up ~495 from previous check at −12,155). Slow improvement but still deeply negative. Top team (`error404 ai`) at +69,007.
