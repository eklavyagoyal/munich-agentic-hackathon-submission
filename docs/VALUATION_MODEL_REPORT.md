# Per-line-item valuation model: evidence and promotion report

Status: complete through game 7. This report deliberately separates measured
results from unresolved questions. Real claim text and decrypted files exist only
below gitignored `data/`; none is reproduced here. The storage boundary is enforced
by `.gitignore:8-10` and the harvester writes the dataset below `data/harvest`
(`tools/harvest.py:517-529`).

## Pre-registered promotion criterion

The learned PRIOR remains SHADOW unless a leakage-free, game-forward backtest meets
all five gates below. This criterion was fixed before implementing or running the
model backtest.

1. Total counterfactual net score is strictly better than the current price-book
   strategy over every completed game available to the test.
2. The lower endpoint of a paired, game-level 95% bootstrap confidence interval for
   the net-score improvement is above zero.
3. Counterfactual insurer cost is no more than 5% worse than the price book.
4. Every out-of-distribution input abstains, and the rule engine demonstrably falls
   back to the price book.
5. The evaluation contains at least five held-out game groups and at least 30
   non-abstaining held-out line items; otherwise the evidence is declared too thin
   for promotion regardless of the point estimate.

If the payoff is only partially identified at a counterfactual price, gates 1-3 use
the conservative score bound. A point estimate is not permitted to turn an
unidentified result into a promotion. The SHADOW lifecycle itself is the loader's
default (`c2f/rules/loader.py:123-125`) and does not require a state-file change.

## Label derivation

For item `i`, let `t_i >= 0` be the secret threshold and let issuer `j` submit charge
`a_ij`. The payoff matrix defines four outcomes (`docs/MODEL_BRIEF.md:43-48`). For an
issuer/reviewer row that was rejected:

- positive `amount` means the issuer was nevertheless paid, which occurs only when
  `a_ij <= t_i`; the positive amount equals the fair charge and is an inclusive lower
  bound;
- zero `amount` occurs only for rejected fraud, so `a_ij > t_i`;
- an accepted row identifies `a_ij <= b` for that reviewer but, by itself, says
  nothing about `t_i`.

These branches are implemented without inferred defaults at
`tools/harvest.py:413-480` and are covered by synthetic tests in
`tests/test_harvest.py:23-62`. The classifier follows directly from the payoff
matrix, not from opponent rationality.

There is an important observability asymmetry. A rejected fraudulent row reports
zero, so the transaction feed does **not** reveal that submitted charge. If another
reviewer accepted the same issuer/item, its positive payment is `min(a_ij,c_i)`.
That payment is still a valid strict upper bound on `t_i`: `a_ij > t_i`, while a
binding cap satisfies `c_i >= 4t_i > t_i` for `t_i > 0`; when `t_i = 0`, any positive
payment is also strictly above it. If every reviewer rejected, the fraud label is
exact but no numeric upper bound is identified. The implementation preserves that
case as `fraud_issuers_without_price` instead of inventing a charge
(`tools/harvest.py:452-467`).

Accordingly, with `F_i` the observed fair charges and `Z_i` the positive payments
from classified fraudulent issuer/items,

```text
L_i = max({0} union F_i)
U_i = min(Z_i), or +infinity when Z_i is empty
L_i <= t_i < U_i.
```

The numeric bracket is exact under the documented payoff/cap contract. Other teams'
strategies determine how tight it becomes, but not whether an observed rejection is
on the fair or fraud side. Selection is therefore informative censoring: teams may
cluster charges around similar heuristics, so issuer labels must not be treated as
independent threshold samples. The model uses one interval per line item, not one
training row per issuer.

### Likelihood to be fitted

The model operates on per-unit rate `R_i = T_i / q_i` for positive finite quantity
`q_i`. On a fixed support grid `r_k` with probability masses `p_k(x_i)`, the
interval-censored log-likelihood is

```text
ell(p) = sum_i w_i log(sum_k p_k(x_i) * 1[L_i/q_i <= r_k < U_i/q_i]).
```

`U_i = +infinity` removes the upper test. A support point at zero represents the
coverage mass `P(T_i=0)`; a finite interval beginning at zero includes that mass.
An interval `[0,+infinity)` contributes no information and is retained for audit but
excluded from fitting. Game weights, rather than issuer weights, prevent a case with
many nearly identical field bids from masquerading as independent ground truth.

### Identifying assumptions and sensitivity

- The payoff table, shared item threshold, and guarantee `c >= 4t` hold as written
  (`docs/MODEL_BRIEF.md:33-48`). A cap-contract change would invalidate the proof
  that a capped positive fraud payment is an upper bound.
- `amount` is issuer receipt, as established in the brief
  (`docs/MODEL_BRIEF.md:223-241`). Every harvested issuer/item is checked for mixed
  paid/unpaid rejections and inconsistent positive payments; either condition fails
  the game rather than silently weakening the label (`tools/harvest.py:437-461`).
- Every ordered pair is present. The harvester unions each public team-filtered view,
  rejects conflicting duplicates, and requires exactly
  `items * teams * (teams - 1)` rows. Missing access or pagination therefore becomes
  an explicit failure (`tools/harvest.py:726-758`).
- Opponent charges need not be rational or independent for the bounds to remain
  valid. They do affect censoring width and any population-level extrapolation; the
  backtest must split by game and may not tune against one early field snapshot.
- A small finite upper bound is evidence for `t` near zero, not proof that `t=0`.
  Exact policy non-coverage is not identifiable from transactions unless an
  additional zero-threshold signal becomes available.

### Contrary evidence to the brief

The exact fair/fraud classifier in §5a is confirmed, but the displayed bracket in
`docs/MODEL_BRIEF.md:243-249` implicitly assumes every fraudulent submitted charge
is numerically visible. It is not: rejected-and-unpaid rows expose receipt `0`, not
the hidden charge, and some issuer/items were rejected by everyone. The dataset
therefore records qualitative fraud labels separately from numeric upper bounds.
This limitation is tested at `tests/test_harvest.py:39-46`.

## Dataset and candidate comparison

The final snapshot contains 67 line items from games 1-7 and 18,224 unique ordered
pair transactions. Forty-nine item intervals have finite upper bounds and 18 are
right-censored; 33 have a positive lower bound. The median finite bracket width is
EUR 45 gross, and the median per-unit width for the dominant `stk` class is EUR
49.25. (E1, E4)

Every game was fetched once per participating team, duplicate views were required to
agree, and the full matrix was required to contain exactly
`items * teams * (teams - 1)` rows. Archives are path-checked, extracted into a
temporary directory, and atomically published only with a completion marker
(`tools/harvest.py`, `validate_archive_members`, `ensure_extracted`, and
`all_transactions`; E1, E8).

The current price book specifically matches 21/67 items and leaves 46/67 on an
unknown-unit band. This challenges the stale statement in the brief that game 2 has
zero matches: the current code now matches 2/7 game-2 items. Reach has improved, but
69% of the accumulated dataset is still unknown. (E4)

I selected the unit-conditional interval model rather than TF-IDF. Only seven
independent game groups exist, while `stk` is the sole cohort meeting the fixed gate
of six informative rows across at least three games. A text model cannot currently
be tuned and evaluated by game without using essentially the same cases for both.
The dataset retains line description, damage context, and policy context under
gitignored `data/` so that choice can be revisited later. (E2; model gates are in
`c2f/estimate/interval_model.py`.)

The fitted magnitude candidate itself uses quantity and canonical unit only; case
context currently enters through the existing COVERAGE stage, not through learned
text coefficients. A genuinely context-conditioned learned model remains unresolved
because the game-level sample is too small for a leakage-free estimate. (E2, E4)

## Model and SHADOW rule

The model fits two related objects, with one interval per line item and total weight
one per game:

1. a grid NPMLE posterior over per-unit `t`, including a point mass at zero; and
2. a bounded lognormal magnitude model conditional on the COVERAGE stage having
   passed, because the existing `Belief` type cannot represent a zero-inflated
   mixture.

The second object is the PRIOR adapter; the first remains available in the research
artifact and supplies the zero-mass value recorded by the SHADOW rule. This
separation is explicit in
`c2f/estimate/interval_model.py` (`_fit_em`, `_fit_positive_lognormal`, and
`predict`) and in `rules_user/interval_valuation_prior.py`; it does not disguise
coverage uncertainty as a central price. (E2, E8)

On all seven games, only `stk` trains: 48 informative rows across seven games. The
central zero-mass fit is 0.251, but sensitivity fits range from 0.095 to 0.420 as the
zero-mass prior moves from 0.05 to 0.50. That spread confirms that exact policy
non-coverage is not identified by current transactions. Conditional on positive
coverage, the fitted median is EUR 34.53 per piece with log-sigma 2.780—very broad,
not a precise estimate. (E2, E3)

The new PRIOR has priority 20, but remains SHADOW because the loader defaults every
new rule to SHADOW and no `rules_state.json` was written. Missing artifacts, unknown
units, thin cohorts, invalid quantities, and quantities outside the observed cohort
range all abstain; the existing engine then uses the price book. Its `apply` method
does no I/O because the artifact is loaded once on the cold import path. (E7, E8;
`rules_user/interval_valuation_prior.py`.)

## Backtest

The split is strictly forward by game: for game `g`, the learned model sees only
games `< g`. Opponent actions are held at their observed values. Counterfactual
income and cost are reported as identified intervals: reviewer acceptance limits,
fraud charges, caps, and `t` are never midpoint-imputed. The exact branches are in
`tools/valuation_backtest.py` (`handyman_income_bounds`, `insurer_cost_bounds`, and
`run_backtest`) and have synthetic payoff tests. (E3, E8)

| game | items | model items | actual net | price-book net interval | model net interval |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 18 | 0 | -8,273.70 | [2,660.38, 46,438.76] | [2,660.38, 46,438.76] |
| 2 | 7 | 0 | -3,343.46 | [-41.81, 10,223.77] | [-41.81, 10,223.77] |
| 3 | 2 | 0 | -761.72 | [-600.59, 3,576.60] | [-600.59, 3,576.60] |
| 4 | 15 | 8 | 699.64 | [-150.71, 18,189.16] | [-5,942.45, -1,520.25] |
| 5 | 17 | 14 | -476.18 | [-488.50, 19,621.95] | [-7,973.02, -4,230.48] |
| 6 | 2 | 2 | 494.75 | [527.65, 7,073.25] | [-4,168.67, -3,978.79] |
| 7 | 6 | 6 | -5,668.42 | [-7,322.23, 66.02] | [-14,779.01, -14,647.46] |
| **total** | **67** | **30** | **-17,329.10** | **[-5,415.80, 105,189.51]** | **[-30,845.16, 35,862.15]** |

The learned model is worse on every game where it speaks, even at each model
interval's optimistic endpoint. Across games, sample variance of actual net is
11,734,230.93; price-book lower/upper net variance is 9,567,449.76 / 243,181,251.39,
and model lower/upper variance is 34,366,830.96 / 390,122,618.11. (E3)

Promotion therefore fails four independent gates: only four held-out games are
available (30 model items), conservative total improvement is -136,034.67, the
paired-game bootstrap 95% lower bound is -25,863.29, and the insurer-cost gate is
false. The rule remains SHADOW. (E3)

## Charge policy and measured field acceptance

For a hypothetical charge, opponent limits are interval-censored too. At EUR 100,
aggregate field acceptance is identified only as 20.1%-78.2%; even at EUR 500 it is
5.1%-64.9%. Thus the brief's statement that `F(a)` is measurable is true at an
actually observed issuer price, but a full counterfactual curve is only bounded
because rejected fraud often hides `a`. (E3; bound construction is
`tools/valuation_backtest.py`, `reviewer_limits` and `acceptance_curve`.)

On games 3-7, multiplying the current price-book charge by 1.5 maximizes the
worst-case income bound: EUR 51,042.61 versus EUR 42,323.53 at 1.0, a gain of EUR
8,719.08. Its lower bound is higher in all five games, but its total interval does
not dominate the current interval; the upper bounds overlap widely, and field
behaviour is still moving. (E3)

Recommendation: keep the current live `a` and `b`; do not promote the learned PRIOR.
If charge and acceptance are later decoupled without restructuring the current
round, test `a = 1.5 * current_charge` as a separate SHADOW-only experiment while
leaving `b` unchanged. The maximin result makes that the next charge experiment, not
evidence for a live switch. (E3)

## Image-only PDF and photo signal

The image-only PDF fatal path is closed locally. When `pdftotext` returns an empty
layer, the parser renders at most six pages to at most 2500 pixels, runs local English
Tesseract with five-second per-page deadlines, reconstructs columns from TSV bounding
boxes, and then applies the same strict contiguous-item validation. Missing binaries,
too many pages, empty OCR, malformed TSV, timeouts, and rendered-page-count mismatches
remain loud `ParseError`s. A rasterized synthetic invoice recovered every printed position and
quantity with no placeholder rows; the complete parser test file passes. (E6;
`c2f/ingest/parse.py`, `_ocr_pdf` and `_tsv_to_layout`.)

All seven completed cases contain a readable image, but there are only seven
independent case-level photos for 67 line-item labels and no line-item/photo mapping.
Using pixels now would create case leakage with no credible held-out estimate, so the
model records image metadata and deliberately drops photo content until more game
groups exist. (E4)

## Open questions resolved and unresolved

1. **`amount` semantics — resolved.** Exact actual-score reconstruction and all
   rejection cross-checks remain consistent with issuer receipt; rejected fair cost
   is reconstructed as `1.5 * amount`. (E1, E3;
   `tools/harvest.py:483-497`.)
2. **Rows not involving Oasis — resolved with nuance.** One team-filtered response
   contains only rows involving that requested team. Because `team` is public and
   accepts every participant name, unioning the 17 filtered views reconstructs the
   complete ordered-pair matrix; all seven games met the exact row-count invariant.
   (E1, E5)
3. **Bracket tightness — resolved for the current sample.** There are 49 finite and
   18 right-censored item intervals; median finite width is EUR 45 total and EUR
   49.25 per piece. It is still too loose for point scoring. (E4)
4. **Coverage versus magnitude — unresolved.** Twenty-eight rows have lower zero and
   a finite upper, but only one is bounded below EUR 10; none proves `t=0`. The fitted
   zero mass changes materially with its prior, so a coverage-error percentage would
   be invented. (E2, E4)
5. **Invoice language — partially resolved.** A fixed, published domain-marker
   heuristic identifies 22 English descriptions, zero German descriptions, and
   leaves 45 unresolved. It supports English coverage but does not prove invoices are
   always English. (E4; marker lists are in `tools/valuation_audit.py`.)
6. **Cap / charges above `4t` — partly resolved.** Thirty-nine positive fraud
   payments are at least four times their item's upper threshold bound, which proves
   the hidden submitted charge exceeded `4t`. Whether `c` actually bound is not
   identifiable because the feed exposes `min(a,c)`, not both `a` and `c`. (E4)
7. **Game status — resolved.** The live games endpoint emitted `active` for an
   in-progress game and `completed` afterwards; harvesting filters only exact
   `completed` status. (E5; `tools/harvest.py`, `completed_games`.)

The post-change comparison requested in §5a is measurable but not causal. Games 1-2
had income/cost/net per item of EUR 72.11 / 536.80 / -464.69; games 3-7 had EUR
1,020.93 / 1,156.93 / -136.00. Both income and cost rose sharply, and opponent fixes,
case mix, and our charge/limit change happened together, so the unknown-item prior's
isolated effect remains unresolved. (E4)

## Evidence ledger

All commands below print aggregates or synthetic data only; none prints a real
description, invoice, policy, photo, key, or raw transaction row.

- **E1 — final harvest and resumability:**
  `C2F_READONLY=1 PYTHONPATH=. .venv/bin/python tools/harvest.py --once --pause 0.1`
  and
  `C2F_READONLY=1 PYTHONPATH=. .venv/bin/python tools/harvest.py --offline --games 1-7 --stats`.
- **E2 — final model fit:**
  `C2F_READONLY=1 PYTHONPATH=. .venv/bin/python tools/train_valuation.py` plus
  `.venv/bin/python -c 'import json; c=json.load(open("data/valuation_model.json"))["cohorts"]["stk"]; print([(k, round(v["probabilities"][0],4)) for k,v in sorted(c["variants"].items())])'`.
- **E3 — score, variance, field curve, and charge sweep:**
  `C2F_READONLY=1 PYTHONPATH=. .venv/bin/python tools/valuation_backtest.py`; the
  command atomically writes the aggregate report `data/valuation_backtest.json`.
- **E4 — feature/label/open-question aggregates:**
  `C2F_READONLY=1 PYTHONPATH=. .venv/bin/python tools/valuation_audit.py`; the command
  atomically writes `data/valuation_audit.json` and never emits claim text.
- **E5 — live endpoint semantics:**
  `.venv/bin/python -c 'from c2f.leaderboard import Leaderboard; l=Leaderboard(); g=l.games(); print([(x.id,x.status) for x in g if x.status!="scheduled"])'`.
  Team-view filtering and union completeness are also enforced by E1.
- **E6 — image-only OCR:**
  `PYTHONPATH=. .venv/bin/python -m pytest tests/test_parse.py -q`.
- **E7 — SHADOW/OOD fallback:**
  `PYTHONPATH=. .venv/bin/python -m pytest tests/test_interval_model.py tests/test_interval_rule.py -q`.
- **E8 — derivation, archive safety, payoff bounds, and no-write structure:**
  `PYTHONPATH=. .venv/bin/python -m pytest tests/test_harvest.py tests/test_valuation_backtest.py -q`.
- **E9 — claim-data boundary:**
  `git check-ignore -v data/harvest/line_items.jsonl data/harvest/keys.json data/harvest/cases/case_001/invoices.pdf data/valuation_model.json data/valuation_backtest.json`.
