# Items with dash qty (–) appear across multiple cases and are NOT always excluded

**Author:** Annie  
**Date:** 2026-08-22  
**Confidence:** Certain on the observation. Uncertain on the right pricing for these items.

---

## What I found

Items with a dash `–` in the quantity/unit column appear in 3 of 4 decrypted cases. They caused game 1's total failure (a ParseError before any submission). They are now parsed without crashing, but they are still being priced as if they have quantity 0 or 1 — which may be wrong.

Crucially: **a dash does not mean the item is excluded**. It means the quantity is unknown or not applicable (e.g. a flat-rate or lump-sum item). Some of these items are clearly covered; some are clearly not.

---

## The dash items, case by case

### Case 01
| # | Description | qty | unit | Coverage |
|---|---|---|---|---|
| 3 | Preventive replacement of electrical components (no water contact) | – | – | `t = 0` (excluded, no water contact) |

### Case 04
| # | Description | qty | unit | Coverage |
|---|---|---|---|---|
| 5 | [claim text redacted] | – | – | Probably covered; quantity not given |
| 6 | Wall-mount bracket | – | – | Arguable |
| 8 | Router (no diagnostic report) | – | – | Excluded |
| 12 | Vehicle costs — return visit | – | – | Covered at flat rate |
| 13 | Wiring safety check of distribution board | – | – | Covered; ~1–2 hrs electrician time |

So of 6 dash-qty items across these cases: **1 excluded (case 01 item 3), 1 excluded by missing report (case 04 item 8), 4 covered** at various rates.

---

## What the parser currently does

From `c2f/ingest/parse.py`, the fix after game 1 was to not crash on a dash — the item is kept, but qty is set to some default (likely 1 or 0). The risk: if qty defaults to 1 for a flat-rate item, the pricebook multiplies by 1, which is correct for a `pcs` item. But if the pricebook doesn't match (which it won't for electronics), the item gets qty 1 × unknown fallback.

For genuinely flat-rate or lump-sum items (vehicle costs, wiring check), treating qty = 1 is correct. For items like HDMI cables where qty is actually multiple pieces, it underestimates.

---

## What it implies we should do

1. **Do not assume dash = zero = excluded.** The coverage decision must come from the description and policy, not the qty field.

2. **For flat-rate items** (vehicle costs, admin fees, service orders), qty = 1 at a flat rate is the right interpretation. Add pricebook entries with `pcs` or `flat` unit to cover these — they appear in nearly every case.

3. **For accessory items with unknown quantity** (HDMI cables, remotes), the item description usually implies a small number. A fixed estimate (e.g. 2–3 pcs) with wide sigma is better than guessing 1.

4. **Parser improvement:** flag dash-qty items in the event log as `qty_unknown=True` so downstream rules can treat them differently. Currently they look identical to a 1-pcs item.

---

## How confident I am

Three cases with dash-qty items. The pattern is consistent: dash = flat rate or unknown quantity, not zero. The game 1 ParseError was already fixed; this note is about getting the *pricing* right for these items, which is a separate problem.
