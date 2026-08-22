# Pricebook has zero coverage for electronics — cases 02 and 04 are 100% electronics items

**Author:** Annie  
**Date:** 2026-08-22  
**Confidence:** Certain on the gap (pricebook has no electronics entries). Rates below are estimates from German consumer market, not measured from transactions.

---

## What I found

Cases 02 and 04 are both power-surge claims against consumer electronics. Every single line item is either an electronic device, a service call, or an accessory. The pricebook (`c2f/estimate/pricebook.py`) has **no entries for electronics as discrete items** — it only covers construction trades (flooring, painting, plumbing, drying) billed per m², hr, or day. All electronics items fall through to the `unknown` fallback at a flat EUR 58.30 (recently raised from 0).

Case 02: 7 items, 0 pricebook matches.  
Case 04: 15 items, 0 pricebook matches.  
Case 01: 18 items — has electrical inspection entries but the hourly `electric` rate is likely the closest match only for the inspection lines.

---

## The items and what they should cost (German market, gross incl. 19% VAT)

### Case 02 — power surge, speaker + TV
| # | Item | Gross estimate (EUR) | Notes |
|---|---|---|---|
| 1 | Speaker system | 300–1 200 | Wide range; no brand/quality info |
| 2 | Shipping | 10–60 | Standard parcel shipping |
| 3 | Installation (1 hr) | 80–140 | Technician rate |
| 4 | TV set | 400–1 500 | Size/brand unknown |
| 5 | Property/liability damage to electronics | 0–200 | Vague; probably a labour/inspection line |
| 6 | Service order | 0–150 | Probably a fixed call-out fee |
| 7 | Vehicle costs | 15–50 | Standard mileage flat rate |

### Case 04 — power surge, full home entertainment + technician
| # | Item | Gross estimate (EUR) | Notes |
|---|---|---|---|
| 1 | TV set | 400–1 500 | |
| 2 | Speaker system | 300–1 200 | |
| 3 | [claim text redacted] | 350–1 200 | |
| 4 | Melted mains plug + lead | 15–60 | Physical consumable |
| 5 | HDMI cables + remotes (qty –) | 15–80 | Accessories; qty unknown |
| 6 | Wall-mount bracket (qty –) | 35–100 | |
| 7 | DVD player (pre-existing fault) | **0** | Excluded — pre-existing, see coverage analysis |
| 8 | Router (no diagnostic report, qty –) | **0** | Excluded or unknown, see coverage analysis |
| 9 | Shipping | 10–60 | |
| 10 | Installation | 80–140 | |
| 11 | Diagnostic + surge-failure report (2 pcs) | 150–350 | 2 visits × technician rate |
| 12 | Vehicle costs — return visit (qty –) | 15–50 | |
| 13 | Wiring safety check (qty –) | 80–200 | Electrician, ~1–2 hrs |
| 14 | Admin / claim-processing fee | **0** | Not an insured loss; typically excluded |
| 15 | Vehicle costs | 15–50 | |

---

## What it implies we should do

Add a `Rate` block to `c2f/estimate/pricebook.py` for electronics and consumer goods:

```python
# Electronics — consumer items, gross EUR per piece
Rate("electronics", "pcs",  350,  1 400, ("tv", "television", "fernseher")),
Rate("electronics", "pcs",  250,  1 100, ("speaker", "lautsprecher", "soundbar", "hifi", "hi-fi")),
Rate("electronics", "pcs",  280,  1 000, ("av receiver", "amplifier", "verstärker", "receiver")),
Rate("electronics", "pcs",   40,    160, ("dvd", "blu-ray", "bluray")),
Rate("electronics", "pcs",   50,    180, ("router", "modem", "fritzbox")),
Rate("electronics", "pcs",   10,     60, ("hdmi", "remote", "cable", "kabel", "fernbedienung")),
Rate("electronics", "pcs",   30,    100, ("wall bracket", "wandhalterung", "halterung")),
Rate("electronics", "pcs",   12,     55, ("mains plug", "power lead", "stecker", "kabel")),
Rate("services",    "pcs",   70,    200, ("surge-failure report", "diagnostic", "diagnose", "gutachten")),
Rate("services",    "pcs",   70,    200, ("surge failure", "inspection report", "prüfbericht")),
Rate("services",    "pcs",   15,     50, ("vehicle costs", "fahrtkosten", "anfahrt")),
Rate("services",    "pcs",   10,     60, ("shipping", "versand", "lieferung")),
Rate("services",    "flat",  50,    200, ("call-out", "callout", "service order", "serviceauftrag")),
```

These are wide bands — sigma will be high and `a` will shade conservatively, which is correct for items where we have no transaction data yet. Narrow the bands once we have bracketed `t` from a few games.

**Also:** the `electric` hourly rate (`65–120 net/hr`, `c2f/estimate/pricebook.py:41`) covers the wiring check and installation lines and should match on `wiring`, `wiring check`, `distribution board`.

---

## How confident I am

- The **gap is certain** — pricebook source has no consumer electronics entries.
- The **rate estimates** are from knowledge of the German consumer market, not measured from transactions. Treat them as a wide prior until we have bracketing data from completed games.
- **Two games** of evidence that electronics cases exist and fall to the unknown fallback. Expect more — surge damage is a common P&C peril.
