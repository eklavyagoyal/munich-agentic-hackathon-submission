# Per-line-item valuation model: evidence and promotion report

Status: complete through game 24. The model remains **SHADOW**. This report contains
only aggregate results and synthetic-test references; decrypted documents, keys, raw
transactions, and line descriptions remain below gitignored `data/` (`.gitignore:6-10`,
`.gitignore:30-43`; E1, E9, E16).

## Outcome

The original brief's seven deliverables exist: an idempotent harvester, written
transaction-label derivation, distributional per-line model, SHADOW PRIOR rule,
partially identified backtest, predeclared promotion gate, charge-policy analysis,
and bounded local OCR fallback. The current evidence rejects promotion:

- 24 completed games and 289 authoritative line items were harvested;
- the model produces 213 held-out predictions across 21 games;
- conservative total net improvement is EUR -5,849,929.21;
- the paired game-bootstrap 95% lower endpoint is EUR -778,036.27;
- the insurer-cost gate fails;
- the current maximin charge multiplier is 1.0, so there is no measured basis for
  the earlier 1.5x charge experiment.

All figures above come from E1–E4. The promotion decision is therefore **FAIL / remain
SHADOW**. This work changed no rule state, daemon, scheduler, submission client, or
live submission.

## Predeclared promotion criterion

The PRIOR may leave SHADOW only if a leakage-free, game-forward backtest passes all
five gates:

1. Conservative total counterfactual net is strictly better than the current active
   rule-stack baseline over every completed game in the frozen evaluation snapshot.
2. The lower endpoint of a paired, game-level 95% bootstrap interval for net-score
   improvement is above zero.
3. Counterfactual insurer cost is no more than 5% worse than baseline.
4. Every unsupported/out-of-distribution input abstains and falls through to the
   price book.
5. At least five held-out games and 30 non-abstaining held-out lines are available.

When score is partially identified, gates 1–3 use the conservative bound; midpoint
imputation is forbidden. New rules default to SHADOW at
`c2f/rules/loader.py:83-89` and `c2f/rules/loader.py:118-125`.

## Written label derivation

For item `i`, secret threshold `t_i`, issuer `j`, and submitted charge `a_ij`, a
rejected transaction identifies the side of `t_i` exactly:

- rejected and paid: `a_ij <= t_i`; the positive receipt exposes the fair charge and
  supplies an inclusive lower-bound candidate;
- rejected and unpaid: `a_ij > t_i`; the fraud classification is exact, but the zero
  receipt hides the submitted charge;
- accepted alone: `a_ij <= b_reviewer`; it is not a fair/fraud label.

If another reviewer accepted the same issuer/item already proven fraudulent, its
positive receipt is `min(a_ij,c_i)` and is a valid strict upper bound on `t_i`: the
game guarantees both `a_ij > t_i` and `c_i >= 4t_i`. The harvester requires all
positive receipts for that issuer/item to agree and rejects mixed paid/unpaid
rejections (`tools/harvest.py:415-482`; E8).

Therefore, for exposed fair charges `F_i` and positive receipts attached to classified
fraudulent issuer/items `Z_i`:

```text
L_i = max({0} union F_i)
U_i = min(Z_i), or +infinity when Z_i is empty
L_i <= t_i < U_i
```

The likelihood fitted on per-unit threshold rate `R_i=T_i/q_i` is:

```text
ell(theta) = sum_i w_i log P_theta(L_i/q_i <= R_i < U_i/q_i)
```

`U_i=+infinity` is right censoring. `[0,+infinity)` is retained for audit but adds no
likelihood information. Weights are normalized by game because invoice lines within
one game share context and field behaviour. Other teams' strategies affect censoring
tightness, not the logical validity of an observed rejection label
(`c2f/estimate/interval_model.py:237-302`, `tools/harvest.py:415-482`; E2, E8).

### What labels do not prove

`L_i=0` does not mean `t_i=0`. Even `L_i=0, U_i<=176` proves only a low threshold,
not policy exclusion, unrelated scope, or visual contradiction. Current transactions
cannot isolate coverage error from positive-magnitude error. This challenges tools
and documents that call such rows “proven worthless”; they are low-threshold proxies
(`tools/validate_masks.py:60-87`; E4).

### Identity reconciliation discovered on real data

Parser row identity and transaction identity are not always the same. Across 24
decrypted cases, the parser emitted 291 rows, including two explicit placeholders;
the complete transaction matrices identify 289 tournament items. One gap is trailing
and one is internal. The internal server identity remains non-contiguous after the
gap, so reindexing later parsed rows would silently attach features to the wrong
labels.

The harvester now permits exactly one safe reconciliation: every server index must
map to a parsed row, and every parser-only row must have the explicit synthetic
placeholder marker. It preserves surviving server indices, including gaps, and fails
on a missing or non-synthetic excess row (`tools/harvest.py:502-538`,
`tools/harvest.py:834-850`; E1, E8). This is contrary evidence to the earlier
contiguous-index assumption.

## Dataset

The frozen snapshot has 24 completed games, 289 authoritative item rows, and 78,608
unique ordered-pair transactions. Its `line_items.jsonl` SHA-256 is
`7233612e70eff2bcbf23f41de8da2d31e3650dd954f73584b8ed2f1d4ff49bd7` (E14). All overlapping records across the 17 public
team views per game agree, and each union has exactly `items * teams * (teams - 1)` rows
(`tools/harvest.py:767-804`; E1).

| aggregate | measured |
|---|---:|
| finite upper bounds | 212 |
| right-censored intervals | 77 |
| positive lower bounds | 192 |
| zero-lower, finite-upper intervals | 91 |
| zero-lower intervals bounded at EUR 10 or below | 18 |
| finite-bracket median width | EUR 38.30 |
| specific price-book matches | 116 / 289 (40.14%) |
| unknown price-book matches | 173 / 289 (59.86%) |
| fixed-marker English descriptions | 108 |
| fixed-marker mixed descriptions | 4 |
| unresolved language | 177 |
| German-only marker classifications | 0 |

These are E4 aggregates. “Unresolved” is not imputed as English. The price book has
improved substantially from the brief's early zero-match observation, but the
majority of rows still lack a specific trade match.

The real document-shape audit separately found 24/24 readable invoice text layers,
24/24 policies and damage descriptions, and 23/24 cases with an image. It found no
invoice currency markers; all three money-shaped decimal tokens were parsed
quantities, not prices (`tools/audit_real_cases.py:194-425`; E12). Valuation remains
from scratch.

## Model and SHADOW rule

The dependency-free CPU model fits:

1. a discrete interval-censored posterior over per-unit `t`, including a zero support
   point; and
2. a bounded positive lognormal magnitude model used by the existing `Belief` API.

The zero mass is retained for research and is not disguised as a lognormal median.
The PRIOR rule loads the artifact once, performs no I/O in `apply`, and abstains on
missing artifacts, unsupported units, thin cohorts, invalid quantities, or quantities
outside the training range (`c2f/estimate/interval_model.py:358-497`,
`rules_user/interval_valuation_prior.py:1-43`; E2, E7).

Three of 289 rows have unrecognized units. Real-data training initially failed the
entire artifact on the first such row. Training now validates their numeric fields,
counts them as `excluded_rows_by_reason=unrecognised_unit`, fits all supported rows,
and leaves prediction for those units abstained (`c2f/estimate/interval_model.py:165-187`,
`c2f/estimate/interval_model.py:358-430`; E2, E7).

| unit cohort | informative rows | games | central zero mass | sensitivity range | positive median rate | log sigma |
|---|---:|---:|---:|---:|---:|---:|
| `h` | 24 | 10 | 0.089 | 0.026–0.189 | EUR 57.13 | 0.680 |
| `lm` | 8 | 5 | 0.057 | 0.014–0.143 | EUR 32.83 | 0.969 |
| `m2` | 18 | 7 | 0.074 | 0.020–0.170 | EUR 27.19 | 1.076 |
| `pauschal` | 72 | 15 | 0.261 | 0.104–0.422 | EUR 24.35 | 3.000 |
| `stk` | 158 | 23 | 0.170 | 0.076–0.267 | EUR 40.28 | 2.863 |

The `pauschal` positive fit hits the maximum permitted sigma, and `stk` remains very
wide at 2.863. Both are signs of weak magnitude information rather than precision.
All values are E2.

## Leakage-free backtest

For validation game `g`, the candidate is fitted only on games `<g`. Baseline is the
current active rule snapshot with SHADOW rules excluded; candidate inserts only the
fold-trained PRIOR. Opponent actions are held observed. Unknown `t`, fraud charge,
cap, and reviewer limits remain bounds—never midpoint guesses
(`tools/valuation_backtest.py:405-461`, `tools/valuation_backtest.py:607-710`; E3, E8).

| game | items | model items | actual net | baseline net interval | model net interval |
|---:|---:|---:|---:|---:|---:|
| 1 | 18 | 0 | -8,273.70 | [11,586.76, 54,306.11] | [11,586.76, 54,306.11] |
| 2 | 7 | 0 | -3,343.46 | [3,078.92, 18,681.99] | [3,078.92, 18,681.99] |
| 3 | 2 | 0 | -761.72 | [-577.15, 3,216.49] | [-577.15, 3,216.49] |
| 4 | 15 | 8 | 699.64 | [-1,167.97, 23,763.05] | [-3,461.83, 5,809.07] |
| 5 | 17 | 14 | -476.18 | [5,569.00, 29,443.72] | [-2,609.72, 3,510.97] |
| 6 | 2 | 2 | 494.75 | [7,877.54, 8,996.87] | [-2,177.87, -1,860.33] |
| 7 | 6 | 6 | -5,668.42 | [3,893.80, 20,352.18] | [-10,128.93, -8,077.06] |
| 8 | 39 | 25 | -1,769.26 | [-11,797.91, 39,871.40] | [-26,834.17, -11,348.93] |
| 9 | 16 | 16 | -6,586.39 | [-4,880.57, 6,578.43] | [-8,377.07, -5,720.50] |
| 10 | 6 | 5 | -59,968.29 | [-61,004.14, -52,732.88] | [-65,268.29, -60,472.62] |
| 11 | 22 | 14 | 9,660.84 | [6,607.25, 36,235.86] | [5,486.83, 17,059.83] |
| 12 | 12 | 12 | -30,039.68 | [-32,175.89, -20,234.56] | [-34,990.75, -34,489.11] |
| 13 | 17 | 13 | -6,910.91 | [-10,352.34, 20,501.35] | [-18,122.50, 16,514.20] |
| 14 | 13 | 13 | -2,016.17 | [-4,774.81, 14,611.38] | [-702.01, 3,922.89] |
| 15 | 29 | 25 | 11,869.08 | [-14,111.80, 38,408.89] | [-12,802.97, -7,398.38] |
| 16 | 2 | 2 | 71.03 | [-341.36, 3,216.49] | [-47.10, 900.70] |
| 17 | 20 | 13 | -9,955.08 | [-1,898,546.06, 3,201,496.62] | [-1,900,293.22, 3,183,725.72] |
| 18 | 14 | 13 | -22,996.25 | [-26,079.83, -18,520.90] | [-33,614.14, -31,689.75] |
| 19 | 9 | 9 | 5,309.50 | [-3,958.72, 40,527.57] | [-7,167.31, -3,017.28] |
| 20 | 6 | 6 | -11,102.08 | [-13,844.63, -5,558.34] | [-24,556.78, -22,887.67] |
| 21 | 2 | 2 | 2,084.65 | [2,058.97, 3,001.45] | [613.39, 850.77] |
| 22 | 1 | 1 | 4,422.50 | [-26,342.81, 33,099.86] | [3,068.85, 6,629.95] |
| 23 | 3 | 3 | -2,304.15 | [-2,304.06, 7,635.13] | [-1,570.19, -1,570.19] |
| 24 | 11 | 11 | -11,364.72 | [-15,817.06, 689.52] | [-29,997.76, -28,899.67] |
| **total** | **289** | **213** | **-148,924.49** | **[-2,266,027.30, 3,530,379.64]** | **[-2,319,549.57, 3,115,837.67]** |

Across-game sample standard deviation is EUR 14,682.25 for actual net. For the
partially identified bounds, endpoint standard deviations are EUR 417,812.64 / EUR
653,436.58 for baseline lower/upper and EUR 417,723.97 / EUR 653,156.32 for model
lower/upper. These describe variation across games, not standard errors; game 17
dominates the bound-endpoint dispersion (E3).

The huge game-17 intervals are not typographical errors: partial identification plus
an unsafe unknown-unit fallback produces extreme exposure. They are retained because
clipping them out would make the strategy look safer than it is. E3 is the source of
every table value.

Promotion fails three substantive gates despite passing sample size:

| gate | result |
|---|---|
| held-out evidence | PASS: 21 games / 213 predictions |
| conservative net improvement | FAIL: EUR -5,849,929.21 |
| paired-game bootstrap 95% lower endpoint | FAIL: EUR -778,036.27 |
| insurer cost no more than 5% worse | FAIL |
| OOD abstention/fallback | PASS in synthetic tests |

The rule remains SHADOW (E3, E7).

## Charge policy and field acceptance

Counterfactual field acceptance is itself interval-censored because rejected fraud
hides the submitted charge. Across 4,624 reviewer/item pairs, acceptance at EUR 100
is bounded at 28.72%–69.77%; at EUR 500 it is 7.16%–54.35%. The curve is measurable
at observed bids but not point-identified at arbitrary charges (E3;
`tools/valuation_backtest.py`, `reviewer_limits` and `acceptance_curve`).

On games 3–24, the current 1.0 multiplier maximizes the lower income bound. No tested
higher multiplier improves that lower bound in any game, and no candidate interval
dominates the current one. This reverses the earlier nine-game 1.5x recommendation.
The evidence-based recommendation is: **keep the current charge policy; do not run a
1.5x canary** (E3).

## Image-only PDF and photo signal

The image-only-PDF path is closed for supported local tooling. On an empty text layer,
the parser renders at most six pages, bounds rendered size, runs local English
Tesseract with five-second per-page deadlines, reconstructs layout, and applies the
same strict row parser. Missing binaries, excess pages, bad TSV, timeouts, empty OCR,
and render-count mismatch are loud failures (`c2f/ingest/parse.py:90-184`; E6).

All 24 real invoices currently have readable text layers, so real OCR accuracy remains
unverified. The rasterized synthetic test passes. Twenty-three of 24 cases have readable
image dimensions, but transactions supply no line-to-photo truth. Pixels therefore
remain outside the promoted valuation model; a separate multimodal plan treats image
results as diagnostic/SHADOW until locally labelled precision exists (E4, E6, E12).

## Open questions

1. **Amount semantics:** resolved under the current payoff/API contract by E1/E3 and
   `tools/harvest.py:415-498`.
2. **Rows outside one team view:** resolved. Unioning all 17 public team views yields
   complete matrices for all 24 games (`tools/harvest.py:767-804`; E1).
3. **Bracket tightness:** current finite median width is EUR 38.30, but 77/289 rows
   remain right-censored (E4).
4. **Coverage versus magnitude:** unresolved. Ninety-one rows have zero lower and a
   finite upper, but none proves `t=0`; component labels require policy/scope review
   (E4).
5. **Invoice language:** partly resolved by a fixed heuristic: 108 English, four mixed,
   177 unresolved, zero German-only. This does not prove English-only invoices (E4).
6. **Cap binding:** unresolved. 230 positive fraud payments are at least four times
   their item's upper threshold bound, but the feed exposes `min(a,c)`, not both `a`
   and `c` (E4).
7. **Photo usefulness:** unresolved. There are 24 case groups and no line/photo truth;
   no real-case VLM benchmark was run (E4, E12).
8. **Strategic fraud-zone charging:** current maximin sweep says stay at 1.0, but field
   behaviour can change as teams adapt; rerun on every frozen snapshot (E3).
9. **Game status semantics:** unresolved. The most recent cached games response
   contained `completed` and `scheduled` states but no observed `running` state, so
   absence of `running` cannot establish whether it is transient or unsupported.
   Harvesting therefore keys only on explicit `completed` (`tools/harvest.py:576-621`;
   E5).

## Operational safety finding

`tools/backtest.py --shadow` previously controlled only rule state; it did not prevent
Runner's model prefetch from using a credential loaded from `.env`. During this audit,
a replay was mistakenly started without forcing the backend off and interrupted after
several provider attempts. It used `MockApi` and never submitted to the tournament,
but some remote valuation calls completed. The tool now forces the model backend to
`none` by default and requires `--allow-model-network` for explicit egress
(`tools/backtest.py:1-29`, `tools/backtest.py:60-72`; E13). The final replay and all
reported valuation results used `C2F_BACKEND=none`.

Both ignored decryption-key caches now have mode `0600`. The replay vault rejects
malformed, duplicate, oversized, or control-bearing entries and uses an fsynced atomic
replace for private writes (`tools/backtest.py:75-142`; E15). Key contents were never
printed.

## Evidence ledger

All commands below emit aggregates or synthetic data only. None prints a key,
description, invoice/policy text, image, or raw transaction row.

- **E1 — harvest, GET-only pass, and offline resumability:**
  `C2F_READONLY=1 PYTHONPATH=. .venv/bin/python tools/harvest.py --once --pause 0.1`,
  then `C2F_READONLY=1 PYTHONPATH=. .venv/bin/python tools/harvest.py --once --offline --pause 0`,
  and `C2F_READONLY=1 PYTHONPATH=. .venv/bin/python tools/harvest.py --stats --offline`.
- **E2 — CPU model fit:**
  `C2F_READONLY=1 C2F_BACKEND=none PYTHONPATH=. .venv/bin/python tools/train_valuation.py`.
  The ignored artifact is `data/valuation_model.json`.
- **E3 — walk-forward score bounds, bootstrap, field curve, charge sweep:**
  `C2F_READONLY=1 C2F_BACKEND=none PYTHONPATH=. .venv/bin/python tools/valuation_backtest.py --bootstrap-samples 10000`.
  The ignored artifact is `data/valuation_backtest.json`.
- **E4 — feature/label/open-question aggregates:**
  `C2F_READONLY=1 C2F_BACKEND=none PYTHONPATH=. .venv/bin/python tools/valuation_audit.py`.
  The ignored artifact is `data/valuation_audit.json`.
- **E5 — live status semantics:**
  `jq -r '.items | group_by(.status) | map({status:.[0].status,count:length})' data/harvest/games.json`.
- **E6 — bounded synthetic OCR:**
  `PYTHONPATH=. .venv/bin/python -m pytest tests/test_parse.py -q`.
- **E7 — model/OOD/SHADOW rule:**
  `PYTHONPATH=. .venv/bin/python -m pytest tests/test_interval_model.py tests/test_interval_rule.py -q`.
- **E8 — derivation, reconciliation, scorer, archive, and payoff bounds:**
  `PYTHONPATH=. .venv/bin/python -m pytest tests/test_harvest.py tests/test_valuation_backtest.py -q`.
- **E9 — claim-data boundary:**
  `git check-ignore -v data/harvest/line_items.jsonl data/harvest/keys.json data/harvest/cases/case_001/invoices.pdf data/valuation_model.json data/valuation_backtest.json data/valuation_audit.json`.
- **E10 — full regression:**
  `C2F_READONLY=1 PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`.
- **E11 — source/worktree boundary:**
  `git status --short`, `git rev-parse HEAD`, `git rev-list --left-right --count origin/main...HEAD`, `git diff --check`, and `git diff -- c2f/runner.py`.
- **E12 — aggregate decrypt/document audit:**
  `C2F_READONLY=1 PYTHONPATH=. .venv/bin/python tools/audit_real_cases.py --games 1-24`.
- **E13 — local-only replay safety:**
  `C2F_READONLY=1 C2F_BACKEND=none PYTHONPATH=. .venv/bin/python tools/backtest.py --verify --games 1-24 --shadow --label mm-plan-audit-24-local`
  and `PYTHONPATH=. .venv/bin/python -m pytest tests/test_readonly.py -q`.
- **E14 — frozen dataset identity:**
  `jq -c '.training_snapshot' data/valuation_model.json` and
  `jq -c '.snapshot' data/valuation_backtest.json`. The identity fields are produced
  by `c2f/estimate/interval_model.py:138-162` and `tools/valuation_backtest.py:792-796`.
- **E15 — key-cache hygiene:**
  `.venv/bin/python -c 'from pathlib import Path; print({str(p): oct(p.stat().st_mode & 0o777) for p in (Path("data/keys.json"), Path("data/harvest/keys.json"))})'`
  and `PYTHONPATH=. .venv/bin/python -m pytest tests/test_readonly.py -q`.
- **E16 — worktree claim-text guard:**
  `C2F_READONLY=1 C2F_BACKEND=none PYTHONPATH=. .venv/bin/python tools/audit_worktree_privacy.py`.
  It reported zero matching worktree files, zero 12-word claim-text shingles, and
  zero exact eligible (≥5-word) item-description matches across 14 changed text files; the scanner emits
  counts only (`tools/audit_worktree_privacy.py:40-155`).
