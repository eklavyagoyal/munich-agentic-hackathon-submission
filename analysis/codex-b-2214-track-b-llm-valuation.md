# Track B — invoice-level LLM as the whole valuation prior

UTC timestamp: 2026-08-22 22:14

Repository: Oasis, read-only tournament mode

Held-out games: 20–43 inclusive

## Verdict

**GO-AS-SHADOW-ONLY.** The candidate beats the price book on the mandated issuer-side
metric, but it is not safe to make ACTIVE because the same beliefs move reviewer limit
`b` and that counterfactual—including its invisible-amount fraud rows—remains unpriced.

Two complete provider runs both beat the price book, but they were materially unstable:
SCORE was **0.428313** in run 1 and **0.317164** in run 2 versus **0.272898** for the
book. The second result is 0.111149 below the first on the identical fixed denominator
of 221 line items and EUR 1,007,179.20 BEST POSSIBLE. These euros are on the prompt's
conservative proven-income denominator; they are not realised tournament net euros.

## Result on the mandated metric

The price-book baseline is stated first, as required:

| Held-out result, games 20–43 | Price book | LLM run 1 | LLM run 2 / router export |
|---|---:|---:|---:|
| SCORE | 0.272898 | **0.428313** | **0.317164** |
| PROVEN INCOME | EUR 274,857.51 | **EUR 431,388.22** | **EUR 319,441.44** |
| BEST POSSIBLE, fixed | EUR 1,007,179.20 | EUR 1,007,179.20 | EUR 1,007,179.20 |
| Foregone versus fixed best | EUR 732,321.69 | EUR 575,790.98 | EUR 687,737.76 |
| Provably undercharged / certainly fair | 89 | 103 | 100 |
| Provably overcharged / certainly fraud | 114 | 100 | 99 |
| Excluded or unprovable | 18 | 18 | 22 |
| Model abstentions | n/a | 0 | 0 |
| Denominator items | 221 | 221 | 221 |

Run 1 improves PROVEN INCOME by EUR 156,530.71; run 2 improves it by EUR 44,583.93.
Both amounts use this metric denominator and are not tournament P&L claims. The
EUR 111,946.78 run-to-run drop is direct evidence that one stochastic call is not a
stable valuation rule even though both observations beat the book.

Run 1 evidence command (its aggregate-only temporary output was removed):

```sh
PYTHONPATH=. .venv/bin/python tools/bench_llm_valuation.py \
  --allow-model-network --max-concurrency 3 --timeout-seconds 45 \
  > /tmp/c2f-track-b-aggregate.json
```

Run 2 and claim-safe router export command:

```sh
PYTHONPATH=. C2F_STORE_LOGS=0 .venv/bin/python tools/bench_llm_valuation.py \
  --allow-model-network --include-item-metrics \
  --max-concurrency 3 --timeout-seconds 45 \
  > /tmp/oasis-track-b-items.json
```

The run 2 file existed only at `/tmp/oasis-track-b-items.json` while Track D performed
the numeric join, then was removed after synthesis. Its 221 rows contained only
game/item identity, price-book charge, LLM charge, effective charge, LLM median, LLM
sigma and a fallback boolean. Validation found 221 unique identities, the exact
declared schema and zero string values in any row. It contained no threshold,
description, unit, trade, policy, damage text, prompt or raw response. The opt-in
export is implemented at `tools/bench_llm_valuation.py:574-616` and serialized at
`tools/bench_llm_valuation.py:773-787`.

The scorer is implemented at `tools/bench_llm_valuation.py:509-551`: it invokes
`c2f.decision.quantile.decide(belief, covered=True, clamp=None)` and implements the
three mandated branches without substituting charge sums or limit sums. The fixed
denominator is checked at `tools/bench_llm_valuation.py:634-635`.

The 317-item / 137-under / 154-over figures in the research prompt are a historical,
different attribution population. They are useful context but are not mixed with this
common held-out denominator. The current held-out baseline was recomputed, not copied.

## Holdout and leakage audit

- `tools/thresholds.py --jsonl` is the only label source. The benchmark executes that
  command with a 20-second deadline and validates every row and identity
  (`tools/bench_llm_valuation.py:155-205`). It never reads the harvested `label` field.
- The sanctioned command currently yields 485 brackets over games 1–43. Filtering to
  the common fixed holdout gives 221 brackets in all 24 games from 20 through 43.
- The model is zero-shot: it is not fitted or updated on any tournament game. Each
  request contains only the current invoice rows' item index, quantity, unit and
  description. It contains no transaction result, threshold, policy, damage narrative,
  price-book prediction, other game, or future outcome
  (`tools/bench_llm_valuation.py:319-340`). Thus there is no fold that can contain its
  test game.
- The current harvested dataset SHA-256 is
  `56098b426062d3f56e89d19a59b5aa75b061418d9d3d7d672840d6c848f29b64`.
  This is a newer 43-game dataset, not the older 24-game hash quoted in prior work.
- The current price-book source contains game-specific tuning comments only for games
  2, 5 and 7; `rg -n "Game |game " c2f/estimate/pricebook.py` found no references to
  games 20–43. Its last commit is `a16126cc259e77d427c87d6ff2c998a92ea7cfa6`
  dated 2026-08-22T17:02:08+02:00.

Supporting count command:

```sh
PYTHONPATH=. .venv/bin/python tools/thresholds.py --jsonl |
  .venv/bin/python -c 'import json,sys,collections; rows=[json.loads(x) for x in sys.stdin if x.strip()]; gs=collections.Counter(r["game"] for r in rows); print({"rows":len(rows),"heldout_rows":sum(v for k,v in gs.items() if 20<=k<=43),"heldout_games":sum(20<=k<=43 for k in gs)})'
```

Observed aggregate: `rows=485`, `heldout_rows=221`, `heldout_games=24`.

## What the candidate actually is

This is one schema-constrained `gpt-4o` call per invoice, not one call per item and
not an item-by-sample ensemble. One response returns a positive gross-total p10, p50
and p90 for every invoice line. The benchmark converts that declared band into a
lognormal `Belief`: p50 becomes the median and p10–p90 determines sigma, bounded by
the repository's sigma floor and maximum (`tools/bench_llm_valuation.py:82-94`).

Therefore this tests the LLM as the whole price belief, not as a gap filler. Both its
point estimate and its spread affect `a`; at the current median reviewer quantile,
its median also sets `b`. Policy coverage and loss relatedness are intentionally not
asked in this pricing-only call.

The response schema fixes the array length, restricts identities to the invoice's
actual indices, requires positive finite ordered totals and rejects additional fields
(`tools/bench_llm_valuation.py:275-316`, `tools/bench_llm_valuation.py:343-390`). A
missing, duplicate, zero, non-finite or unordered output becomes an explicit
abstention, never a zero valuation.

## Actual provider use and latency

Both valid benchmark runs:

| Measurement | Run 1 | Run 2 / router export |
|---|---:|---:|
| Expected invoices | 24 | 24 |
| Calls attempted | 24 | 24 |
| Calls successful | 24 | 24 |
| Calls failed | 0 | 0 |
| Missing item outputs | 0 | 0 |
| Invalid item outputs | 0 | 0 |
| Input tokens | 12,169 | 12,169 |
| Output tokens | 6,053 | 6,114 |
| Total tokens | 18,222 | 18,283 |
| Calls missing usage metadata | 0 | 0 |
| Per-invoice latency p50, nearest rank | 1.864 s | 1.687 s |
| Per-invoice latency p95, nearest rank | 3.876 s | 4.302 s |
| Slowest invoice call | 4.863 s | 4.960 s |
| Sum of individual call latencies | 50.329 s | 49.164 s |
| End-to-end wall clock, concurrency 3 | 18.305 s | 17.327 s |

Usage numbers come from provider response metadata; none is estimated. Automatic
retries were disabled. Calls had a 45-second provider deadline plus a bounded outer
deadline, and concurrency was capped at three (`tools/bench_llm_valuation.py:400-506`).
The final holdout's largest invoice has 25 labelled items. This run does not measure
the separate 39-item case, so no 39-item latency is inferred from these observations.

Total research-call disclosure: the first research sweep made 24 calls but then hit a local
aggregate-rendering defect on a per-game zero denominator. Its in-memory results and
usage metadata were discarded before a report could be emitted. Two subsequent valid
runs made 48 calls, all successful, using 36,505 measured total tokens. Consequently,
across all three attempts 72 provider calls were attempted; success/failure and token
counts for the discarded first 24 remain unresolved. Every attempt used provider
request storage `false`.

## Failure and privacy semantics

- Model network access is rejected unless `--allow-model-network` is explicit
  (`tools/bench_llm_valuation.py:921-924`). A no-flag check exited nonzero with the
  expected refusal; it cannot masquerade as a passing no-op.
- `C2F_READONLY` is loaded by the `c2f` package before `main` and is required before
  any call (`tools/bench_llm_valuation.py:118-124`,
  `tools/bench_llm_valuation.py:925-927`). The real runs' nonzero calls and token
  metadata independently prove that it was not a `C2F_BACKEND=none` replay.
- Every direct provider request uses `store=False`; the process also forces
  `C2F_STORE_LOGS=0` before backend resolution
  (`tools/bench_llm_valuation.py:428`, `tools/bench_llm_valuation.py:931-935`).
- Prompts and raw responses exist only in process memory. Console and temporary output
  are aggregate-only by default; the explicit router export adds only identifiers and
  derived numeric fields described above. Provider errors expose only exception class
  and upstream status, never exception text that could contain a request fragment
  (`tools/bench_llm_valuation.py:439-475`).
- A provider failure returns no beliefs and marks every affected item missing. The
  effective candidate overlays valid model beliefs onto a complete price-book map, so
  every abstention falls back to the price book rather than zero
  (`tools/bench_llm_valuation.py:645-656`, `tools/bench_llm_valuation.py:727-731`).
- Synthetic checks cover valid output, duplicate identity, zero output, scoring,
  abstention and provider timeout. Command:
  `PYTHONPATH=. .venv/bin/python tools/bench_llm_valuation.py --self-test`.
  Numeric-export schema/fallback is also covered. Result: `self-test: 6 checks passed`.

The required whole-worktree privacy command was attempted before this report:

```sh
PYTHONPATH=. .venv/bin/python tools/audit_worktree_privacy.py
```

It returned `PrivacyAuditError` because an unrelated pre-existing untracked binary
`.env.swp` is included by the worktree enumerator and non-text changed files fail
closed (`tools/audit_worktree_privacy.py:75-76`). I did not delete or modify that
file. I then ran the same audit module's scanner over the Track B tool alone; it
scanned one file and found zero matching files, zero 12-word claim shingles and zero
exact item-description matches. The report is scanned again in final verification.

## Tournament-euro reconciliation and reviewer-side limit

Fresh required command:

```sh
PYTHONPATH=. .venv/bin/python tools/score.py --actual
```

It reports actual tournament net **EUR -430,982** and 1,158 unpriced reviewer rows
through game 43. This makes the prompt's EUR -163,687 cumulative figure stale. These
tournament euros are not used in the SCORE table above.

The candidate changes the complete belief, so it also changes `b`. The numeric router
export is not a score-compatible event log, and Track B did not persist one. Track D
later reconstructed the numeric `(a,b)` map in memory and called the sanctioned
`tools.score.score` API: baseline and candidate both report **918 unpriced rows on
games 20–43**. Equal counts do not price the changed limits, so candidate total-net
effect remains **unresolved**, not assumed zero. The 1,158 figure is the current
actual run over games 1–43 and is not a candidate estimate.

This unresolved reviewer exposure is the reason a strong issuer-side result is not
an ACTIVE recommendation. A shadow deployment must preserve the current price-book
submission while measuring model stability, deadline success and reviewer-side
maximin impact without becoming a second submitter.

## Bottom line

The invoice-level model beats the current price book on the requested per-item metric
in two complete provider runs. Each 24-call run produced all 221 beliefs with about
18.2k measured tokens and no fallback. However, SCORE moved from 0.428313 to 0.317164
with the same inputs and model: a 0.111149 swing large enough to reject the first run
as a stable point estimate. The 39-item deadline is not directly measured here, and
the reviewer-side effect of moving `b` is still unpriced.

**GO-AS-SHADOW-ONLY — rests on the worse observed complete-run SCORE 0.317164 versus
0.272898, denominator 221 held-out items / EUR 1,007,179.20 fixed BEST POSSIBLE.
The one measurement that
would change this to ACTIVE GO is a price-book-fallback shadow replay whose
`tools/score.py`-reconciled maximin total-net delta stays above zero after explicitly
pricing the candidate's invisible-amount reviewer rows.**
