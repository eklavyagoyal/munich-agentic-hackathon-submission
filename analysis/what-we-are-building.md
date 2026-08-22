# What We Are Building and Why

---

## The problem

We're playing a 100-round insurance pricing tournament against 16 other teams. Each round (~12.6 min) releases an encrypted case file containing a damaged-property claim: a policy, a damage description, an invoice template (items but no prices), and photos. Every team independently prices each line item and submits two numbers:

- **`a`** — what you charge opposing teams as the repair company ("issuer")
- **`b`** — the max you'll pay when receiving that line item as the insurer ("reviewer")

There is a secret fair-value threshold `t` per item. The payoff:

| | `a ≤ t` (fair charge) | `a > t` (fraud) |
|---|---|---|
| **`a ≤ b`** (accepted) | reviewer pays `a`, issuer gets `a` | reviewer pays `min(a,c)`, issuer gets `min(a,c)` |
| **`a > b`** (rejected) | reviewer pays `1.5a`, issuer gets `a` | both pay 0 |

**The key insight**: if your charge is fair (`a ≤ t`), you get `a` from every opponent _regardless_ of whether they accept or reject. Rejecting a fair charge only hurts the reviewer (1.5a penalty), not the issuer. So the only losing outcome as issuer is: overcharge AND get rejected.

Net score = total income as issuer − total costs as reviewer, over all rounds and all items.

---

## What went wrong in the first 17 games

**eyay is ranked 5th with +$33k. We should be ~2nd.**

The gap comes from two compounding failures:

### 1. LLM was silently broken for all 17 games

`c2f/estimate/llm.py` had two bugs that individually caused every call to throw, get caught by a broad `except`, and fall through to the static price book:

- Model ID `claude-opus-5` doesn't exist (HTTP 404 on every request)
- `output_config=` is not a valid Anthropic SDK parameter (TypeError)

Effect: **every single price estimate came from a keyword-match price book**, which systematically underestimates `t`. The LLM path — which sees the actual invoice text, damage description, policy scope, and photos — was never consulted.

Fix: changed model to `claude-sonnet-4-6`, rewrote `_anthropic()` to use the `tools` + `tool_choice` pattern for structured JSON output. See `c2f/estimate/llm.py`.

### 2. Acceptance limit `b` was set far too low

The acceptance formula was `b = Q(1/3)` of our belief ≈ 0.87 × median. With the pricebook already underestimating `t`, this put `b` deep below the actual fair-value threshold.

Result: **897 wrongful rejections out of 2009 reviewer decisions** (8.7:1 wrongful-reject to wrong-accept ratio vs the theoretical 2:1 optimum). At ~$280 average charge, that's ~$125k in avoidable 1.5x penalties over 17 games — 3.8× our entire current net profit sitting on the table.

The OPUSMOPUS game 10 case study (see `leaderboard-math-and-trick.md`) shows the exact mechanism: they charged $7,225 (fair), all 16 teams rejected it wrongfully and each owed $7,225 + $3,612 penalty. eyay charged correctly but then paid ~$50k in wrongful rejection penalties in the same game because `b` was too low.

Fix: raised `ACCEPT_QUANTILE` from 1/3 to 3/4 (`c2f/decision/quantile.py`). This puts `b` at ~1.1–1.4× median depending on σ, making wrongful rejections much rarer at the cost of occasionally accepting a capped fraudulent claim — a trade that's almost always worth it given the 1.5x asymmetry.

---

## The system we are building

### Overview

A fully autonomous agent that:
1. Monitors the API for new round releases every ~30 seconds
2. Decrypts the case archive with the round key
3. Parses the invoice, policy, damage description, and photos
4. Estimates the fair value `t` for each line item
5. Computes optimal `(a, b)` decisions using decision theory
6. Submits twice per round: a conservative price-book estimate at T+15s, then an LLM-refined estimate at T+52s

### The valuation pipeline

**Tier 1 (T+15s) — price book only**  
A keyword-based matcher (`c2f/estimate/pricebook.py`) looks up rates by trade category and unit type (per m², per hour, per unit). Deterministic, fast, covers ~80% of items. This submission retires all deadline risk.

**Tier 2 (T+52s) — LLM ensemble**  
Three parallel calls to Claude Sonnet 4.6 each see: the case system prompt (policy + damage description), the invoice text, and up to 3 damage photos. Results are aggregated into a lognormal `Belief(median, sigma)`. This replaces the Tier 1 submission if it produces numbers.

The ensemble prefetches ALL items concurrently before the rule engine runs — so individual rules stay pure (dict lookups only, no I/O).

### The rule engine

A 4-stage pipeline in `c2f/rules/engine.py`:

| Stage | Logic | Key rules |
|---|---|---|
| `COVERAGE` | pick highest-priority; returns `covered: bool` | `coverage_exclusions.py` (explicit policy exclusions), `llm_prior.py` (LLM relatedness check) |
| `PRIOR` | pick highest-priority; returns `Belief` | `pricebook_prior.py` (priority 10), `llm_prior.py` (priority 0) |
| `ADJUST` | apply ALL multiplicatively; returns scale `k` | `calibration_bias.py` (learned correction from past rounds) |
| `GUARD` | apply ALL as intersection; returns clamp `(lo, hi)` | `pricebook_prior.py:SanityClamp` (0.15x–4x book range) |

Rules run in a 50ms sandboxed timeout — a crashing rule cannot miss a submission deadline.

### The decision math

Given a lognormal belief `Belief(median=m, sigma=σ)`:

**Charge `a`**: maximise `a · P(a ≤ t)`. Solving the first-order condition gives the inverse Mills ratio equation `φ(z)/Φ(-z) = σ`. Result: `a ≈ 0.75m` for σ in [0.15, 0.50], capped at the σ=0.5 value to prevent tail-betting on uncertain beliefs.

**Accept limit `b`**: accept iff `P(a ≤ t) > 1/4` (current setting). Given the wrongful-reject asymmetry (costs 1.5a vs 1.0a for wrong accept), we lean toward accepting. `b = Q(3/4)` of belief ≈ 1.1–1.4m depending on σ.

**Coverage**: if the item is not covered by policy or not related to the reported damage, set `a = b = 0`. This is the single highest-leverage decision — an error here is 100% loss, vs ~20% for mispricing.

Both `a < b` always (we'd accept our own charges) — enforced in `c2f/core/invariants.py`.

### The calibration loop

After each game, `c2f/calibrate.py` reads the transaction log and extracts interval-censored bounds on `t`:
- If we rejected a fair charge (paid 1.5× penalty) → `t ≥ that charge amount`  
- If an opponent's fraud charge was rightfully rejected → `t < charge amount`

It fits a global multiplicative correction `k` and per-trade corrections from these bounds. `CalibrationBias` in `rules_user/calibration_bias.py` applies the correction as an ADJUST rule, multiplicatively shifting the median before the decision step.

**Status**: the calibration architecture is correct but the transaction wire-format adapter (`bounds_from_transactions`) uses old field names and needs updating to match the live API format `{issuer, reviewer, line_item_index, accepted, amount}`.

---

## Current state of each piece

| Component | Status | Notes |
|---|---|---|
| Round loop, decrypt, parse | Working | Tested end-to-end |
| Price book valuation (Tier 1) | Working | Runs in all 17 games |
| LLM ensemble (Tier 2) | **Fixed, untested live** | Needs `ANTHROPIC_API_KEY` set |
| Rule engine + sandbox | Working | 131/131 tests pass |
| Decision math (`quantile.py`) | Fixed | `ACCEPT_QUANTILE` raised to 3/4 |
| Calibration loop | Partially broken | Wire-format mismatch in adapter |
| Tournament daemon (`serve.py`) | Working | Needs `TEAM_API_KEY` env var |
| Dashboard UI | Working | Reads `data/events/tournament.jsonl` |

---

## The gap to close

| Issue | Estimated impact |
|---|---|
| Wrongful rejection penalties (897 events, b too low) | ~$125k avoidable over 17 games |
| Charge undershoot (pricebook vs LLM, item 3 game 10: $3,482 vs $7,225) | ~$62k per similar high-value round |
| Calibration loop broken (no per-trade k correction) | Unknown; likely 10–20% systematic underestimate |

With the LLM fix and the raised `b`, the most acute bleeding stops immediately. The calibration loop is the next lever once we have a few rounds of LLM-sourced medians to fit against.

83 games remain. The overnight window (21:00–08:00 UTC) covers 52 of them — the always-on daemon is critical for not missing those.
