# Vision/XGBoost calibration promotion review

**Reviewed:** `origin/feature/vision-xgb-calibration` at
`add064e927fad7d75109d2b0341c9a15f04bbe38`

**Baseline:** `origin/main` at `3487e077bb7b7158d985b6065bdb4c0f68455786`

**Audit started:** 2026-08-22 18:54 UTC

**Final evidence refresh:** 2026-08-22 19:00 UTC

**Scope:** read-only review and isolated MockApi/provider measurements. No tournament
submission, daemon restart, promotion, source edit, or commit was made. This report is
the sole requested workspace output. [E1, E2]

## Verdict

**NO-GO. Do not promote this branch as the front-line Stage.PRIOR valuation model, and
do not merge the branch's runner as a shadow deployment.**

The single decision number is **0/24 strict temporal held-out games evaluated**. The
denominator is the frozen 24-game, 289-authoritative-line-item universe. The branch has
no game split, no temporal fold, no sanctioned backtest hook, and its live runner
explicitly bypasses the XGBoost/calibration/rule path. Therefore there is no candidate
euro delta that can honestly be put through `tools/score.py`, and maximin's required
worst-case-positive result does not exist. [E3, E4, E5, E7, E12]

This is stronger than “insufficient evidence.” The branch also fails the mandatory
outage invariant: with no provider, the exact 39-item real-case run produced a second
tier containing **39/39 `a=b=0` decisions**, overwriting the price-book first tier in
MockApi. That is the game-1 failure shape, not an abstention. [E9;
`add064e9:c2f/agents/coverage.py:66-81`;
`add064e9:c2f/agents/relatedness.py:73-100`;
`add064e9:c2f/agents/combine.py:38-76`;
`add064e9:c2f/runner.py:146-168`]

## The proposal and the code are not the same thing

The proposed change is “replace `pricebook_prior` at `Stage.PRIOR`.” The branch does
not implement that. Its XGBoost function returns category-level multiplicative
corrections that are consumed by `CalibrationBias`, whose declared stage is
`Stage.ADJUST` and whose verdict contains `scale`, not `belief`.
[`add064e9:c2f/calibrate.py:271-350`;
`add064e9:rules_user/calibration_bias.py:25-42`]

More decisively, the branch runner says and implements that `c2f/calibrate.py`, the
rule engine, `decision/quantile.py`, and `rules_user/*` are unused. The live path is a
new four-agent graph with fixed 0.75/0.87 shading. Consequently XGBoost has **zero
front-line invocations**, whether the rule is nominally ACTIVE or SHADOW.
[`add064e9:c2f/runner.py:1-14,23-28,127-168`;
`add064e9:c2f/agents/graph.py:1-37`;
`add064e9:c2f/agents/combine.py:16-22,38-76`]

The branch is also stale: it is one branch-only commit against 72 main-only commits,
and a three-way merge reports both-side changes in at least `c2f/ingest/parse.py`,
`c2f/runner.py`, `requirements.txt`, tests, and entrypoints. It is not a narrow model
promotion. [E2]

## 1. Overfitting

### Exact feature count and effective data ratio

The branch encoder has:

- 9 observed one-hot trade columns;
- 5 observed one-hot unit-class columns; and
- 3 numeric columns: labour flag, log quantity, and log baseline median.

That is **17 exact encoded features** on games 1–24. Against the requested 289
authoritative items, the headline ratio is **17.00 rows per feature**. [E4;
`add064e9:c2f/calibrate.py:216-242`]

That ratio is already flattering:

- `tools/thresholds.py` emits only 287 transaction-labelled items for games 1–24;
  two authoritative items have no rejection-derived evidence, so the labelled ratio
  is 287/17 = **16.88 independent items per feature**. [E5;
  `tools/thresholds.py:126-129`]
- The branch's actual event join recovers only 272 positive observed rows for games
  1–24, or **16.00 observed items per feature**, before requiring a matching bound.
  [E4]
- Expanding one item into several one-sided transaction bounds may increase the
  DMatrix row count, but those rows are repeated measurements of one game/item and do
  not increase the independent sample size. The sanctioned unit of evidence remains
  the game/item bracket. [`tools/thresholds.py:91-129`]

### Capacity configuration

| Setting | Branch value | Evidence |
|---|---:|---|
| `max_depth` | 3 | `add064e9:c2f/calibrate.py:309` |
| trees / `n_estimators` equivalent | 40 `num_boost_round` | `add064e9:c2f/calibrate.py:310` |
| learning rate | `eta=0.15` | `add064e9:c2f/calibrate.py:309` |
| L2 | `lambda=2.0` | `add064e9:c2f/calibrate.py:309` |
| L1 | not set | `add064e9:c2f/calibrate.py:309` |
| row subsampling | not set | `add064e9:c2f/calibrate.py:309-310` |
| column subsampling | not set | `add064e9:c2f/calibrate.py:309-310` |
| `gamma` / minimum split loss | not set | `add064e9:c2f/calibrate.py:309-310` |
| early stopping | none | `add064e9:c2f/calibrate.py:308-310`; E7 |
| validation/eval set | none | `add064e9:c2f/calibrate.py:308-323`; E7 |
| minimum data gate | only 20 bound rows | `add064e9:c2f/calibrate.py:38-42,299-300` |

This capacity is **not defensible** at this sample size. Forty depth-three trees can
form up to roughly 320 leaves before considering repeated boosting, versus 272 event
observations and no out-of-sample stopping criterion. More importantly, capacity is
never selected or tested on a game-held-out loss. The only XGBoost tests use synthetic
data generated from the same simple pattern they ask the model to recover.
[`add064e9:tests/test_calibrate.py:18-64`]

The deployed environment does not currently contain `xgboost`: the exact branch test
run reported that the complete XGBoost test module was skipped. `fit_xgboost()` catches
the missing import and silently returns `None`; there is no metric or alert that the
named model never ran. [E6; `add064e9:c2f/calibrate.py:284-288`]

## 2. Label leakage and temporal validity

There is **no split of any kind**. `fit_xgboost()` builds one DMatrix from every bound,
fits on it, and predicts category combinations derived from those same rows. There is
no game ordering, train/test partition, fold loop, evaluation set, or held-out metric.
[`add064e9:c2f/calibrate.py:290-323`; E7]

The tests are in-sample synthetic recovery tests. They create bounds and observations
together, fit on all of them, and assert only the direction of the returned correction.
They do not test a new game. [`add064e9:tests/test_calibrate.py:18-64`]

The label adapter is independently disqualifying. Its own source calls the wire format
a guess; it hand-interprets transaction rows and drops every accepted row.
[`add064e9:c2f/calibrate.py:106-132`] The sanctioned derivation establishes that an
accepted positive charge from an issuer already classified fraudulent supplies the
observable upper bound. [`tools/thresholds.py:91-125`] The candidate therefore trains
from a stale, incomplete label rule and does not consume `tools/thresholds.py` at all.

**Leakage verdict:** every model-quality headline is void. There are no strict temporal
headline figures to salvage: **0 train-games-1..k / test-game-k+1 evaluations exist**.
[E7]

## 3. Latency and failure semantics

### Measured successful path

I ran the exact branch graph against the real 39-item maximum case, with the configured
OpenAI backend, aggregate-only instrumentation, and no tournament API. All 42 provider
calls completed. [E8]

| Measurement | Result | Denominator |
|---|---:|---|
| per-price-item p50 | **2.940 s** | 39 A4 price calls |
| per-price-item p95 | **7.753 s** | 39 A4 price calls |
| slowest price call | **10.149 s** | 39 A4 price calls |
| 39-item graph wall clock | **27.311 s** | 39 prices + 1 image + 2 masks = 42 calls |
| successful provider calls | **42/42** | one observed real-case run |

This clears 52 seconds in that one observation, but it is a graph-only observation:
it excludes key-fetch and final submission latency and is not a p95 or worst-case
round guarantee. The 11-item cross-check took 11.759 seconds; its 11 price calls had
p50 3.112 seconds and p95 5.164 seconds. [E8]

The implementation has no graph-wide hard timeout. Level 1 awaits image, coverage,
and every price call; Level 2 then starts a relatedness call with another copy of the
same per-call timeout. [`add064e9:c2f/agents/graph.py:21-33`] The runner computes a
remaining budget once, passes up to 25 seconds into the graph, and does not check the
hard deadline again before tier-2 submission. [`add064e9:c2f/runner.py:150-168`]
Two sequential 25-second timeout phases plus decrypt, parse, and submission therefore
sit on the 52-second wall with no safety margin and no actual outer cancellation.

### Measured outage path

The required degradation contract fails:

| Injected condition | Observed result | Evidence |
|---|---:|---|
| no model backend, real 39-item case | graph returns successfully | E9 |
| first tier built | yes | E9 |
| second tier built after failures | yes | E9 |
| second-tier zero/zero decisions | **39/39** | E9 |
| second tier is last/overwriting tier | yes | E9 |

Why: A4 correctly returns no price and documents a per-item book fallback, but A2 and
A3 swallow provider failures and return empty masks. `combine.decide()` treats either
missing mask as false and emits zero/zero. Since no exception escapes, the runner's
“tier 1 stands on failure” handler never runs and it submits tier 2.
[`add064e9:c2f/agents/pricer.py:58-93`;
`add064e9:c2f/agents/coverage.py:66-87`;
`add064e9:c2f/agents/relatedness.py:73-100`;
`add064e9:c2f/agents/combine.py:38-76`;
`add064e9:c2f/runner.py:150-168`]

That is a direct **NO-GO**, regardless of average latency.

## 4. Abstention

There are two different failure paths, neither of which supports the proposal as
stated:

1. **XGBoost helper:** missing XGBoost or fewer than 20 rows returns `None`.
   `build_history()` then retains the older global/per-trade ratio fit, and the
   ADJUST rule itself returns `None` when no usable scale exists.
   [`add064e9:c2f/calibrate.py:278-300,335-351`;
   `add064e9:rules_user/calibration_bias.py:31-42`] That is not a Stage.PRIOR
   prediction and cannot replace `pricebook_prior`.
2. **Actual branch runner:** any missing coverage or relatedness answer becomes false,
   then zero/zero, and the result overwrites the price book. [E9 and sources in §3]

So the docstring-level claim “failure leaves tier 1 standing” is false on the caught
provider-error path. The exact executed failure path, not the stated intent, controls
the verdict.

## 5. Calibration of what

The XGBoost target is only a **point-scale multiplier** `M = bound_price /
previous_median`. It predicts `k`, clips it to `[0.5, 2.0]`, and applies it through
`Belief.scaled()`. It never predicts, fits, or modifies sigma.
[`add064e9:c2f/calibrate.py:271-332`;
`add064e9:rules_user/calibration_bias.py:31-42`;
`add064e9:c2f/core/models.py:85-91`]

Point calibration quality: **unmeasured out of sample**. There is no temporal fold,
no interval violation rate on held-out games, no median error metric, and no sanctioned
score delta. [E7]

Spread calibration quality: **not modelled and not measured**. The branch's new live
graph discards `Belief` entirely and uses fixed 0.75/0.87 shading around a single price.
[`add064e9:c2f/agents/combine.py:16-22,38-76`]

There is also contrary evidence to the premise in the question. On current main,
`ACCEPT_QUANTILE` is exactly 1/2 and the lognormal quantile is
`median * exp(sigma * NormalCDFInverse(q))`. At `q=1/2`, the inverse CDF is zero, so
`b` equals the median for every sigma. The executed check returned 100.0 for both
sigma 0.1 and sigma 1.0 at median 100. Sigma currently moves the charge `a`, but does
**not** move `b` at q=1/2. [`c2f/decision/quantile.py:21-35,84-85`;
`c2f/core/models.py:85-88`; E10]

The branch itself is stale at q=1/3, where sigma would affect `b`, but its runner
bypasses that quantile function anyway.
[`add064e9:c2f/decision/quantile.py:21,70-71`;
`add064e9:c2f/runner.py:1-14`]

## 6. Vision specifically

Vision contributes nothing to XGBoost: its 17 features contain only trade, unit class,
labour flag, quantity, and previous median. [`add064e9:c2f/calibrate.py:216-242`]

In the separate live graph, vision contributes only this chain:

1. A1 turns each photo into free text.
2. A2 combines those generated captions with damage text and emits a binary
   relatedness mask.
3. The mask is ANDed with policy coverage; false or missing zeroes both `a` and `b`.

[`add064e9:c2f/agents/images.py:27-56`;
`add064e9:c2f/agents/relatedness.py:43-100`;
`add064e9:c2f/agents/combine.py:38-64`]

The price agent does not receive images. It receives policy text, damage text, and one
line item. [`add064e9:c2f/agents/pricer.py:40-70`] The coverage agent is also text-only.
[`add064e9:c2f/agents/coverage.py:42-77`]

No real-data vision quality validation exists. The branch tests mock every model call
and explicitly say they test contracts, not model quality.
[`add064e9:tests/test_agents.py:1-5`] The local-VLM documentation records only a
synthetic smoke test and says one item's coverage was misjudged; it calls for shadow
comparison before unattended use. [`add064e9:docs/local-vlm.md:81-96`]

The sanctioned mask run in this audit used `C2F_BACKEND=none`; it reported “detector
never fired,” precision undefined, recall 0. That is an invocation-control result, not
candidate quality: `tools/validate_masks.py` targets main's ensemble, and this branch
provides no adapter for its A1/A2/A3 masks. [E12;
`tools/validate_masks.py:107-156`]

The prior real-data audit found readable text layers in 24/24 invoice PDFs and no
transaction-derived line-to-photo ground truth. Thus the PDF-rendering vision fallback
adds no demonstrated value on the frozen cases, and the only novel photo contribution
is the unvalidated high-impact binary mask. [`docs/VALUATION_MODEL_REPORT.md:134-135,247-256`]

The successful provider probes are not validation: the graph zeroed 4/39 items in the
maximum case and 2/11 in the cross-check, but no reliable visual ground truth says
whether those six gates were correct. [E8]

## Sanctioned-tool results

### `tools/score.py`

At the final 19:00 UTC evidence refresh, `tools/score.py --actual` reproduced the live
database's realised total as **-163,687 EUR over games 1–29**, with 1,079
rejected-fraud rows whose amounts remain unpriced. This is the only euro total reported
here; its denominator is the then-current 29-game database, not the frozen 24-game
modelling snapshot. [E12;
`tools/score.py:124-172`]

No candidate euro number is reported. The branch produces no compatible backtest run,
its XGBoost path is never invoked, and its graph changes both `a` and `b`. Reusing
actual issuer income would silently omit the 16x undercharge effect, while raising `b`
would introduce unknown rejected-fraud amounts. `tools/score.py` explicitly forbids
turning either omission into an exact result. [`tools/score.py:9-33,87-120`]

### `tools/thresholds.py`

The frozen first 289 rows still hash exactly to the supplied SHA-256
`7233612e70eff2bcbf23f41de8da2d31e3650dd954f73584b8ed2f1d4ff49bd7`.
The current file contains later games, so its full-file hash differs; the 1–24 prefix
is the frozen snapshot. [E15]

On games 1–24, the sanctioned tool emitted 287 labelled items: 192 positive lower
bounds, 212 finite upper bounds, 121 with both, and 404 bound endpoints. [E5] These are
the only labels accepted for this decision. The candidate does not use them.

### `tools/validate_masks.py`

The mandatory no-network control found no model invocation: precision undefined,
recall 0. It cannot validate this branch because the branch replaces the rule/ensemble
path rather than exposing a detector to the tool. [E12]

### `tools/backtest.py`

The mandatory 1–24 `--shadow` replay completed 24/24 cases under MockApi with
`C2F_BACKEND=none`, but it exercised current main and invoked this candidate zero times.
It is retained only as a control. Treating its 1.35-second runtime as candidate latency
would repeat the explicitly warned-about false pass. [E12]

Running main's backtest with `--allow-model-network` would invoke main's LLM ensemble,
not this branch's graph or XGBoost helper, so it would answer the wrong question. No
such misleading run was used.

## Maximin decision

The promotion rule requires a positive euro result at every plausible value of each
unknown parameter. [`docs/CLAIM_PIPELINE_PLAN.md:223-242`]

This candidate has no evaluable maximin curve:

- The low endpoint includes provider outage. The measured behavior is 39/39 zero/zero
  in the overwriting tier, not exact price-book fallback. [E9]
- The high-`b` side cannot be priced without sizes for rejected-fraud charges. The
  candidate has no compatible run from which `tools/score.py` can report the affected
  `unpriced` count. [`tools/score.py:29-33,107-116`]
- The issuer side changes `a`; actual income cannot be reused as candidate income, and
  charge sums are not euro impact. [`tools/score.py:9-21,95-99`]
- There are zero temporal held-out games, so even the observable point estimate is
  absent. [E7]

The worst case is therefore not demonstrated positive. Under the stated criterion,
that is an automatic NO-GO; substituting an average, a charge sum, or zero for the
unknown terms would be the exact error the criterion prohibits.

## Additional front-line blockers

1. **Real parser identity mismatch.** Against the same 289 authoritative rows, the
   branch parser produced 280 rows. Six games disagreed: game 11 (23 vs 22), game 15
   (27 vs 29), game 17 (18 vs 20), game 18 (11 vs 14), game 20 (4 vs 6), and game 23
   (2 vs 3). A valuation model cannot be promoted when its runner does not preserve the
   API's line-item identity/count. [E13]
2. **No current backtest integration.** The branch predates the sanctioned backtest
   and changes `Runner`'s constructor and decision path. Its XGBoost output is neither
   serialized nor loaded by the runner. [`add064e9:c2f/runner.py:45-56`;
   `add064e9:c2f/calibrate.py:335-351`; E2, E3]
3. **Silent dependency disablement.** `xgboost>=2.0` is added without a lock, while the
   deployed venv lacks it; ImportError silently turns the named model off. [E6;
   `add064e9:requirements.txt:5-7`;
   `add064e9:c2f/calibrate.py:284-288`]
4. **No rate-table blast radius in this commit.** The branch adds no `Rate()` entries,
   so the `in_generic=False` rule is not triggered. This is not a compensating benefit;
   it simply means that specific trap is absent. [E14]

## What would change this verdict

One measurement would change my mind:

> A real 24-game, strictly walk-forward run (train games `1..k`, predict only game
> `k+1`) in which the candidate is demonstrably invoked, its decisions are scored by
> `tools/score.py`, every raised-`b` result reports its `unpriced` count, the unknown
> charge-size parameter is swept over the predeclared plausible range, and the
> **worst-case total euro delta is greater than 0 EUR** on the 24-game denominator.

That run must additionally show exact price-book equality on no-backend, timeout, and
provider-error injections, and any vision gate used to zero or cap an item must pass
`tools/validate_masks.py` at precision at least 0.90 against proven ground truth. These
are validity conditions for the one euro measurement, not alternative decision
numbers. [`docs/CLAIM_PIPELINE_PLAN.md:223-242`]

## Evidence ledger

All commands were run from
`/Users/eklavyagoyal/Projects/hackathons/8-munich-agentic-hackathon`. Commands that
executed branch code used an isolated clone at `/tmp/c2f-vision-clone.2P4Mof`, detached
at `add064e9`; ignored outputs went to `/tmp` or the isolated clone.

- **E1 — branch identity and requested diff:**
  `git fetch origin feature/vision-xgb-calibration`;
  `git rev-parse origin/feature/vision-xgb-calibration`;
  `git diff --stat origin/main...origin/feature/vision-xgb-calibration`.
  Result: exact commit `add064e9`; 28 changed files, 1,768 insertions and 287 deletions,
  including `c2f/runner.py`.
- **E2 — ancestry/merge surface:**
  `git rev-list --left-right --count origin/main...origin/feature/vision-xgb-calibration`;
  `git merge-tree $(git merge-base origin/main origin/feature/vision-xgb-calibration) origin/main origin/feature/vision-xgb-calibration`.
  Result: `72 1`; both-side changes include parse, runner, requirements, tests, and
  entrypoints.
- **E3 — runtime reachability:**
  `git grep -n -E 'build_history|fit_xgboost|bounds_from_transactions|trade_bias' origin/feature/vision-xgb-calibration -- '*.py'` and
  `git show origin/feature/vision-xgb-calibration:c2f/runner.py | nl -ba`.
  Result: only calibrate/tests/rule references; runner explicitly bypasses them.
- **E4 — exact branch encoding audit:** aggregate-only execution of branch
  `match_rate`, `unit_class`, and `_meta_row` over the frozen 1–24 rows. Results:
  289 authoritative rows, 9 trades, 5 unit classes, 17 features, ratio 17.0. Branch
  `from_events()` on `data/events/tournament.jsonl`, filtered to games 1–24, recovered
  272 positive observations, ratio 16.0.
- **E5 — sanctioned labels:**
  `PYTHONPATH=. C2F_BACKEND=none .venv/bin/python tools/thresholds.py --jsonl > /tmp/c2f-thresholds-vision.jsonl` followed by aggregate-only `jq` filtering games
  1–24. Result: 287 labelled rows, 192 positive lowers, 212 finite uppers, 121 both,
  404 endpoints.
- **E6 — exact-commit tests:** in the isolated detached clone,
  `PYTHONPATH=. .venv/bin/python -m pytest -q -rs`.
  Result: 154 passed, 4 skipped; the XGBoost module was skipped because `xgboost` is
  not installed, and three rendering tests were skipped because `pymupdf` is absent.
- **E7 — split/early-stop search:**
  `git grep -n -E 'KFold|GroupKFold|TimeSeriesSplit|train_test_split|early_stopping|evals|eval_set|game_id|case_id' origin/feature/vision-xgb-calibration -- c2f/calibrate.py tests/test_calibrate.py`.
  Result: case IDs are only join keys; no split/eval/early-stop implementation.
- **E8 — aggregate-only real provider timing:** exact branch `graph.run_sync(case,
  timeout=25.0)` with a wrapper around `llm.ask_json` that recorded only call kind,
  elapsed time, success, and exception class. No prompts, responses, filenames, or
  claim text were printed or stored. Maximum case: 39 price calls, 42/42 total calls
  successful; price p50 2.940 s, p95 7.753 s, max 10.149 s, graph 27.311 s. Cross-check:
  11 price calls; p50 3.112 s, p95 5.164 s, graph 11.759 s.
- **E9 — exact failure path:** detached branch `Runner(MockApi, EventBus)` on the
  39-item case with `C2F_BACKEND=none`, aggregate-only output. Result: two tiers,
  last tier 2, 39/39 zero/zero, elapsed 0.0603 s. No HTTP submit method exists in the
  MockApi used.
- **E10 — q=1/2 sigma check:**
  `PYTHONPATH=. .venv/bin/python` evaluated `accept_limit(Belief(100, 0.1))` and
  `accept_limit(Belief(100, 1.0))`. Both returned 100.0.
- **E11 — vision reachability:**
  `git show add064e9:c2f/agents/{images,relatedness,coverage,pricer,combine}.py | nl -ba`
  and `git show add064e9:c2f/calibrate.py | nl -ba`. Result: only A1/A2 use photos;
  neither XGBoost nor A4 pricing has image features.
- **E12 — mandatory tools:**
  `PYTHONPATH=. C2F_BACKEND=none .venv/bin/python tools/score.py --actual`;
  `PYTHONPATH=. C2F_BACKEND=none .venv/bin/python tools/validate_masks.py --games 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24 --samples 1 --timeout 1`;
  isolated `tools/backtest.py --shadow --games 1-24 --cases-dir <real encrypted cases> --label vision-audit-shadow-control`.
  Results are reported in “Sanctioned-tool results.” `score.py --actual` was refreshed
  at 19:00 UTC after the live database advanced through game 29. The backtest used
  MockApi and no model network.
- **E13 — parser reconciliation:** aggregate-only branch `parse.build_case()` over
  existing decrypted games 1–24, compared by game/index count to the frozen harvest
  rows. Result: 280 branch rows versus 289 authoritative; six mismatch games listed
  above; no parse exception.
- **E14 — generic-rate check:**
  `git diff d969c56..add064e9 -U0 | rg '^\\+.*Rate\\('`.
  Result: no added `Rate()`.
- **E15 — frozen dataset identity:**
  `head -n 289 data/harvest/line_items.jsonl | sha256sum` and verification that row
  289 belongs to game 24. Result:
  `7233612e70eff2bcbf23f41de8da2d31e3650dd954f73584b8ed2f1d4ff49bd7`.

---

**FINAL: NO-GO — 0/24 strict temporal held-out games evaluated (denominator: 24
games / 289 authoritative line items). The one measurement that changes the verdict
is a `tools/score.py`-reconciled, strictly walk-forward, maximin worst-case euro delta
greater than 0 EUR on those 24 games, with zero unsafe fallback divergence and the
vision precision gate satisfied.**
