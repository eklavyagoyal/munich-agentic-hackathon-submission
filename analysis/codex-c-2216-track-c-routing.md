# Track C — can we identify the price-book items that are wrong by more than 2×?

**Snapshot:** 2026-08-22 22:16 UTC. **Held-out games:** 20–43. **Track verdict:**
there is **modest separation**, but not a selective enough hard gate. Pass the numeric
score to Track D as a soft ranking feature; do not treat the fixed 0.5 flag as an
operational router without pricing the exact hybrid.

The one-number summary is held-out ROC AUC **0.6458** on **157 bracket-adjudicable
items** (game-block bootstrap 95% interval **0.5724–0.6959**). At the fixed, untuned
0.5 threshold, precision is **76.64%** against **67.52%** class prevalence and recall
is **77.36%**, but it routes **148/221 = 66.97%** of every held-out item. Saving only
one third of expensive-path work for a 9.12 percentage-point precision lift is useful
triage, not a high-confidence gate.

## Target: proof, not imputation

For the production price-book belief I obtain `a` only through
`decide(belief, covered=True, clamp=None)`. Labels are loaded only by importing
`brackets()` from `tools/thresholds.py`; the harvested dataset's `label` field is
explicitly never accessed (`tools/price_confidence.py:163-206,209-252,305-357`).

For a bracket `[t_lo, t_hi)`:

- **severe underpricing (positive):** `a < t_lo / 2`;
- **severe overpricing (positive):** finite `t_hi` and `a > 2 * t_hi`;
- **proved not severe (negative):** finite `t_hi`, `a >= t_hi / 2`, and
  `a <= 2 * t_lo`, which rules out both positive conditions for every threshold in
  the bracket;
- **ambiguous:** everything else. Ambiguous rows are excluded from classification
  metrics and are never relabelled as correct (`tools/price_confidence.py:255-277`).

Held out, that gives **50 severe-under, 56 severe-over, 51 proved-not-severe, and 64
ambiguous** rows: 157/221 (**71.04%**) are adjudicable. The positive prevalence among
adjudicable rows is 106/157 (**67.52%**). This high prevalence is why precision must be
compared with 67.52%, not with 50%.

## Common price-book baseline

On held-out games 20–43, using the user-specified fixed denominator:

| metric | current deterministic price book |
|---|---:|
| items with a sanctioned `t_lo` | 221 |
| provably undercharged (`a <= t_lo`) | 89 |
| provably overcharged (finite `t_hi`, `a > t_hi`) | 114 |
| excluded / unprovable | 18 |
| PROVEN INCOME | **EUR 274,857.51** |
| BEST POSSIBLE | **EUR 1,007,179.20** |
| SCORE | **0.27289832 (27.2898%)** |

This is a **proven-income denominator**, not realised tournament P&L. It is calculated
exactly as `16*a` only when `a <= t_lo`, zero when finite `t_hi` proves `a > t_hi`,
and excluded otherwise (`tools/price_confidence.py:583-606`). The prompt's 317-item
price-book baseline and cumulative -163,687 are an older/different snapshot and must
not be mixed with this held-out reconstruction. A fresh
`PYTHONPATH=. .venv/bin/python tools/score.py --actual` reports realised net
**-430,982** with **1,158 unpriced** through game 43; that is separately reconciled
realised P&L and is not used anywhere in the router metric.

## Signal and temporal protocol

The signal is a deliberately small, class-balanced L2 logistic model: **9 features,
10 parameters including the intercept**, fixed L2 0.10, fixed learning rate 0.05,
1,200 deterministic batch iterations, and fixed route threshold 0.5. The score is a
risk ranking, not a calibrated probability (`tools/price_confidence.py:52-69,413-453`).

Only pre-outcome features are present:

1. generic fallback;
2. unrecognised unit;
3. log price-book band width;
4. longest compatible keyword coverage of the item text;
5. number of compatible matching rates;
6. longest-versus-second-longest keyword margin;
7. log quantity;
8. robust quantity extremity within the historical unit class; and
9. log price-book median total.

No policy, damage, transaction, acceptance, payment, threshold, or future-game value
is a model feature. Text is consumed only to compute non-identifying match statistics
and is never emitted (`tools/price_confidence.py:284-302,360-402`).

Every test game `g` fits a fresh model on adjudicable games `< g`; quantity reference
statistics also use all feature rows strictly below `g`. The first fold, game 20,
uses 160 adjudicable training rows through game 19 (**16.0 rows/parameter**). The last,
game 43, uses 314 through game 42 (**31.4 rows/parameter**). All 24 recorded folds have
`max_train_game < test_game`; there is no random/item split and the threshold is not
tuned on held-out outcomes (`tools/price_confidence.py:609-646,697-720`).

One methodological caveat: before the first model run I inspected held-out aggregate
class cardinality and source-by-class counts to validate that the target was
non-empty. I fixed the prompted feature family and the 0.5 threshold before observing
any router score. The implementation is mechanically leakage-free, but this is not a
pristine never-looked-at holdout and should not be presented as one.

## Held-out separation

At route score `>= 0.5`:

| | actually severe | proved not severe |
|---|---:|---:|
| routed | TP **82** | FP **25** |
| kept on book | FN **24** | TN **26** |

- Precision: **82/107 = 76.64%**.
- Recall: **82/106 = 77.36%**.
- Specificity: **26/51 = 50.98%**.
- Severe-under recall: **37/50 = 74.00%**.
- Severe-over recall: **45/56 = 80.36%**.
- Evaluated-item flag rate: **107/157 = 68.15%**.
- All-item flag rate: **148/221 = 66.97%**; this includes **41/64 ambiguous** rows,
  whose correctness is intentionally unknown.
- ROC AUC: **0.6458**; 2,000-replicate game-block 95% interval
  **[0.5724, 0.6959]**.
- Average precision: **0.7786**; game-block 95% interval
  **[0.7141, 0.8430]**.

The individual prompted heuristics are weak. With direction fixed before scoring,
held-out ROC AUC is 0.596 for wider bands, 0.595 for generic fallback, 0.584 for weak
keyword margin, 0.570 for weak keyword coverage, 0.532 for quantity extremity, and
0.509 for an unrecognised unit. “More matching-rate ambiguity means more risk” is
actually inverted here (AUC 0.393). The composite extracts some interaction, but the
game-block interval and 67% route rate rule out calling this a sharp discriminator.
The calculations, tie-safe ROC/AP implementations, and cluster bootstrap are at
`tools/price_confidence.py:456-580,650-692`.

## Recommendation to Track D

Use the per-item numeric `route_score` only as an input to an **exact hybrid replay**
with the better Track A/B candidate. Do not infer a euro gain from precision/recall,
and do not promote the binary 0.5 gate merely because AUC exceeds 0.5. Running the
tool without `--aggregate-only` emits only `{game, item, route_score, route, target}`
for all 221 held-out items—no claim text (`tools/price_confidence.py:723-733`).

The falsifier is straightforward: if a strictly walk-forward hybrid using these
scores does not improve the shared **PROVEN INCOME / BEST POSSIBLE** score over the
better unrouted A/B candidate on the same 221-item denominator, routing adds no value
and should be dropped. Given today's broad flag rate, that is the expected outcome
unless the expensive candidate is much better specifically in the top-score tail.

## Evidence, safety, and reproducibility

Inputs were self-identified as 487 feature rows and 485 sanctioned threshold rows;
dataset SHA-256 is
`56098b426062d3f56e89d19a59b5aa75b061418d9d3d7d672840d6c848f29b64`, and the
canonical bracket SHA-256 is
`edc40ac0fd5cda1e6d037a66df629c5a1e885d9b72a2df2ed56c1c3cf24aa9bf`.
The tool verifies `C2F_READONLY=1`, opens SQLite read-only/query-only, bounds input
sizes, validates identities and numeric fields, fails on contradictory brackets, and
prints no raw item text (`tools/price_confidence.py:130-252,769-806`).

Commands used:

```text
rg -q '^C2F_READONLY=1([[:space:]]*(#.*)?)?$' .env
PYTHONPATH=. .venv/bin/python tools/thresholds.py --jsonl
PYTHONPATH=. .venv/bin/python tools/score.py --actual
PYTHONPATH=. .venv/bin/python tools/price_confidence.py --self-test
PYTHONPATH=. .venv/bin/python tools/price_confidence.py --aggregate-only
PYTHONPATH=. .venv/bin/python -m py_compile tools/price_confidence.py
git diff --check -- tools/price_confidence.py analysis/codex-c-2216-track-c-routing.md
```

The mandatory whole-worktree `tools/audit_worktree_privacy.py` was run before this
report and failed closed with `PrivacyAuditError` because the unrelated pre-existing
untracked `.env.swp` is a non-text changed file. It was preserved and never opened.
Running the same auditor logic path-scoped to `tools/price_confidence.py` before the
report found **0 matching files, 0 twelve-word claim shingles, and 0 exact item
descriptions**. A final path-scoped scan covers both authorized outputs; root will run
the global audit after coordinating the shared worktree.

No API request, model-provider request, submission, process signal, daemon restart,
configuration change, commit, or promotion was made.
