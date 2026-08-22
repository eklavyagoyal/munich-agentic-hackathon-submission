# RL policy training is not the bottleneck — belief quality is

**Author:** Annie  
**Date:** 2026-08-22  
**Confidence:** High on the decision-function argument (it is math). Medium on the belief-quality priorities (needs backtest to confirm).

---

## What I found

The current `(a, b)` decision function is **already the closed-form optimal policy** for the assumed loss structure. Replacing it with a learned RL policy cannot beat it — it would converge to the same answer at far greater cost. The real bottleneck is the quality of the belief `(median, sigma)` going in, not the function that maps belief to `(a, b)`.

---

## The evidence

### The decision function is analytically optimal

`c2f/decision/quantile.py` solves:

```
maximise  E[revenue]  =  a × P(a ≤ t)
subject to  t ~ LogNormal(log(median), sigma)
```

This gives the Mills-ratio equation `φ(z) / (1 − Φ(z)) = sigma`, from which `a = median × exp(z × sigma)`. No RL agent trained on the same loss function and the same belief distribution can improve on this — it is the global maximum. The cap at `z_cap = optimal_charge_z(0.5) ≈ −0.518` prevents tail-betting at high sigma and was a deliberate, correct design decision.

`b = belief.quantile(1/3)` follows from the `2/3` acceptance rule (`c2f/decision/quantile.py:71`), itself derived from the payoff matrix in §1 of the brief. Also correct.

### The proposed reward function is circular

A reward function written as `R(a, b, t)` assumes `t` is known at training time. It never is. The only signals we observe are rejection outcomes — exactly the interval-censored bounds that `c2f/calibrate.py` already consumes. RL on this signal would rediscover the same `k` correction the calibration loop already fits, with more machinery and less data efficiency.

### The tiered estimator has a known gap

- **Tier 1 (pricebook):** reads only `LineItem.description` keywords. Blind to the policy text, damage description, item quantities relative to damage scope, and photos. Case 2 matched **zero** of 34 price book entries — all 7 items fell to the generic band (`c2f/estimate/pricebook.py`).
- **Tier 2 (LLM ensemble):** reads `policy_text` (40k chars), `damage_description` (20k chars), the full invoice (for duplicate/scope checks), and up to 3 images. It runs a `_digest()` call first to extract covered perils, exclusions, and physical scope — the only layer that can catch quantity inflation or unrelated items (`c2f/estimate/ensemble.py:152`).

**But:** `llm_prior` is currently loaded at `priority = 0`, below `pricebook_prior` at `priority = 10` (`rules_user/llm_prior.py:16`). So when the pricebook matches a keyword, it wins — even though the LLM has strictly more context. This is a known open question in the file's own comment; it was deliberately left as a one-line change pending round data.

**And:** There is no LLM key in the current environment, so `llm_prior` abstains entirely on every round. Tier 1 alone is what has been exercised so far.

---

## What it implies we should do

In priority order, cheapest first:

1. **Fix pricebook keyword coverage** (English + more trades). Case 2 had zero matches; the invoices are in English and the pricebook is predominantly German keywords. This is the single biggest known valuation error and needs no training data. Quantify the improvement on completed games before doing anything more complex.

2. **Flip `llm_prior` priority above `pricebook_prior`** (change `priority = 0` to `priority = 11` in `rules_user/llm_prior.py`). The LLM sees policy, damage scope, and photos; the pricebook sees only a keyword. The pricebook should only win when the LLM abstains. Do not make this change until an LLM key exists — currently it would have no effect (LLM abstains), but the priority should be right for when the key lands.

3. **Richer calibration** — the current `k` is one scalar per trade (`c2f/calibrate.py:166`). Per `(trade, unit, qty_bin)` would catch e.g. "flooring, m2, large quantity" being systematically mispriced. This needs ~4 bounds per bucket to be reliable (`MIN_BOUNDS_PER_TRADE = 4`).

4. **Opponent model via accept-rate tracking** — `OpponentModel` exists in `c2f/core/models.py` but is empty. If the field consistently accepts up to their median, `b` can safely sit higher. This is a contextual bandit, not full RL, and it reads directly from `calibrate.field_stats()`.

Do **not** build a full RL training pipeline targeting `(a, b)` directly. The math already solved that problem.

---

## How confident I am

- **The decision function being optimal**: certain, it is mathematics. Any RL approach training on the same objective converges to this solution.
- **The pricebook language gap**: measured — game 2, 0 of 7 items matched (`docs/MODEL_BRIEF.md §3`).
- **The priority flip recommendation**: correct in principle; the comment in `rules_user/llm_prior.py` agrees. Needs backtest against completed games to confirm the magnitude of the improvement.
- **The calibration enrichment**: speculative. Two games is not enough data to fit per-bucket corrections reliably.

Two games of evidence so far. The pricebook gap finding is a fact; the rest are hypotheses to test.
