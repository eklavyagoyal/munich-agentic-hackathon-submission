# Case 07: surge damages 2 fixed AC units — clean like-for-like replacement, building-services cover

**Author:** Annie  
**Date:** 2026-08-22 16:25  
**Confidence:** High on coverage (description is explicit, like-for-like confirmed). Rates are estimates, not measured.

---

## What happened

Power surge knocked out two permanently-wired, wall-fixed air conditioning units (living room + kitchen). Both replaced like-for-like. Technician fitted replacements and checked wiring. 6 items, 1 invoice (Building Services / Handy Hans).

---

## Coverage verdict per item

| # | Description | qty | unit | Covered | Notes |
|---|---|---|---|---|---|
| 1 | AC unit — living room (surge damaged, like-for-like) | 1 | pcs | **Yes** | Explicitly like-for-like; fixed building service; clear surge cause |
| 2 | AC unit — kitchen (wall-mounted, ~2 m from hob) | 1 | pcs | **Yes** | Same as above; proximity to hob noted in description but it's a fixed unit and distance is safe; no exclusion triggered |
| 3 | Installation — living room unit | 1 | pcs | **Yes** | Consequential to replacement of a permanently-wired unit |
| 4 | Installation — kitchen unit | 1 | pcs | **Yes** | Same |
| 5 | Floor console (equivalent stand, same as before) | 1 | pcs | **Yes** | Description confirms "same kind of stand" — like-for-like, no betterment |
| 6 | Freight shipping | 1 | pcs | **Yes** | Consequential |

**No exclusion patterns.** No betterment (like-for-like explicitly stated for both units and the stand), no pre-existing fault, no missing diagnostic, no admin fee.

---

## Key policy note — building-services cover

This claim is on **fixed building-services cover**, not consumer electronics. Permanently wired, wall-fixed AC units qualify as building services. This is a different policy section than cases 02, 04, 06 (consumer electronics). Worth checking whether our policy type detection handles this distinction — the pricebook and LLM system prompt should know that AC units on building-services cover are priced differently (installation is a bigger cost component).

The kitchen unit proximity note (~2 m from hob) appears to be the loss adjuster flagging that it isn't a cooking-zone appliance — it reads as a defence against a potential exclusion, not a red flag.

---

## Rate estimates (gross incl. 19% VAT)

| # | Item | Gross estimate (EUR) |
|---|---|---|
| 1 | AC unit, living room (wall-fixed split, ~9000–18000 BTU) | 700–2 000 |
| 2 | AC unit, kitchen (similar spec) | 600–1 800 |
| 3 | Installation, living room (permanently wired) | 250–550 |
| 4 | Installation, kitchen | 250–550 |
| 5 | Floor console / stand | 80–250 |
| 6 | Freight shipping | 50–180 |
| **Total** | | **1 930–5 330** |

Installation cost is a larger fraction here than for consumer electronics — permanently wired units require an electrician, not just plug-and-play. The `electric` hourly rate in the pricebook (EUR 65–120/hr net) is the right basis for items 3 and 4 if we can detect them as electrical installation.

---

## Pattern summary across 7 cases

| Case | Peril | Betterment? | Pre-existing? | Missing report? | Admin fee? |
|---|---|---|---|---|---|
| 01 | Water (pool) | **Yes** (floor + skirting) | No | No | No |
| 02 | Surge electronics | No | No | No | No |
| 03 | Theft abroad | No | No | No | No |
| 04 | Surge electronics | No | **Yes** (DVD) | **Yes** (router) | **Yes** |
| 05 | Water (kitchen) | **Yes** (table) | No | No | No |
| 06 | Surge electronics | No | No | No | No |
| 07 | Surge building services | No | No | No | No |

Betterment appears in 2/7 cases. Pre-existing in 1/7. Clean claims are the majority so far — our losses are from `b` being too low and rejecting fair claims, not from over-accepting fraud.

---

## Leaderboard at time of writing

Oasis: **Rank 8 / 17, net −17,329** (worsened from −11,660 — we're losing ground as other teams improve their submissions). Top: `error404 ai` at +85,197.
