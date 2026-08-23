# Track D — per-item valuation synthesis

> Superseded for action by `analysis/codex-2330-corrected-valuation-verdict.md` after
> direct expensive-mask validation and the strictly later games 44–47 block.

UTC synthesis: 2026-08-22 22:23

Repository snapshot: `b49dccc9830cc22db0a2329693abb036a9d84f7f`

Common held-out window: games 20–43 inclusive

## Decision

**GO-AS-SHADOW-ONLY** for exactly one configuration:

> Use the one-call-per-invoice LLM as the complete price belief on every item, with
> unconditional item-level fallback to the current price book on timeout, provider
> failure, malformed output, or abstention. Do not use Track A's fitted scales. Do not
> use Track C's fixed router. Do not change `ACCEPT_QUANTILE`, `b`, the active rule set,
> or the submission path.

The conservative held-out number is **SCORE 0.317164450879**, the worse of two complete
LLM runs, versus **0.272898316898** for the price book. That run has **PROVEN INCOME
EUR 319,441.44**, **22 excluded/unprovable items**, 100 certainly-fair/under-floor
charges, and 99 certainly-fraudulent over-ceiling charges. The fixed denominator is
**221 items / EUR 1,007,179.20 BEST POSSIBLE**. These euros are the deliberately
synthetic `16 * charge` proven-income denominator, not tournament P&L. (Track B report
lines 16–33; Track A report lines 11–16.)

This is not an ACTIVE recommendation. The LLM moved from SCORE 0.428313 to 0.317164
on identical inputs, and in the numeric replay it raised reviewer limit `b` on 116 of
221 items. `tools.score.score` reports 918 invisible-amount reviewer rows on games
20–43, but cannot price the candidate's exposure on those rows. An issuer-side win is
therefore not a maximin total-net win. The 39-item latency case is also unmeasured.

## Locked comparison protocol

All three tracks used the same protocol rather than selecting their own favourable
denominators:

- Labels came only from `tools/thresholds.py`. A repeated export produced 485 identical
  rows through game 43; games 20–43 contain 221 rows, 169 finite ceilings, and fixed
  `BEST POSSIBLE = EUR 1,007,179.20`.
- For every belief, charge `a` came from
  `decide(belief, covered=True, clamp=None)`. No charge sum or limit sum was treated as
  euro impact.
- Track A and Track C were walk-forward by game: test game `g` used only training games
  `< g`. Track B was zero-shot and received no transaction or threshold values.
- The first test game was fixed at 20 before any track score was observed. The current
  price-book file was last changed before game 20, so its held-out baseline does not
  incorporate games 20–43. (Track A report lines 37–46; Track B report lines 78–96;
  Track C report lines 75–93.)

The prompt's 317-item, 137-under, 154-over price-book attribution remains a valid
historical population, but it is not this holdout. On the current common holdout, the
recomputed baseline is 89 under, 114 over, 18 unprovable, and SCORE 0.272898316898.
Mixing the two populations would make the comparison invalid. (Track A report lines
13–23.)

There is also live-data drift in realised tournament P&L. A fresh
`tools/score.py --actual` reports **EUR -430,982 and 1,158 unpriced rows through game
43**, not the brief's earlier EUR -163,687 snapshot. Neither realised-P&L number enters
the valuation SCORE. (Track A report line 50; Track B report lines 203–219.)

## Shared-metric results

| Candidate | Held-out SCORE | PROVEN INCOME | Under | Over | Unprovable | Decision |
|---|---:|---:|---:|---:|---:|---|
| Current price book | 0.272898316898 | EUR 274,857.51 | 89 | 114 | 18 | baseline |
| Track A fitted rates | 0.215632738401 | EUR 217,180.81 | 118 | 61 | 42 | NO-GO |
| Track B LLM, complete run 1 | 0.428313 | EUR 431,388.22 | 103 | 100 | 18 | unstable positive |
| Track B LLM, complete run 2 | **0.317164450879** | **EUR 319,441.44** | 100 | 99 | 22 | conservative candidate |
| Track C router + Track B run 2 | 0.315666330318 | EUR 317,932.56 | 103 | 97 | 21 | drop router |

The table is deliberately conservative. A charge receives income credit only when it
is at or below the proven floor; a charge above a finite ceiling receives zero; every
other charge is counted as unprovable and receives no credit.

## Track A: compact fitting is defensible but loses

Track A learned one multiplier per eligible `(trade, normalised unit)` cohort and
preserved the price book's sigma. Capacity was 11–14 parameters across folds; the
full descriptive fit had 14 parameters over 485 rows, or 34.643 raw rows per
parameter. The implementation therefore avoided the high-capacity failure mode that
motivated this work. (Track A report lines 25–35.)

It still failed held out. SCORE fell by **0.057265578497**, equivalent to EUR
57,676.70 less PROVEN INCOME on the fixed metric denominator. The fit cut proven
overcharges from 114 to 61, but increased under-floor charges from 89 to 118 and
unprovable charges from 18 to 42. This confirms the brief's diagnosis: removing
overcharging by broadly shrinking rate groups does not solve item-level
discrimination. (Track A report lines 13–23 and 62.)

No `Rate()` was added. Consequently `_generic_by_unit()` was not changed and the
`in_generic=False` constraint was not activated. Track A is rejected rather than
converted into a new rate table. (Track A report lines 35–36.)

## Track B: it beats the book, but the point estimate is unstable

Each valid run made one schema-constrained provider call per invoice and returned a
positive p10/p50/p90 gross-total band for every item. Missing, duplicate, non-finite,
zero, or unordered rows abstain; the effective candidate overlays only valid model
beliefs onto a complete price-book map. A provider error therefore degrades to the
book, never to zero or an absent belief. (Track B report lines 107–124 and 162–184.)

Both complete runs produced 221/221 beliefs with no missing or invalid outputs:

| Provider measurement | Run 1 | Run 2 |
|---|---:|---:|
| Calls | 24/24 successful | 24/24 successful |
| Input / output / total tokens | 12,169 / 6,053 / 18,222 | 12,169 / 6,114 / 18,283 |
| Invoice latency p50 / p95 / max | 1.864 / 3.876 / 4.863 s | 1.687 / 4.302 / 4.960 s |
| End-to-end wall clock, concurrency 3 | 18.305 s | 17.327 s |

Those are provider response metadata, not estimates. Request storage was disabled,
automatic retries were zero, concurrency was bounded at three, and each call had a
bounded deadline. Across research attempts, 72 calls were made: 48 belong to the two
complete measured runs; an earlier 24-call result was discarded after a local
post-call renderer failure and has unresolved usage metadata. (Track B report lines
126–160.)

The model's advantage is not stable enough to quote run 1 as the answer. SCORE changed
by **-0.111149**, or EUR -111,946.78 PROVEN INCOME, between otherwise identical runs.
The worse run still beats the price book by **0.044266133980 SCORE** and EUR 44,583.93
on the fixed proven-income denominator. This observed minimum—not the favourable
0.428313 run—is the basis for the shadow recommendation. (Track B report lines 16–41.)

The largest invoice in this holdout has 25 items. The observed latency cannot be
presented as a measurement of the separate 39-item maximum. (Track B report lines
148–152.)

## Track C: modest ranking signal, failed exact hybrid test

Track C used nine pre-outcome features and ten logistic parameters including the
intercept. Every fold refit on earlier games only. At the fixed 0.5 threshold, the
router achieved:

- ROC AUC 0.6458, game-block 95% interval [0.5724, 0.6959];
- precision 76.64% against 67.52% severe-error prevalence;
- recall 77.36%; and
- 148/221 items routed, a 66.97% all-item route rate.

This is modest separation, not a selective gate. (Track C report lines 8–14 and
95–122.)

Track C predeclared its falsifier: discard routing if an exact hybrid does not beat
the better unrouted valuer on the same items. The numeric-only join did exactly that.
On Track B run 2, the fixed router produced SCORE **0.315666330318** versus
**0.317164450879** for pure LLM, a change of **-0.001498120561** and EUR -1,508.88
PROVEN INCOME. The router is therefore excluded from the one recommended
configuration. No threshold sweep was used to rescue it after seeing the result.
(Track C report lines 128–138; evidence command D1 below.)

## Reviewer side and maximin boundary

The candidate replaces the complete belief, not merely charge `a`. At the current
1/2 acceptance quantile, the median sets `b`; run 2 raised `b` on 116 items and
lowered it on 105. The sanctioned `tools.score.score` API reports 918 unpriced
hidden-amount rows for both baseline and candidate across games 20–43. Equal counts do
not prove equal cost: the hidden amounts determine which newly raised limits would
accept fraud. (Evidence command D2; hidden-risk semantics at `tools/score.py:87-121`.)

Therefore the issuer metric establishes only an issuer-side lower bound. It does not
establish positive total-net P&L in the worst plausible reviewer case. The maximin
criterion blocks ACTIVE promotion until the invisible-amount exposure is bounded and
the worst point in that range remains positive. SHADOW evaluation is safe because it
does not replace the submitted price-book decisions.

This analysis did not run `tools/backtest.py`: the batched candidate is a research
benchmark, not an integrated rule, and pretending the existing rule path exercised it
would be another silent no-op. Any future integrated replay must explicitly use
`--allow-model-network --shadow`; no network-disabled pass counts as evidence.

## Configuration and pre-registered next gate

The only retained configuration is:

1. one whole-invoice, schema-constrained valuation request;
2. one p10/p50/p90 gross-total belief for every item;
3. strict response completeness and numeric validation;
4. item-level abstention on every invalid/missing output;
5. unconditional price-book fallback for each abstention or provider failure;
6. bounded timeout, bounded concurrency, no automatic retry, request retention off;
7. SHADOW only; no router and no fitted-rate multiplier.

Before any future data are inspected, the falsifier is fixed as follows: **on the next
strictly forward block of at least 100 sanctioned threshold items, if the candidate's
worst complete-run SCORE is less than or equal to the contemporaneous price-book
SCORE, discard the candidate.** No retuning on games 20–43 qualifies as new evidence.

Even if that valuation gate passes, ACTIVE promotion remains separately blocked until
a `tools.score.py`-reconciled maximin reviewer analysis is positive, the 39-item case
lands inside the tier-2 deadline, and timeout/provider-error shadow tests prove exact
price-book fallback. These are safety gates, not alternate configurations.

## Evidence ledger

### D1 — exact router join

Inputs were numeric-only `/tmp` exports. The join asserted exactly 221 identical
`(game,item)` identities, reconstructed beliefs, and called Track B's tested
`score_beliefs()`; that function calls production `decide()`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. .venv/bin/python <numeric-only join>
identity_count=221; routed_count=148; charge_replay_max_abs_error=0.0
pure_llm_repeat: SCORE=0.317164450879, income=319441.437905,
  under=100, over=99, excluded=22
router_llm_hybrid: SCORE=0.315666330318, income=317932.562036,
  under=103, over=97, excluded=21
hybrid_minus_pure: SCORE=-0.001498120561, income=-1508.875868
```

Implementation evidence: numeric export and exact production charge derivation are at
`tools/bench_llm_valuation.py:509-616`; router identity/score output is at
`tools/price_confidence.py:723-733`.

### D2 — reviewer-side sanctioned scorer

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. .venv/bin/python <tools.score.score API join>
games=20-43; limits_raised=116; limits_lowered=105; limits_unchanged=0;
baseline_unpriced=918; candidate_unpriced=918
```

The command constructed baseline and candidate `(a,b)` only through production
`decide()` and passed them to `tools.score.score`; it did not recreate transaction
payoff SQL.

### D3 — current realised tournament reconciliation

```sh
PYTHONPATH=. .venv/bin/python tools/score.py --actual
```

Observed total: `net=-430,982; unpriced=1,158`, through game 43. This is a separate
realised-tournament denominator.

### D4 — privacy and worktree boundary

The required global command was run before this report:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. .venv/bin/python tools/audit_worktree_privacy.py
```

It failed closed with `PrivacyAuditError` because the preserved pre-existing untracked
binary `.env.swp` is included by the worktree enumerator. It did not report a claim
text match. The file was not opened, modified, renamed, or removed. A final
path-scoped scan over the seven authorized source/report files is recorded after this
report is written.

```text
worktree_files_scanned=7; matching_worktree_files=0;
twelve_word_claim_shingle_matches=0; exact_item_description_matches=0
```

## Final verdict

**GO-AS-SHADOW-ONLY — one-call-per-invoice LLM on every item, no router, with exact
price-book fallback. The single deciding number is the worse observed held-out SCORE
0.317164450879 (22 unprovable), versus 0.272898316898, on 221 games-20–43 items and
EUR 1,007,179.20 fixed BEST POSSIBLE. The one measurement that falsifies it is a
pre-registered, strictly future >=100-item block whose worst complete-run SCORE does
not beat the contemporaneous price book.**
