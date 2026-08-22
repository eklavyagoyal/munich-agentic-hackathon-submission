# Case 05: kitchen water damage — betterment pattern repeats, plumbing rates needed

**Author:** Annie  
**Date:** 2026-08-22  
**Confidence:** High on coverage calls (description is explicit). Rate estimates from knowledge, not transactions.

---

## What happened

Leak under kitchen sink → floor and wall-base moisture damage → leak detection, pipe repair, multi-day drying, floor reinstatement. Also: water-damaged kitchen table replaced with a **premium solid-oak designer model** (explicit upgrade).

17 items across 4 invoices: Leak Detection, Plumbing, Drying Technology, Carpentry.

---

## Coverage verdict per item

| # | Description | Covered | Notes |
|---|---|---|---|
| 1 | Leak detection call-out + electro-acoustic pinpointing | Yes | Standard, clearly caused by the insured peril |
| 2 | Moisture measurement, floor and wall base | Yes | |
| 3 | [claim text redacted] (14 hrs) | Yes | 14 hrs is substantial but plausible for a full pipe job |
| 4 | Vehicle costs | Yes | Standard |
| 5 | [claim text redacted] | Yes | |
| 6 | Removal/disposal of damaged pipe insulation (2 pcs) | Yes | |
| 7 | Repair of confirmed leak on copper supply pipe | Yes | Core covered loss |
| 8 | [claim text redacted] (flat rate) | Yes | |
| 9 | Vehicle costs | Yes | |
| 10 | Condensation dryer rental | Yes | |
| 11 | Room drying, kitchen floor and wall base | Yes | |
| 12 | Vehicle costs | Yes | |
| 13 | Removal, transport, disposal of water-damaged table (3 pcs) | Yes | 3 pcs is odd for one table — likely labour + vehicle + disposal counted separately |
| 14 | **Replacement table — premium solid-oak designer, higher specification** | **Partial / No** | **Betterment** — like-for-like (standard wooden table) is covered; the oak designer upgrade is not |
| 15 | Delivery and assembly (flat rate) | Yes | Consequential to replacement |
| 16 | Cleaning of installation area | Yes | |
| 17 | Vehicle costs | Yes | |

**Item 14 is the key risk.** The description explicitly says "higher specification than the original". The pricebook has no entry for furniture — this will fall to the unknown fallback. A standard replacement kitchen table (IKEA-tier) is EUR 150–400 gross; a solid-oak designer model could be EUR 800–3000+. We should charge the like-for-like rate, not the designer rate.

---

## Rate estimates (gross, incl. 19% VAT)

### Plumbing / leak detection (invoices 1 & 2)
- Leak detection call-out (1 pcs): EUR 120–250 (specialist rate, includes equipment)
[claim text redacted] (1 pcs): EUR 80–160
- Technician hours (14 hrs at plumber rate): EUR 60–110/hr net → EUR 71–131/hr gross = **EUR 994–1 834 gross total**
- Vehicle costs (pcs): EUR 15–50
- Pipe freeing (1 pcs): EUR 150–350 (labour)
- Insulation removal (2 pcs): EUR 30–80 each
- Leak repair (1 pcs): EUR 200–500
- Copper pipe + fittings (flat rate): EUR 80–250 materials

### Drying technology (invoice 3)
- Condensation dryer rental (1 pcs): EUR 15–32/day × ~7 days = EUR 105–224
- Room drying (1 pcs): EUR 200–600 (depends on m², drying days)
- Vehicle: EUR 15–50

### Carpentry / furniture (invoice 4)
- Table removal + disposal (3 pcs): EUR 40–120 total
- Replacement table — **like-for-like standard** (1 pcs): EUR 150–400
- Delivery and assembly (flat rate): EUR 50–150
- Cleaning (1 pcs): EUR 30–80
- Vehicle: EUR 15–50

---

## What this confirms across cases 01–05

**The betterment/upgrade pattern has now appeared in 2 of 5 cases** (case 01: floor + skirting; case 05: kitchen table). It is not rare. The rule should be in place before more games play. Suggested keywords for the COVERAGE/GUARD rule: `upgrade`, `premium`, `higher specification`, `higher-quality`, `designer`, `rather than`, `instead of the original`.

**Plumbing rates** appear in cases 01 and 05. The pricebook has `plumbing h 60–110` — that's a net hourly rate, correct for labour lines. But multi-line plumbing jobs also include flat-rate call-out fees and materials; these need `pcs` entries.

---

## New pricebook entries needed from this case

```python
# Leak detection
Rate("leak_detection", "pcs", 100, 220, ("leak detection", "leckortung", "electro-acoustic", "akustisch")),
Rate("leak_detection", "pcs",  70, 140, ("moisture measurement", "feuchtemessung", "moisture measurement")),
# Plumbing materials / flat rates
Rate("plumbing",       "pcs", 200, 450, ("pipe repair", "leckage reparatur", "rohr reparatur")),
Rate("plumbing",       "pcs",  70, 230, ("pipe section", "fittings", "copper pipe", "kupferrohr")),
Rate("plumbing",       "pcs",  25,  70, ("pipe insulation", "rohriso", "insulation removal")),
# Furniture — like-for-like standard
Rate("furniture",      "pcs", 130, 380, ("kitchen table", "esstisch", "table")),
Rate("carpentry",      "pcs",  35, 110, ("table removal", "disposal", "abtransport")),
Rate("carpentry",      "flat", 45, 140, ("delivery and assembly", "lieferung", "montage")),
```
