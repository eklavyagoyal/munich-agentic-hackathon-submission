# Coverage exclusion patterns across cases 01–04: upgrades, pre-existing faults, missing reports

**Author:** Annie  
**Date:** 2026-08-22  
**Confidence:** High on items explicitly flagged in the damage description. Medium on items inferred from policy logic.

---

## What I found

Reading the damage descriptions and invoices for cases 01–04 together, several items are clearly `t = 0` (excluded) from the description alone — before touching the policy. These are not edge cases. They follow three recurring patterns: **betterment/upgrades**, **pre-existing conditions**, and **no supporting evidence**. Getting coverage right is where the most money is lost, because a covered item set to `b = 0` eats a `1.5a` penalty from every other team.

---

## Per-case findings

### Case 01 — pool house water damage (18 items)

The damage description explicitly flags two upgrades and one speculative replacement:

> *"the owner didn't want the plain tiling that was there before and had it redone in high-end natural stone instead… the new skirting went in as a premium hardwood rather than the softwood that came out — both upgrades on the pre-loss standard. The electrician also swapped out a run of components… over and above the ones that had actually been in contact with the water."*

| Item | Description | Coverage verdict | Reason |
|---|---|---|---|
| 3 | Preventive replacement of plant-room electrical components (no confirmed water contact) | `t = 0` | Explicitly "no confirmed water contact" — precautionary, not a covered loss |
| 4 | Upgrade to natural stone floor (12 m²) | `t = 0` likely | Policy should only cover like-for-like (ceramic → ceramic). Upgrade cost is uninsured betterment |
| 18 | Premium hardwood skirting (15 m) | `t = 0` likely | Same betterment issue; softwood like-for-like is covered, premium hardwood upgrade is not |

Items 1, 2, 5–17: appear covered (water damage, inspection, drying, repair of affected areas). Items 6 (wall surfaces, 10 m²) and 15 (room drying) look like clear covered costs.

**Note on qty dash:** Item 3 has qty `–` — this is the same dash pattern that caused game 1's `ParseError`. The item is probably excluded anyway (`t = 0`), but the parser must not crash on it.

### Case 02 — power surge, speaker + TV (7 items)

No red flags in the damage description. Both the speaker and TV are explicitly named as surge-damaged. Appears mostly covered subject to the policy's electronics clause.

| Item | Description | Coverage verdict |
|---|---|---|
| 1 | Speaker system | Covered |
| 4 | TV set | Covered |
| 2 | Shipping | Covered (consequential to replacement) |
| 3 | Installation (1 hr) | Covered (consequential) |
| 5–6 | "Property and liability damage to electronics" × 2 | Vague; likely a call-out/inspection fee — covered if the policy covers labour |
| 7 | Vehicle costs | Covered at standard rate |

### Case 03 — theft abroad, car break-in (2 items)

This case is entirely about what the policy covers for theft from a vehicle while abroad. Nothing in the home was touched.

| Item | Description | Coverage verdict |
|---|---|---|
| 1 | Clothing and jewellery stolen from car | **Policy-dependent.** Many P&C policies cover theft of personal effects from a locked vehicle; jewellery is often sub-limited or excluded. Cannot determine without reading `policy.txt` |
| 2 | Vehicle costs | Covered at standard rate if claim is valid |

**Key risk:** if the policy excludes jewellery or theft from a vehicle, item 1 is `t = 0` and we are paying `1.5a` to everyone who rightfully rejects us. This case must read the policy before setting `b`.

### Case 04 — power surge, full home entertainment (15 items)

The damage description explicitly flags two problem items:

> *"The DVD player had already been playing up for months before the storm and is showing its age"*  
> *"the router is on the claim but no diagnostic report was produced for it"*

And one line in the invoice is an admin fee — almost universally excluded.

| Item | Description | Coverage verdict | Reason |
|---|---|---|---|
| 7 | DVD player | `t = 0` | Pre-existing fault ("already been playing up for months") — not caused by the surge |
| 8 | Router | `t = 0` or highly uncertain | No diagnostic report; description explicitly notes the absence. Cannot prove surge damage |
| 14 | Administrative and claim-processing fee | `t = 0` | Admin fees are not an insured loss in standard P&C policy |
| 12 | Vehicle costs — return visit (qty –) | Covered but qty unknown | |
| 13 | Wiring safety check (qty –) | Covered — directly supports the surge claim | |
| 5 | HDMI cables + remotes (qty –) | Probably covered, qty unknown | Minor accessories |
| 6 | Wall-mount bracket (qty –) | Arguable | Not surge-damaged; incidental to TV replacement |
| 1–4, 9–11, 15 | TV, speaker, AV receiver, plug/lead, shipping, installation, diagnostic | Covered | |

---

## Recurring patterns — actionable for the rule engine

Three exclusion patterns appear across these 4 cases. Each is detectable from the damage description alone, without reading the full policy:

1. **Betterment/upgrade** — invoice description says "upgrade from…" or "premium … rather than". The like-for-like rate applies; the upgrade delta is excluded. Detection: keyword match on `upgrade`, `premium`, `high-end`, `rather than`, `instead of`.

2. **Pre-existing condition** — damage description says the item was already failing. Detection: keywords `already`, `before the storm`, `playing up`, `age-related`, `pre-existing`.

3. **No supporting documentation** — item on the invoice but no report/diagnosis exists. Detection: damage description says `no diagnostic report`, `no report provided`. These should get `t = 0` or a heavy veto.

**Admin fees** (`administrative fee`, `claim-processing fee`) are a fourth pattern — nearly always excluded.

---

## What it implies we should do

1. Add a `COVERAGE` rule in `rules_user/` that scans the damage description for the three patterns above and returns `Verdict(covered=False)` when matched to the current item. This is keyword-level, no LLM needed, and it fires before the price is estimated.

2. For **case 03** (theft abroad) and any other policy-heavy case: read `policy.txt` to check the relevant clause. This is exactly what `llm_coverage` does — but it needs a model key. Until a key exists, the fallback should be conservative (do not assume covered).

3. **Betterment for construction items**: for items 4 and 18 in case 01, the correct `a` is the like-for-like rate (ceramic tile / softwood skirting), not the upgrade rate. Specifically: ceramic tile ≈ EUR 45–95/m² gross, natural stone ≈ EUR 120–300/m² gross. Charging the natural stone rate exposes us to rejection by every well-calibrated insurer.

---

## How confident I am

- Items 3, 7, 14, and DVD/router exclusions: **certain** — the damage description states the exclusion reason explicitly.
- Items 4 and 18 (betterment): **high** — standard P&C principle, description confirms the upgrade. Depends on the exact policy wording but almost always excluded above the like-for-like cost.
- Case 03 coverage: **unknown** — entirely depends on policy.

Four cases of evidence. The three exclusion patterns appear in 3 of 4 cases, suggesting they are common in this game's claim set.
