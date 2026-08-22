# The five-question pipeline: implementation plan

**Source:** Eklavya's whiteboard, 22 Aug ~18:20 CEST. Written up against everything
the tournament has actually measured, 17 games in.

The sketch is right about the decomposition and wrong about one box. Both matter, so
this is organised as: what the sketch says, what the data says, what to build, and
how we will know it worked.

---

## 0. The sketch, formalised

```
photo.jpg ──A1──► photo.txt            (VLM: describe this image as a claims adjuster)
invoice.pdf ─A2──► [{idx, desc, qty, unit}]   + our predicted price per item
description.txt ─③  (given)
policy.txt ──────④  (given)

B1  GATE      photo.txt  vs  description.txt      ── NO ──►  whole claim is fraud
                    │ YES
                    ▼
M1  MASK/item (A1, A2, ③) → does this line item match the damage and its scope?
M2  MASK/item (A2, ④)     → is this line item covered by the policy?

            M1 AND M2  ──►  price the TRUE items
```

Your five questions map to it exactly: (1) is A2, (2) is the pricing that hangs off
A2, (3) is M2, (4) is M1, (5) is B1.

---

## 1. Three factual corrections before anyone builds it

### 1.1 The invoice has no prices. A2 cannot read a price column.

Measured on case 1: **zero money-shaped tokens** in the whole invoice. The columns
are `POS. | DESCRIPTION | AMOUNT | UNIT | TOTAL` and the money columns are empty --
`AMOUNT` is the quantity, not a price.

So the `Item | Price` table in the sketch is `Item | OUR predicted price`. There is
no claimed price to check against, which removes a whole class of easy fraud signal
(nobody is over-billing a stated rate; we have to value from scratch). It also means
A2 is already built: `c2f/ingest/parse.py` does it, and the two bugs that cost us
rounds are fixed (dash-quantity rows, two-word units).

### 1.2 "FRAUD → a = 0, b = 0" is the one box that is measurably wrong

This is the most important correction in the document, and it applies to B1's NO
branch *and* to every item the AND-mask marks false.

Setting `a = 0` throws away money. Roughly half the field accepts our over-charge on
worthless items, and **13,005.30 of our income across games 1-7 came from charges
proven fraudulent**. Charging on a worthless line costs nothing: if `a > t` the
reviewer either rejects (we get 0, no penalty) or accepts (we get paid for nothing).
There is no downside to the charge.

Measured on the 60 items with a proven ceiling under 100 and no fair charge ever
observed, over 15 games:

| policy on a worthless item | measured |
| --- | --- |
| keep `a`, set `b = 0` | **+14,575.16** |
| set `a = 0, b = 0` (the sketch's box) | +4,475.46 |

Same items, same data. The difference is the 10,099.70 of income that zeroing `a`
forfeits. So the false branch is **"charge as normal, accept nothing"**, never
`0/0`.

This is now expressible: `Verdict.accept_ceiling` caps `b` alone (`c2f/core/models.py`),
`decide()` applies it after the clamp and skips the `b > a` repair
(`c2f/decision/quantile.py`), and `check_decision` permits `b < a` only when a rule
asked for it. Before today it was structurally impossible -- our own invariant, not
the game's. `API_HANDBOOK:82` requires only that both values be finite and
nonnegative.

### 1.3 A whole-claim gate is the highest-variance decision in the system

B1 as drawn zeroes an entire round on one boolean. Our rounds are worth roughly
-60k to +12k, and the cost of a round is concentrated: median worst-item share ~49%,
and game 10 was 92% of its cost in a single item. A wrong NO on a real claim
therefore forfeits the whole round's income and, with `a = 0`, pays `1.5a` to
everyone on every fair charge -- which is exactly the -8,273.70 we scored in game 1
by submitting nothing.

Keep B1, but make it asymmetric: a NO must never zero `a`, and it should require a
much higher bar than a per-item mask. Concretely, B1's NO sets `accept_ceiling = 0`
for the whole case and leaves every charge intact.

---

## 2. What the data says about the masks -- read this before building them

The masks are the hard part, and they have already been measured in three different
forms. All three lost money.

| attempt | form | measured |
| --- | --- | --- |
| `llm_coverage` | LLM says not covered/unrelated → `a=b=0` | held; zeroing measured -3,182.79 |
| coverage keywords (`policy_exclusion`) | keyword table over policy text | has never once fired in 17 games |
| `worthless_accept_guard` | LLM prices item at 0 → `b=0`, keep `a` | **-75.00** on games 9, 10, 12 |

That last one is the sketch's design, already built and already measured, and it is
the most informative result we have. The mechanism is correct: charges stayed
identical, limits fell (game 9 limit 1,142 → 713, game 10 843 → 398). It still lost
75 EUR, because **the detector fires on the wrong items often enough to cancel a
+14,575 oracle**.

So the critical path is not the mechanism and not the wiring. It is **mask
precision**. Any plan that does not put measurement of precision first will
reproduce the -75.

### 2.1 The one signal that has shown real discrimination

The LLM's own zero-price vote. On game 8, the four items it priced at zero had proven
thresholds `t < 84.33`, `< 1.00`, `< 1.00`, `< 1.00`, while the four it priced were
all `t >= 400`. Four for four. That vote used to be discarded as a failed sample and
is now kept as `PriorEstimate.worthless_votes` (`c2f/estimate/ensemble.py`).

It is promising and it is not yet good enough. Both things are true.

### 2.2 The validation set exists -- use it, do not invent one

From `tools/thresholds.py` over 17 games:

- **75 items** with `t_lo == 0`, bounded, ceiling `t < 176`, median ceiling 38.25.
  These are proven worthless. This is the positive class for M1/M2.
- **86 items** with both bounds, many at `t >= 400`. Proven valuable. Negative class.

Two independent derivations agree on the boundary: the game-8 zero-vote observation
from one side, the 75-item population from the other.

---

## 3. Build order, with the latency budget

The round is 60 seconds and the existing two-tier structure already solves the
deadline problem: tier 1 submits from the price book in ~2 s, tier 2 overwrites by
52 s, and any tier-2 failure leaves tier 1 standing. **Everything below goes in tier
2.** Nothing in this plan may touch the tier-1 path.

Measured latencies to budget against:

| step | measured |
| --- | --- |
| key fetch + decrypt + parse + tier-1 submit | ~2.0-2.7 s |
| ensemble, 16-17 items, 2-3 samples each | 19-32 s |
| ensemble, 6 items | 2.8 s |
| ensemble, 39 items | ~24 s (35/39 estimated) |
| one VLM/LLM call, trivial prompt | 0.7-4.8 s |

Headroom is real but not generous. A 39-item case at 24 s plus a VLM call plus two
mask passes must fit in ~50 s. Budget: **A1 ≤ 8 s, A2 ~0 s (already local), masks
inside the existing per-item call, B1 ≤ 5 s.**

### Step 1 — A1: photo → text. NEW capability, nothing exists.

`photo.jpg` is 3.25 MB and we have never looked at it. `c2f/estimate/llm.py`
already supports images (`_b64`, `images=` on `ask_json`), so the seam exists.

- New module `c2f/estimate/vision.py`, one function:
  `describe(image_path, timeout) -> str`.
- Schema-constrained JSON, not prose: `{visible_damage: [...], rooms_or_objects:
  [...], severity: "none|minor|moderate|severe", inconsistencies: [...]}`. Free text
  cannot be compared mechanically; a list can.
- One call per case, not per item. Cache to `data/vision/case-NN.json` so a replay
  costs nothing.
- **Abstain loudly.** No image, timeout, or refusal → return `None` and let every
  downstream mask default to "pass". A missing photo must never fail an item.
- Cost note: images are the expensive input. One call per case is ~85 calls for the
  rest of the tournament; per-item would be ~850.

### Step 2 — Fold M1 and M2 into the existing per-item call

Do **not** add two more LLM round-trips per item. The ensemble already asks a
per-item question and already returns `covered` and `related` booleans; extend that
schema instead:

```
covered_by_policy : bool     # M2
matches_damage    : bool     # M1, against description.txt
matches_photo     : bool     # M1, against A1's structured output
confidence        : "low" | "medium" | "high"
unit_price_p10/p50/p90       # already there
```

Three booleans and a confidence, no extra latency. The digest call already
summarises the policy once per case, so M2 costs nothing extra either -- and note
the item prompt was resending the full 40k-char policy per sample until today, which
is what made the ensemble miss its deadline (53.9 s → 24.5 s once fixed).

### Step 3 — The AND, as a GUARD not a COVERAGE verdict

```python
# rules_user/mask_accept_guard.py, Stage.GUARD
if B1 failed          -> accept_ceiling = 0        # whole case, charge untouched
elif not (M1 and M2)  -> accept_ceiling = 0        # this item, charge untouched
elif confidence low   -> no opinion                # fall through to the book
```

GUARD, because a COVERAGE verdict short-circuits the engine to `a=b=0` and forfeits
the charge -- the -3,182.79 result. GUARD runs after the belief is fixed and can cap
`b` alone.

Loads SHADOW. Promotion requires §4.

### Step 4 — Only then, consider using the masks to raise `b`

Tempting and currently unprovable. 423 rejected-fraud charges over games 1-10 have
**invisible amounts** (a rejected fraudulent charge pays nothing, so it never reveals
its size), so any change that raises `b` is an upper bound, never a measurement.
`tools/score.py` reports those as an `unpriced` count for exactly this reason.
Lowering `b` is exactly measurable; raising it is not. Do the measurable half first.

---

## 4. The gate. Nothing promotes without passing this.

Pre-registered, because a criterion invented after seeing the number is not a
criterion:

1. **Mask precision on the validation set.** On the 75 proven-worthless items and the
   86 proven-valuable ones, report precision and recall for `NOT (M1 AND M2)`.
   Required: **precision ≥ 0.90** on the worthless class. At the measured
   concentration -- one item is often half a round's cost -- a false positive on a
   valuable item costs more than several true positives save.
2. **`tools/score.py --label X --vs baseline` positive across all 17 games**, not a
   subset. The -75.00 result came from three games; three games is where a wrong
   answer hides.
3. **No increase in the `unpriced` count.** If a variant raises `b` anywhere, its
   number is an upper bound and does not count.
4. **Tier-1 untouched**, and tier 2 completing inside 52 s on the largest case seen
   (39 items).
5. **Abstention verified**: no photo, no LLM key, or a timeout must leave the price
   book's numbers exactly unchanged. Test it by unsetting the key.

6. **Where a parameter is unknown, decide by MAXIMIN, not by refusing.** Bound the
   unknown, evaluate the candidate at every point in that range, take the WORST
   case, and ship only if the worst case is positive. This is borrowed from a
   procurement-prediction system under the same shape of asymmetric cost, and it
   replaces the reflex of calling a change "unprovable" and stopping.

   Worked, on the biggest open question -- should `b` rise generally? The exact
   saving from accepting every fair charge we wrongly rejected is +112,061. The
   unknown is the size of the 848 rejected-fraud charges whose amount is never
   revealed. Bounding it as a multiple of the 490 fraud charges we DID accept
   (mean 168.36):

   | multiple | assumed size | added fraud cost | net |
   | ---: | ---: | ---: | ---: |
   | 0.5 | 84.18 | 71,386 | **+40,675** |
   | 1.0 | 168.36 | 142,773 | -30,712 |
   | 3.0 | 505.09 | 428,318 | **-316,257** |

   Worst case -316,257, so: do not ship. Break-even is ~0.78x the observed mean,
   which would require the invisible charges to be SMALLER than the ones we
   accepted -- and they are selected for being obviously fraudulent, since all
   sixteen reviewers rejected them, so larger is the realistic assumption.

   The same procedure is why lowering `b` on identified worthless items IS
   shippable: it has no unknown parameter at all. Lowering `b` only converts
   acceptances into rejections, so every affected charge is one whose amount we
   already know.

Use `tools/score.py`. Do not write another scorer -- five agents have now each
rebuilt one in a scratchpad, and the shared one validates itself with `--actual` by
reproducing all 17 realised scores to the cent.

---

## 5. The open areas, and what I would put in them

**"How do we compare photo.txt to description.txt?" (B1)**
Not string similarity. Ask the model directly, once per case, with a schema:
`{consistent: bool, contradictions: [...], confidence: ...}`. Then require
`consistent == false AND confidence == high` before acting, and act only on `b`.

**"What is the boolean mask, exactly?"**
Per line item, `NOT (covered_by_policy AND matches_damage AND matches_photo)` →
`accept_ceiling = 0`. Note the photo term should be permissive: a photo showing one
room does not disprove a line item about another. Use it to *confirm* damage, not to
refute absence.

**"What do we do with FALSE items?"**
Charge normally, accept nothing. §1.2. This is the single most valuable correction
in the plan.

**"How do we know the masks are any good?"**
§4.1, against the 75/86 split. This is the part I would build first, before any of
the pipeline -- it is a scoring script over cached LLM answers, it needs no
tournament round, and it tells you whether the rest is worth writing.

**Unfilled and honestly unanswered:** how to price a *covered* item well. The masks
only decide which items to accept; they do not tell us what `t` is. That is where
the remaining income gap lives -- we are 173k behind the leader on income and only
28k on costs. The LLM reached the proven floor on 9 of 12 high-value items against
the book's 2 of 12, which is the most promising unexploited result on the board and
is not part of this sketch at all.

---

## 6. What already exists

| piece | state |
| --- | --- |
| A2 (invoice → items) | done, `c2f/ingest/parse.py`, two round-costing bugs fixed |
| ③ ④ (description, policy) | done, `parse.read_files` |
| per-item LLM valuation | done, `c2f/estimate/ensemble.py`, 19-32 s, digest-based |
| `covered` / `related` votes | done, unused by any active rule |
| zero-price vote | done today, `PriorEstimate.worthless_votes` |
| charge-high/accept-nothing | done today, `Verdict.accept_ceiling` |
| the AND guard | built, SHADOW, measured **-75.00** -- needs a better mask |
| A1 (photo → text) | **not started.** The only genuinely new capability here |
| mask validation harness | **not started.** Build this first |

Two of the five questions are already answered in code. The third and fourth are
built and measured and losing money. The fifth has never been attempted.

---

## 7. The order I would actually do it in

1. **Validation harness** (§4.1) against the 75/86 split. No tournament round needed.
   If precision on the current zero-vote detector is below 0.90, the pipeline as
   drawn cannot pay and we learn that in an hour instead of a night.
2. **A1**, cached, abstaining, one call per case. It is the only new signal, and the
   photo is the only input we have never used.
3. **Extend the item schema** with the three booleans. No new latency.
4. **The GUARD**, SHADOW, measured over all 17 games.
5. **Promote or discard** on §4.
6. Only then: the income half, which is bigger and is not in this sketch.

The reason for that order is the -75.00. We already built the pipeline's back half
and it did not pay, because the mask was not accurate enough. Measuring the mask is
cheap; building around an inaccurate one is what costs a night.
