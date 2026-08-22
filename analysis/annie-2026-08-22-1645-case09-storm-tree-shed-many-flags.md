# Case 09: storm tree falls on shed — 16 items, 6 explicit exclusion flags, policy endorsement

**Author:** Annie  
**Date:** 2026-08-22 16:45  
**Confidence:** High on flagged exclusions (description names them explicitly). Medium on rate estimates.

---

## What happened

Storm fells large tree onto garden shed, caves in one roof section. Three trades: carpenter (roof repair), tree service (removal), recycling (debris + ground reinstatement). 16 items, 3 invoices.

Description pre-flags 6 issues: full shed repaint incl. undamaged walls, UV coating, all trim renewal incl. undamaged, hand tools, return-visit, catering, and duplicate transport charge.

**Policy carries grounds-reinstatement endorsement GR-2026** — ground disturbed by insured tree impact is covered at insurer's cost. This explicitly covers item 15.

---

## Coverage verdict — all 16 items

### Invoice 1: Carpentry (items 1–9)

| # | Description | qty | Covered | Notes |
|---|---|---|---|---|
| 1 | Repair storm-damaged roof section (restored to pre-loss standard) | 1 flat rate | **Yes** | Explicitly like-for-like; core covered loss |
| 2 | Full repaint entire shed, incl. undamaged walls | – | **Partial — FLAGGED** | Only the damaged section is covered; painting undamaged walls is scope creep. Description flags this. Charge at ~25–33% of full repaint rate |
| 3 | UV-resistant protective exterior coating | – | **No — EXCLUDED** | Betterment — UV coating was not the pre-loss standard. Description flags this |
| 4 | Renewal of all shed trim, incl. undamaged trim | 1 flat rate | **Partial — FLAGGED** | Only damaged trim covered. Description flags this. Discount heavily |
| 5 | Skilled carpentry labour for roof repair | 1 pcs | **Yes** | Direct labour for the covered repair |
| 6 | Contractor hand tools and reusable equipment | 1 flat rate | **No — EXCLUDED** | Contractor's own tools are an overhead cost, never an insured loss. Description flags this |
| 7 | Vehicle costs | 1 pcs | **Yes** | Standard |
| 8 | Vehicle costs — return visit | – | **Uncertain** | Description flags it; may be legitimate re-check or padding. Low confidence |
| 9 | Catering for work crew | – | **No — EXCLUDED** | Third catering exclusion in 9 cases (cases 08, 09). Certain exclusion |

### Invoice 2: Tree Service (items 10–12)

| # | Description | qty | Covered | Notes |
|---|---|---|---|---|
| 10 | Cutting and removal of storm-felled tree from roof | 1 flat rate | **Yes** | Core insured peril |
| 11 | Lifting and earth-moving machinery hire | 1 flat rate | **Yes** | Necessary for tree removal |
| 12 | Vehicle costs | 1 pcs | **Yes** | |

### Invoice 3: Recycling Service (items 13–16)

| # | Description | qty | Covered | Notes |
|---|---|---|---|---|
| 13 | Disposal of shed roof timber and glass (building debris) | 2 pcs | **Yes** | Consequential to roof repair |
| 14 | Disposal of felled-tree green waste and root ball | 2 pcs | **Yes** | Consequential to tree removal |
| 15 | Reinstatement of excavated soil and displaced paving | 2 pcs | **Yes — GR-2026** | Explicitly covered by grounds-reinstatement endorsement. Description confirms |
| 16 | Transport charge for tree waste | – | **No — EXCLUDED (duplicate)** | Description states explicitly: "already billed by the tree service" (item 12). Certain double-billing |

---

## Exclusion summary

| Item | Reason | Confidence |
|---|---|---|
| 3 | UV coating — betterment beyond pre-loss standard | Certain |
| 6 | Hand tools — contractor overhead, not insured loss | Certain |
| 9 | Crew catering | Certain |
| 16 | Transport — duplicate of tree service item 12 | Certain |
| 2 | Full shed repaint — scope creep beyond damaged section | High |
| 4 | All trim renewal — only damaged portion covered | High |
| 8 | Return visit — possible padding | Medium |

---

## Rate estimates (gross incl. 19% VAT)

| # | Item | Estimate |
|---|---|---|
| 1 | Shed roof repair (flat rate, timber + covering) | EUR 800–2 500 |
| 2 | Painting — covered fraction (~25–33% of shed) | EUR 80–250 |
| 4 | Trim — covered fraction (damaged pieces only) | EUR 100–350 |
| 5 | Carpentry labour (1 pcs flat job) | EUR 250–600 |
| 7 | Vehicle costs | EUR 15–50 |
| 10 | Tree cutting + removal (flat rate) | EUR 500–2 000 |
| 11 | Machinery hire (flat rate) | EUR 300–1 200 |
| 12 | Vehicle costs | EUR 15–50 |
| 13 | Building debris disposal (2 pcs) | EUR 80–250/pcs → EUR 160–500 |
| 14 | Green waste disposal (2 pcs) | EUR 60–200/pcs → EUR 120–400 |
| 15 | Soil/paving reinstatement (2 pcs, GR-2026) | EUR 150–500/pcs → EUR 300–1 000 |

**Rough total covered: EUR 2,640–8,900**

---

## New patterns from this case

1. **Hand tools / reusable equipment** — new exclusion type. Contractors billing their own overhead. Add to exclusion keywords: `hand tools`, `reusable equipment`, `contractor tools`, `werkzeug`.
2. **Scope creep on adjacent undamaged areas** — painting/trim on undamaged parts. Distinct from betterment (quality upgrade); this is area inflation. The correct charge is a fraction of the billed rate proportional to the damaged area. Hard to detect without the LLM reading the damage scope.
3. **Policy endorsements** (GR-2026) — grounds reinstatement is an explicit endorsement that expands coverage. Without reading `policy.txt`, we'd treat item 15 conservatively. The LLM digest step is essential for endorsement detection.
4. **Duplicate transport** — item 16 is the second clear double-billing in 9 cases (after case 08's duplicate waste disposal). Pattern: two different contractors billing the same logistical service.
5. **First storm/tree peril** in 9 cases. Carpentry and tree-service rates now needed in the pricebook.

---

## Leaderboard at time of writing

Oasis: **Rank 10 / 17, net −25,685** — dropped 2 places since last tick (was rank 8 at −17,329). We're falling fast as other teams improve. Six teams now in positive territory.
