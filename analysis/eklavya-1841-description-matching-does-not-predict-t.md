# Description-to-damage matching does not predict `t` — and the hypothesis was wrong

**Written:** 22 Aug 2026, 18:41 UTC · 27 games played · measured offline, no round spent

Stage 4 of the pipeline sketch — "check what matches the description" — was the only
unbuilt stage with usable ground truth. It does not clear the gate, and the more
useful finding is *why*.

## What was measured

Reproduce with `PYTHONPATH=. .venv/bin/python tools/measure_description_match.py`.
No network, no model: keys come from the local cache.

Two deterministic detectors scoring each line item's description against the claim's
`damage_description`, on the proven split from `tools/thresholds.py` (worthless =
`t_lo == 0`, bounded, ceiling < 176; valuable = `t_lo >= 200`). Base rate is 50/50 —
96 proven-worthless against 96 proven-valuable.

| detector | worthless mean | valuable mean | best precision | recall |
| --- | ---: | ---: | ---: | ---: |
| word containment | 0.367 | 0.437 | 0.62 @ ≤0.10 | 0.37 |
| trigram cosine | 0.179 | 0.200 | 0.70 @ ≤0.05 | 0.09 |

The gate is **precision ≥ 0.90** (`docs/CLAIM_PIPELINE_PLAN.md` 4.1). Both fail, and
they fail against a 0.50 base rate, so the best result is 0.20 above chance on 12
items.

## Why acting on it would be expensive, not merely useless

At the best containment threshold, 53 items are flagged at precision 0.62 — about
**20 false positives on proven-valuable items**, some with proven floors above 7,000.
A false positive zeroes `b` on a valuable item, so we reject every fair charge on it
and pay `1.5a` on each. That is the game-1 failure mode, twenty times over, and cost
is concentrated enough (median worst-item share ~49%) that a handful of these decides
a round.

## The hypothesis was mis-specified, which is the real result

The hypothesis was: *an item unrelated to the damage text is padding, and padding has
low `t`.* The direction of both detectors supports it — worthless items really are
less related. But the effect is tiny, and the reason is that the two classes are not
what the hypothesis assumes.

The proven-worthless population is **66 of 96 under 50 EUR, median 38.30**. These are
*cheap* items, not *padded* ones. A legitimate 38-euro consumable matches the damage
text perfectly and still has low `t`, because `t` is the fair *price* of the work, not
a measure of whether the work belongs on the invoice.

So description-matching answers a different question than the labels ask. It would
detect padding; our ground truth measures price. There is no padding label anywhere in
the transactions, which is the same structural wall stage 5 hits — and it is not
fixable by tuning a cutoff or swapping in a semantic model, because the target is
mismatched rather than the metric.

## What this means for the pipeline sketch

Stages 4 and 5 are both unvalidatable against the data we have. Stage 4 is now a
measured negative rather than an open question. `tools/measure_description_match.py`
is kept because the measurement is worth more than the code — and because the harness
is what a padding-label experiment would need if labels ever appear.

This is the third detector to fail on the same split (LLM zero-votes at the wiring
stage, fuzzy trigram trade matching, and now this). The mechanism they feed is proven
— `worthless_accept_guard` is live at **+22,715 over 22 games, exact**. Detector
precision is the binding constraint, and text is turning out to be a weak source for
it.

The open lead remains the income half, where we are ~173k behind versus ~28k on
costs: `F(a) ≈ 0.18`. Over 24 games and 25,984 reviewer decisions against
proven-fraudulent charges, **17.5% were accepted at mean 374.69**. Our charge policy
assumes an over-charge earns nothing; it does not. That is measurable purely on the
issuer side — our own charges and their outcomes are both observed — so it has none of
the invisible-amount problem that makes any `b` raise an upper bound.
