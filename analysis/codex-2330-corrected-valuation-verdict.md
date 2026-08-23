# Corrected valuation verdict — detector precision is the gate

UTC: 2026-08-22 23:30

Scope: offline research only. No submission, promotion, daemon restart, process stop,
or edit to `c2f/runner.py` was made.

## Decision

**NO-GO for handing either fitted rates or the whole-invoice LLM to the teammate as a
front-line replacement for `pricebook_prior`. Keep the price book unchanged. Retain the
LLM only as an offline candidate until its expensive-item mask passes the registered
precision gate.** Promotion in this repository is moot, and none was attempted.

The single number is **0.000 expensive-mask precision on the genuinely later games
44–47**, replicated in all three complete model draws. Each draw used the same 77
sanctioned-bracket items: 1 proven expensive, 56 proven below the EUR 1,200 target, and
20 unresolved. The actionable mask made 5, 6, and 6 positive predictions respectively;
it produced 0 true positives, 5/5/4 proven false positives, and 0/1/2 unresolved
predictions. Thus both proven precision and the conservative unresolved-as-false
precision were 0.000 in every draw. Evidence is command B3 below.

The one measurement that would change this recommendation is a **locked, strictly
forward expensive-item mask whose 95% Wilson lower bound on conservative precision is
at least 0.90** under `tools/validate_masks.py`, with no threshold selection after
viewing those games. The current fresh-holdout lower bound is 0.000.

For completeness, the recommended unchanged price-book configuration scores
**0.283863**, with 11 unprovable items, on the separate 77-item / EUR 405,224.48 fixed
BEST POSSIBLE denominator for games 44–47. Those euros are the specified conservative
PROVEN-INCOME denominator, not realised tournament P&L. Evidence is commands A2 and B3.

## What changed from the earlier synthesis

I accept all four corrections, with one evidence limitation stated rather than filled
with a guess.

1. A raise in `b` is not globally bad. The scenario analysis proves it remains positive
   in the `t_lo >= 1200` bucket even at four times the observed invisible-fraud mean,
   while the lower buckets are unsafe (`analysis/eklavya-2243-where-our-errors-live-by-item-value.md:152-174`).
   The relevant question is therefore where the model raises, not whether it raises.
2. Detector precision, not valuation SCORE, is the critical gate. The independent
   follow-up records the approximately 25x oracle-to-logged-rule gap at
   `analysis/eklavya-2312-the-overcharge-curve-closes-the-income-lever.md:78-92`.
   Commands M1, B1, and B3 below now measure the mask directly.
3. The fitted-rate mechanism does lower `b` at the expensive end. It does so on both the
   historical holdout and the genuinely later block; command A1/A2 quantify it.
4. Run variance changes the magnitude of the LLM's issuer-side advantage, not its sign
   on games 20–43. Five complete draws all beat the book. That variance is no longer a
   blocker; the detector failures are.

The evidence limitation: the exact five-bucket distribution of the original 116 raises
cannot be recovered. Its only numeric export was deliberately deleted after the prior
join (`analysis/codex-b-2214-track-b-llm-valuation.md:50-66`), and the synthesis retained
only `116 raised / 105 lowered` (`analysis/codex-d-2223-track-d-synthesis.md:215-225`).
No item identities or per-item limits were persisted. I will not manufacture that
distribution from a new stochastic draw. Three exact reproductions on the identical
221-item universe are reported next.

## Correction 1 — where the whole-invoice LLM raises `b`

Three new games-20–43 runs produced 114, 121, and 112 raises, close to the deleted
run's 116. The distribution is not economically safe:

| Complete draw | SCORE | Unprovable | All raises | 0–50 | 50–150 | 150–400 | 400–1200 | 1200+ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| R3 | 0.420789 | 15 | 114 | 41 | 26 | 17 | 24 | 6 |
| R4 | 0.346618 | 20 | 121 | 47 | 26 | 17 | 26 | 5 |
| R5 | 0.347920 | 18 | 112 | 42 | 27 | 17 | 20 | 6 |

In the three reproductions, 84/114, 90/121, and 86/112 raises—73.7%, 74.4%, and
76.8%—fell below `t_lo 400`, the region the maximin analysis says is strongly
negative. Only 5–6 raises per draw were in `1200+`. The model usually moved all six
top-bucket items upward, but surrounded those useful moves with many unsafe ones.
Command B1 emitted the bucket counts directly; command S1 performs the percentages.

The genuinely later block is worse:

| Complete draw, games 44–47 | All raises | 0–50 | 50–150 | 150–400 | 400–1200 | 1200+ |
|---|---:|---:|---:|---:|---:|---:|---:|
| F1 | 39 | 17 | 6 | 6 | 9 | 1 |
| F2 | 41 | 17 | 7 | 8 | 8 | 1 |
| F3 | 36 | 16 | 4 | 6 | 9 | 1 |

The sole fresh `1200+` item was raised in all three draws, but 26–30 proven-below-target
items were also raised. That is why direction alone has 2.4–2.8% conservative precision
on the fresh block. Command B3 produced these counts through production `decide()`.

## Correction 2 — validate the detector, not merely the price

The validator uses this locked ground truth:

- positive: `t_lo >= 1200`;
- negative: finite `t_hi <= 1200`, which proves the item lies below the target; and
- unresolved: every other sanctioned bracket.

It deliberately omits symmetric accuracy. The measured reviewer costs are asymmetric:
wrong rejection EUR 574.60 versus wrong acceptance EUR 202.70, and wrong rejection of
fair charges is 61% of reviewer cost
(`analysis/eklavya-2243-where-our-errors-live-by-item-value.md:15-53`).

### Logged `llm_prior` shadows

`tools/validate_masks.py` found 200 labelled items over the 20 games where
`prior.prefetched` proves the model path ran. Ground truth contains 7 positives, 142
negatives, and 51 unresolved items.

| Logged prediction definition | TP | FP | FN | Predicted unresolved | Conservative precision | Recall | 95% precision lower |
|---|---:|---:|---:|---:|---:|---:|---:|
| raises `b` and lands at EUR 1,200+ | 2 | 0 | 5 | 0 | 1.000 | 0.286 | 0.342 |
| any `b` raise | 4 | 24 | 3 | 8 | 0.111 | 0.571 | 0.044 |

The strict logged mask has a promising point estimate but only two positive calls; it
does not establish the 0.90 gate. Treating every raise as an expensive prediction fails
plainly. Both figures come from command M1, which invokes only
`tools/thresholds.py --jsonl` and the numeric event fields.

### Whole-invoice replacement on games 20–43

The stricter actionable mask—`to_b > from_b` and `to_b >= 1200`—also fails in every new
complete draw:

| Draw | TP | FP | FN | Predicted unresolved | Conservative precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| R3 | 3 | 7 | 3 | 1 | 0.273 | 0.500 |
| R4 | 4 | 8 | 2 | 2 | 0.286 | 0.667 |
| R5 | 4 | 8 | 2 | 2 | 0.286 | 0.667 |

The best observed conservative precision is 0.286, not the required 0.90. This is the
direct empirical form of the oracle-to-detector gap. Command B1 produced the confusion
matrices using the same scorer as command M1.

### Genuinely later games 44–47

The same locked mask produced **zero true positives in three of three draws**. It made
5, 6, and 6 positive calls, all either proven false or unresolved, while missing the
one proven expensive item each time. This is the principal NO-GO evidence; it is not a
retuned split and it is not an issuer-only proxy. Command B3 is the complete evidence.

## Correction 3 — fitted rates move the expensive end the wrong way

Track A is now negative twice, including a fresh temporal block:

| Strict temporal test | Price-book SCORE | Fitted SCORE | Delta | Book / fitted unprovable | Expensive-bucket movement |
|---|---:|---:|---:|---:|---|
| Games 20–43, 221 items | 0.272898 | 0.215633 | -0.057266 | 18 / 42 | lowered 5/6; mean `Δb=-158.30` |
| Games 44–47, 77 items | 0.283863 | 0.183973 | -0.099889 | 11 / 13 | lowered 1/1; `Δb=-219.59` |

The later fold fits 14 cohort parameters using only earlier games, then loses EUR
40,477.62 of PROVEN-INCOME numerator on the fixed EUR 405,224.48 denominator. That is
not tournament P&L. Reviewer scoring reports 161 invisible rows for both fresh-block
baseline and candidate, so it does not turn the issuer loss into an exact total-net
claim. Commands A1 and A2 are the sources.

This confirms the proposed mechanism more strongly than the earlier comparison to
`interval_valuation_prior`: fitted rates lower the only fresh `1200+` item and lose
issuer-side SCORE at the same time. There is no reason to hand off this approach.

## Correction 4 — variance is not the blocker

On the identical games-20–43 universe, the five complete whole-invoice scores are:

`0.428313, 0.317164, 0.420789, 0.346618, 0.347920`

The price-book baseline is 0.272898. All five draws win; the observed minimum is
0.317164, or +0.044266 SCORE. The median is 0.347920 and mean is 0.372161. An exact
enumeration of the 5^5 ordinary bootstrap resamples puts the 95% nearest-rank interval
for the sample mean at `[0.335097, 0.410469]`. This is descriptive with only five draws,
not a prospective guarantee, but it supports the correction: sign instability was not
observed. Commands B1 and S2 produce these values.

On the genuinely later 77-item denominator, three scores were 0.327480, 0.315628, and
0.285592 versus 0.283863. Again all three are positive, though the worst advantage is
only +0.001729. The issuer metric therefore remains interesting offline. It does not
override zero detector precision on the reviewer-critical mask.

## Handoff-ready configuration

The only configuration I recommend handing to the teammate is:

1. keep `pricebook_prior` as the active/front-line valuation rule;
2. keep fitted rates rejected;
3. keep the whole-invoice LLM offline, one call per invoice, with strict schema checks;
4. on every timeout, provider error, malformed response, missing item, or abstention,
   preserve the price-book belief—never zero and never absent;
5. evaluate an expensive-item mask independently of valuation SCORE, with precision as
   the gate and unresolved predictions counted conservatively; and
6. do not use Track C's symmetric severe-error router as the safety gate.

The model path itself was operationally healthy in these added measurements: 72/72
calls succeeded on the three new games-20–43 runs, and 12/12 succeeded on the three
fresh games-44–47 runs, with zero missing or invalid outputs. Calls were bounded at
concurrency three, automatic retries were zero, request storage was false, and each
call had a 45-second deadline. This establishes fallback-ready mechanics, not decision
quality. Commands B1/B3 provide the provider metadata; failure fallback is implemented
at `tools/bench_llm_valuation.py` in `aggregate_report()` and covered by its self-test.

No `Rate()` was added, so `_generic_by_unit()` and its `in_generic=False` hazard were
not touched. No rule state was changed.

## Denominator and euro discipline

Command P1 reconciles realised tournament net through game 47 as **EUR -454,207**, with
**1,158 unpriced** rejected-fraud rows. That is the only realised-tournament total in
this report.

Every other euro figure above is explicitly on the fixed PROVEN-INCOME denominator:
`16*a` only when `a <= t_lo`, zero for proven fraud, and zero credit for unresolved
charges. It is not realised income, cost, net, a charge sum, or a limit sum. Candidate
changes to `b` remain unpriced in exact euros because the hidden rejected-fraud amounts
are unavailable; this report uses the validated mask rather than pretending that risk
is zero.

## Evidence ledger

### K1 — local keys and sanctioned labels

```sh
C2F_READONLY=1 .venv/bin/python tools/backtest.py --verify
# all 48 held key(s) open their archive

.venv/bin/python tools/thresholds.py --jsonl | jq -s \
  '{rows:length,games:([.[].game]|unique|length),min_game:([.[].game]|min),max_game:([.[].game]|max)}'
# rows=562, games=47, min_game=1, max_game=47
```

No key fetch was needed because the cache was already complete. Verification is local;
`backtest.py` uses `MockApi` for replay and its key vault has no submit method
(`tools/backtest.py:1-29`, `tools/backtest.py:75-176`).

### A1 — historical Track A with b buckets

```sh
C2F_READONLY=1 .venv/bin/python tools/fit_rates.py --json | \
  jq '{baseline,candidate,score_delta,proven_income_delta,reviewer_side}'
```

This emitted the 221-item scores and exact bucket movements in the first row of the
Track A table. Labels are loaded by the sanctioned subprocess; split and decision code
are in `tools/fit_rates.py` (`load_thresholds`, `evaluate`, and
`limit_movements_by_bucket`).

### A2 — genuinely later Track A

```sh
C2F_READONLY=1 .venv/bin/python tools/fit_rates.py \
  --start-game 44 --end-game 47 --json | \
  jq '{evaluation,baseline,candidate,score_delta,proven_income_delta,reviewer_side}'
```

Observed: 77 rows; baseline/candidate SCORE 0.283862847833/0.183973466975;
unprovable 11/13; `1200+` lowered 1/1 by EUR 219.593231; unpriced 161/161.

### M1 — logged expensive-mask validation

```sh
C2F_READONLY=1 .venv/bin/python tools/validate_masks.py
C2F_READONLY=1 .venv/bin/python tools/validate_masks.py --prediction raise
```

The first command emitted TP/FP/TN/FN `2/0/142/5`, conservative precision 1.000,
recall 0.285714, Wilson lower 0.342380. The second emitted `4/24/118/3`, eight predicted
unresolved, conservative precision 0.111111, recall 0.571429, Wilson lower 0.044066.

### B1 — three more identical games-20–43 whole-invoice draws

The following was executed three times; `jq` allowed only aggregate metrics to stdout:

```sh
set -o pipefail
C2F_READONLY=1 C2F_STORE_LOGS=0 \
  .venv/bin/python tools/bench_llm_valuation.py \
  --allow-model-network --max-concurrency 3 --timeout-seconds 45 | \
  jq '{pricebook_baseline,llm_candidate,
       effective_candidate_with_pricebook_fallback,provider,reviewer_side,
       run_valid,wall_clock_seconds}'
```

The three complete outputs are the R3–R5 rows and mask matrices above. Total tokens
were 18,269 / 17,979 / 18,125; every run made 24/24 successful calls with no missing or
invalid item.

### B3 — three genuinely later games-44–47 whole-invoice draws

The following was executed three times:

```sh
set -o pipefail
C2F_READONLY=1 C2F_STORE_LOGS=0 \
  .venv/bin/python tools/bench_llm_valuation.py \
  --allow-model-network --start-game 44 --end-game 47 \
  --max-concurrency 3 --timeout-seconds 45 | \
  jq '{heldout,pricebook_baseline,llm_candidate,
       effective_candidate_with_pricebook_fallback,provider,reviewer_side,
       run_valid,wall_clock_seconds}'
```

The three complete outputs are F1–F3 and the fresh detector verdict above. Total tokens
were 5,219 / 5,026 / 5,106; every run made 4/4 successful calls with no missing or
invalid item.

### S1/S2 — arithmetic only

```sh
.venv/bin/python - <<'PY'
# S1: counts are B1 output
for raised, low in [(114,84),(121,90),(112,86)]:
    print(low / raised)

# S2: exact enumeration of the five observed-score bootstrap
import itertools, math, statistics
scores=[0.428313,0.317164,0.420789,0.346618,0.347920]
means=sorted(sum(x)/5 for x in itertools.product(scores, repeat=5))
q=lambda p: means[math.ceil(p*len(means))-1]
print(min(scores), statistics.median(scores), statistics.fmean(scores), q(.025), q(.975))
PY
```

### P1 — realised tournament reconciliation

```sh
C2F_READONLY=1 .venv/bin/python tools/score.py --actual
# total net -454,207; unpriced 1,158, through game 47
```

### V1 — safety, tests, and privacy

```sh
C2F_READONLY=1 .venv/bin/python tools/bench_llm_valuation.py --self-test
C2F_READONLY=1 .venv/bin/python tools/fit_rates.py --self-test
C2F_READONLY=1 .venv/bin/python -m pytest -q \
  tests/test_validate_masks.py tests/test_real_case_audit.py
PYTHONPATH=. C2F_READONLY=1 .venv/bin/python tools/audit_worktree_privacy.py
```

Observed before this report was written: benchmark 7 checks passed, fitted-rate
self-test passed, 21 focused tests passed, and the global privacy audit scanned seven
changed files with zero matching files, zero 12-word claim shingles, and zero exact
item-description matches. Final whole-worktree verification is repeated after writing.

Final verification after writing: the full suite passed **223 tests**; `py_compile` and
`git diff --check` passed; `c2f/runner.py` has no diff; and the global privacy audit
scanned 11 changed files with zero matching files, zero 12-word claim shingles, and
zero exact item-description matches. The extra worktree files include concurrent
teammate changes and were preserved rather than rewritten.

## Final verdict

**NO-GO — rests on fresh-holdout expensive-mask precision 0.000, denominator 77
sanctioned-bracket items per draw (1 positive / 56 negative / 20 unresolved), replicated
across three complete draws. Keep the price book front-line. The one result that changes
this is a locked strictly-forward `tools/validate_masks.py` run whose conservative
precision has a 95% Wilson lower bound at or above 0.90.**
