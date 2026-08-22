# Track A — fitted rate corrections

UTC run: 2026-08-22 22:15

Repository HEAD at start: `b49dccc9830cc22db0a2329693abb036a9d84f7f`

Decision: **NO-GO** for replacing or modifying the active price-book prior.

## Result on the common held-out denominator

The fixed evaluation set is every sanctioned threshold row in games 20–43: 221 items. `BEST POSSIBLE` is identical for both candidates and all euro amounts in this table are on the special **PROVEN INCOME denominator**, not tournament P&L. The baseline charge and candidate charge both come from the exact production call `decide(belief, covered=True, clamp=None)`. (E1; `tools/fit_rates.py:458-484`; `tools/fit_rates.py:550-585`)

| belief | SCORE | PROVEN INCOME | BEST POSSIBLE | under | over | excluded / unprovable |
|---|---:|---:|---:|---:|---:|---:|
| production price book | **0.272898316898** | **274,857.51** | 1,007,179.20 | 89 | 114 | 18 |
| temporally fitted rates | **0.215632738401** | **217,180.81** | 1,007,179.20 | 118 | 61 | 42 |

The candidate loses **0.057265578497 SCORE**, or **57,676.70 of PROVEN INCOME on this fixed 1,007,179.20 denominator**. It converts many certain overcharges into conservative charges—the over count falls 114→61—but it also charges too little on more items and moves 24 additional items into the no-credit unprovable region. Fewer proven overcharges is therefore not the same as more proven income. (E1; `tools/fit_rates.py:466-479`; `tools/fit_rates.py:658-662`)

The brief's 137-under / 154-over / 317-item price-book figures are historical and are not the same denominator as this required games-20–43 walk-forward comparison. I cannot reproduce them on the common denominator: the directly recomputed production baseline is 89 under / 114 over / 18 unprovable across 221 items. I do not mix the historical counts with the held-out headline. (E1)

## What was fitted

This is deliberately a correction table, not a flexible item model. Each eligible `(production trade match, normalized unit)` cohort learns exactly **one scalar multiplier** on the existing price-book median. The existing item-specific price-book sigma is preserved. Routing uses the production match and unit normalization; the learned capacity is the number of eligible cohort scales, not one parameter per item or keyword. (`tools/fit_rates.py:309-315`; `tools/fit_rates.py:436-455`)

Eligibility was locked before the held-out run: at least six numerically informative brackets, at least three distinct training games, and at least one lower-bound and one finite-upper-bound observation. The center is found by maximizing a ridge-regularized interval-censored log-likelihood over a bounded scale range `[0.125, 8]`; right-, left-, and interval-censored rows have separate likelihood cases. Thin or one-sided cohorts abstain to the unchanged price-book belief. (`tools/fit_rates.py:59-66`; `tools/fit_rates.py:358-445`; `tools/fit_rates.py:448-455`)

Capacity is small enough to be statistically discussable:

- game 20 used 11 learned parameters from 264 prior threshold rows: **24.00 raw rows/parameter**;
- game 43 used 14 parameters from 481 prior rows: **34.357 raw rows/parameter**;
- the descriptive full-data fit has 14 parameters against all 485 rows: **34.643 raw rows/parameter** (478 numerically informative, 34.143 informative rows/parameter).

These counts are emitted from the same folds that produce the metric; the full-data fit is never used to score a held-out row. The capacity is defensible relative to the cited 17-feature/272-row failure, but defensible capacity cannot rescue negative held-out performance. (E2; `tools/fit_rates.py:550-577`; `tools/fit_rates.py:629-690`)

No `Rate()` was added or proposed by the tool. Consequently this experiment cannot mutate `_generic_by_unit()` at all; if a later implementation materializes any fitted cohort as a new `Rate()`, it must explicitly use `in_generic=False`, because the generic band includes only rates whose flag is true. (`c2f/estimate/pricebook.py:20-34`; `c2f/estimate/pricebook.py:204-223`)

## Label provenance and leakage audit

All 485 labels come only from a subprocess invocation of `tools/thresholds.py --db … --jsonl`, with bounded runtime/output and strict shape/duplicate validation. The feature loader reads `game_id`, item identity, description in memory for production matching, quantity, and unit; it never indexes the harvested row's derived `label` field. The resulting feature snapshot has 487 rows across games 1–43 and SHA-256 `56098b426062d3f56e89d19a59b5aa75b061418d9d3d7d672840d6c848f29b64`. (E1; `tools/fit_rates.py:179-242`; `tools/fit_rates.py:245-306`; sanctioned derivation at `tools/thresholds.py:84-129`)

The split is strictly expanding by game. For each test game `g` in 20–43, training selects only rows with `game < g`, asserts that its maximum training game is below `g`, fits new cohort scales, and then scores only game `g`. The emitted fold audit confirms `training_game_max = test_game - 1` for every one of the 24 folds; game 20 begins with games 1–19 and game 43 ends with games 1–42. There is no random, item-level, or same-game split. (E2; `tools/fit_rates.py:550-577`)

The sanctioned tool itself derives a lower bound only from rejected-yet-paid charges and a finite upper bound only when a fraudulent issuer's charge is visible; accepted-only items are discarded. I did not recreate that transaction logic. (`tools/thresholds.py:84-129`)

## Reviewer-side risk

Scaling the median also scales `b` because the production acceptance quantile is 1/2. Across the 221 held-out parsed items, the candidate lowers 171 limits, raises 31, and leaves 19 unchanged. The `tools.score.score` API reports **918 unpriced hidden rejected-fraud rows** for both baseline and candidate over games 20–43. That count does not price what happens on raised limits, so an exact reviewer-side euro delta remains unresolved and this result is not active-promotion evidence. (E2; `c2f/decision/quantile.py:35`; `c2f/decision/quantile.py:84-107`; `tools/fit_rates.py:487-516`; `tools/fit_rates.py:604-638`; hidden-risk semantics at `tools/score.py:87-121`)

For denominator hygiene, a fresh `tools/score.py --actual` run through game 43 reports actual tournament net **−430,982** and **1,158 unpriced**. That makes the brief's −163,687 context stale. Neither actual number is used in the fitted-rate SCORE or its PROVEN INCOME amounts. (E3; total formatting at `tools/score.py:148-172`)

## Safety and reproducibility

The CLI fails closed unless `.env` contains exactly one `C2F_READONLY=1`, bounds dataset and threshold sizes, rejects malformed/non-finite inputs and duplicate identities, imposes a 30-second threshold subprocess deadline, and emits no claim text. (`tools/fit_rates.py:45-66`; `tools/fit_rates.py:146-242`; `tools/fit_rates.py:245-306`)

Normal output contains aggregate metrics; `--json` additionally emits numeric per-item records keyed only by game/item, with no descriptions or other claim text, so Track D can combine routes without persisting claim content. (`tools/fit_rates.py:586-601`; `tools/fit_rates.py:810-819`)

The global privacy CLI is presently blocked—not failed on a text match—because the preserved, pre-existing untracked `.env.swp` is a non-text file and `audit_worktree_privacy.py` intentionally rejects every changed non-text file. I did not open, remove, or modify it. Before this report was written, a path-scoped call to the same `scan_files` implementation over `tools/fit_rates.py` returned zero matching files, zero 12-word claim shingles, and zero exact eligible item-description matches. The post-report path-scoped scan over both authorized files returned the same three zeroes. (E4, E6; rejection rule at `tools/audit_worktree_privacy.py:67-88`)

## Verdict

**NO-GO.** The single deciding number is **−0.057265578497 held-out SCORE**, on the fixed 221-item, games-20–43, `BEST POSSIBLE = 1,007,179.20` PROVEN INCOME denominator. The one measurement that would change this verdict is a preregistered correction model beating **0.272898316898** on genuinely unseen future games while retaining price-book fallback and reporting reviewer-side hidden-risk counts; retuning against games 20–43 after observing this result would not qualify.

## Evidence ledger: exact commands and outputs

**E1 — locked held-out headline**

```sh
PYTHONPATH=. .venv/bin/python tools/fit_rates.py
```

```text
features: 487 rows, sha256=56098b426062d3f56e89d19a59b5aa75b061418d9d3d7d672840d6c848f29b64
sanctioned threshold rows: 485
held-out games: 20-43
baseline: SCORE=0.272898, PROVEN INCOME=274857.51, BEST POSSIBLE=1007179.20, under=89, over=114, excluded=18
candidate: SCORE=0.215633, PROVEN INCOME=217180.81, BEST POSSIBLE=1007179.20, under=118, over=61, excluded=42
delta: SCORE=-0.057266, PROVEN INCOME=-57676.70
capacity: fold parameters 11-14; full fit 14 parameters, 34.64 raw rows/parameter
reviewer hidden-amount risk: baseline unpriced=918, candidate unpriced=918 (tools.score.score API)
```

**E2 — machine-readable fold/capacity/reviewer audit**

```sh
PYTHONPATH=. .venv/bin/python tools/fit_rates.py --json | .venv/bin/python -c \
  'import json,sys; x=json.load(sys.stdin); print(json.dumps({"baseline":x["baseline"],"candidate":x["candidate"],"delta":x["score_delta"],"capacity":x["capacity"],"reviewer":x["reviewer_side"],"folds":x["folds"]},indent=2,sort_keys=True))'
```

Relevant aggregate output: baseline `score=0.272898316898`; candidate `score=0.215632738401`; `score_delta=-0.057265578497`; fold parameters 11–14; first-fold raw rows/parameter 24.0; last-fold 34.357143; full fit 14 parameters over 485 rows; all 24 records have `training_game_max < test_game`; reviewer limits raised/lowered/unchanged = 31/171/19 and baseline/candidate unpriced = 918/918.

**E3 — current tournament reconciliation, separate denominator**

```sh
PYTHONPATH=. .venv/bin/python tools/score.py --actual | tail -n 4
```

```text
  41     18,636     86,445     -67,808       0
  42     28,565     54,362     -25,797       0
  43          0      9,052      -9,052       0
 TOT                          -430,982    1158
```

**E4 — privacy scan before report**

```sh
PYTHONPATH=. .venv/bin/python tools/audit_worktree_privacy.py
# output: {"error_class": "PrivacyAuditError"}; diagnosed from
# tools/audit_worktree_privacy.py:67-88 as the preserved non-text .env.swp

PYTHONPATH=. .venv/bin/python - <<'PY'
import json
from pathlib import Path
from c2f.estimate.interval_model import load_rows
from tools.audit_worktree_privacy import scan_files
print(json.dumps(scan_files(load_rows(), [Path('tools/fit_rates.py')]), sort_keys=True))
PY
```

```text
{"exact_item_description_matches": 0, "matching_worktree_files": 0, "twelve_word_claim_shingle_matches": 0, "worktree_files_scanned": 1}
```

**E5 — deterministic checks**

```sh
PYTHONPATH=. .venv/bin/python tools/fit_rates.py --self-test
.venv/bin/python -m py_compile tools/fit_rates.py
```

```text
fit_rates self-test: ok
# py_compile exited 0 with no output
```

**E6 — post-report privacy scan**

```sh
PYTHONPATH=. .venv/bin/python - <<'PY'
import json
from pathlib import Path
from c2f.estimate.interval_model import load_rows
from tools.audit_worktree_privacy import scan_files
paths = [Path('tools/fit_rates.py'), Path('analysis/codex-a-2215-track-a-fitted-rates.md')]
print(json.dumps(scan_files(load_rows(), paths), sort_keys=True))
PY
```

```text
{"exact_item_description_matches": 0, "matching_worktree_files": 0, "twelve_word_claim_shingle_matches": 0, "worktree_files_scanned": 2}
```
