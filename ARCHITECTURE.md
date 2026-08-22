# Claim to Fame — Independent Analysis & System Architecture

Second opinion on [GAMEPLAN.md](GAMEPLAN.md), derived independently from
[GAME_DESCRIPTION.md](GAME_DESCRIPTION.md). Sections 1–2 are the strategy re-derivation,
3–8 answer the operational question: **where does what run, on what hardware, and how do we
keep improving it mid-tournament.**

---

## 1. What I re-derived independently — and it holds

I worked the payoff matrix from scratch before reading GAMEPLAN. Same conclusions, so these
two rules are now independently confirmed and safe to build on.

**Insurer rule.** For an incoming charge `a`:

```
cost(accept) = min(a, c) = a          (for any sane a)
cost(reject) = 1.5a · P(a ≤ t)
accept  ⟺  a < 1.5a · P(a ≤ t)  ⟺  P(a ≤ t) > 2/3
```

⇒ **`b` = the 1/3-quantile of our belief about `t`.** Wrongly accepting fraud costs the full
`a`; wrongly rejecting a fair claim costs only the extra `0.5a`. Fraud is exactly 2× worse,
hence the 2/3 threshold. Not a tuning knob — it falls out of the numbers.

**Issuer rule.** In the fair zone the issuer is paid `a` whether or not the opponent accepts
(rejection costs the *insurer* `1.5a`, the issuer still collects `a`). And there is **no penalty
for overcharging** — a rejected fraudulent charge is simply zero. So:

```
E[revenue] = a · P(a ≤ t)  +  min(a,c) · P(a > t ∧ a ≤ b_opponent)
```

Ignoring the second term, maximising `a·(1−F(a))` for a lognormal belief with spread `σ` gives
`h(z*) = σ` where `h = φ/(1−Φ)`. For `σ = 0.25` → `z* ≈ −1.10` → **`a ≈ 0.76 · m`**.
GAMEPLAN's `0.75 · m` is correct.

**Invariant worth asserting in code:** `a < b` for every item. We must always be willing to
accept our own charge. If that ever fails, the pipeline is broken.

---

## 2. Three places I disagree with GAMEPLAN

### 2.1 "There is no game theory against opponents" (§0) is overstated

It contradicts GAMEPLAN's own §2.2. Opponents enter through two real channels:

1. **The issuer's upside term.** `min(a,c) · P(a > t ∧ a ≤ b_opp)` is *entirely* a function of
   opponents' `b`. If the field sets `b` generously, charging above `t` is profitable — free,
   since overcharging carries no penalty. How far above `t` we should charge is an **empirical
   question about opponent behaviour**, not a fact about `t`.
2. **Selection effect on `b`.** Incoming charges are not drawn from our prior over `t`; they are
   drawn from opponents' strategies. If everyone charges `0.75m`, almost every incoming charge
   is fair, and the posterior `P(a ≤ t | a observed)` is far above the prior — pushing `b` up.

Both are second-order in round 1 and both are **measurable from round 2 onward**. Treating the
opponent field as a fixed constant is fine as an opening default and wrong as a standing policy.

### 2.2 The fallback ladder's last rung is exploitable

GAMEPLAN §4 ends with *"last resort: generous `b`, `a = 0` … accepting is bounded-bad."*
Accepting is bounded by `c ≥ 4t` — i.e. up to **4× the fair value, per item, per opponent.**
Wrongly rejecting is bounded by `1.5t`. So a maximally generous `b` is the *more* expensive
error, and it is precisely the hole that GAMEPLAN's own §2.5 "cap exploit" is designed to punch.
If any team runs that exploit, a generous-`b` fallback hands them our entire balance.

**Fix:** the bottom rung is `b = price-book median for the trade`, never "generous", never `0`.
An uninformed-but-anchored limit is bounded on both sides.

### 2.3 It never says *where* anything runs — and overwrite makes that dangerous

See §3. GAME_DESCRIPTION says *"later submissions overwrite earlier ones"*, which GAMEPLAN
correctly exploits for staged submission but does not follow through on: **overwrite semantics
make a redundant second submitter a liability, not a safety net.** If the backup posts its crude
fallback at T+55s, it silently destroys the primary's good answer from T+50s. Redundancy here
needs a single-writer rule, not just a second machine.

---

## 3. Where things run

| Component | Host | Why |
| --- | --- | --- |
| **Primary runner** | Small always-on EU cloud VM (2 vCPU / 4 GB, ~€4/mo) | No sleep, no conference wifi, NTP-disciplined clock, systemd timer. The API is on `quantco.cloud` — stay in the same region to cut RTT. |
| **Standby runner** | One designated laptop, wired if possible | Takes over *only* on primary failure, under the single-writer rule below. |
| **Case archives** | Pre-synced to both, before the round | Only the *key* is time-gated. Downloading zips in the hot path is self-inflicted latency. |
| **Dashboards / analysis** | Anywhere | Off the hot path entirely. |

The hackathon-wifi failure mode is the single most likely cause of a default submission, and a
default submission is the worst possible outcome in this game. A €4 VM is cheap insurance.

**Single-writer rule (must be explicit):**

- The primary owns the final submission. It writes a heartbeat after each stage.
- The standby submits **only** the baseline, **only** if no submission exists by T+40s.
- Ideal coordination primitive: a `GET` of our own current submission, if the API offers one —
  then "does a submission already exist?" is answerable without any shared state of our own.
  **Check API_HANDBOOK for this first** (§8).
- Every submission carries a monotonically increasing quality tier. A lower tier must never
  overwrite a higher tier for the same case.

**Clock discipline.** The window is 60 seconds and GAMEPLAN starts polling at T−3s. A laptop a
few seconds off makes that plan actively harmful. Sync via NTP, and derive round timing from the
server's `Date` response header rather than the local clock.

---

## 4. The 60-second path

```
T−30s  archives on disk, process warm, connection pool open, prompt cache primed
T−2s   begin polling for the key (bounded retries, jittered)
T+0s   key acquired → 7z decrypt → parse policy.txt / description.txt / invoices.pdf
T+3s   Stage A: coverage pass    — 1 call, whole invoice, shared context
       Stage B: pricing pass     — K parallel calls, one per line item
T+15s  SUBMIT #1 (tier 1, baseline). Deadline risk is now retired.
T+18s  Stage C: ensemble refinement — 3 samples/item, vision on images.png if present
T+45s  diff vs #1 printed; human eyeballs only the 3 largest items
T+52s  SUBMIT #2 (tier 2, final). Hard timer fires at T+52s regardless of what is still running.
```

Two refinements over GAMEPLAN's version:

**Split coverage from pricing.** `t` becomes zero via a *policy* question ("is this covered and
related?") and non-zero via a *market* question ("what is the fair gross total?"). These are
different problems with different failure modes. One holistic call answers coverage with the
whole invoice in view; K parallel calls answer pricing. Merging them into one per-item prompt
makes coverage errors invisible and correlated.

**Prompt-cache the shared context.** `policy.txt` + `description.txt` is identical across all K
per-item calls. Cache that prefix once per case: it is the difference between paying for the
policy text K times and paying for it once, and it cuts time-to-first-token on every item.

---

## 5. How much compute we actually need

**Local compute is a non-issue.** 7z decrypt, `pdftotext`, and JSON assembly are milliseconds.
No GPU. No local model. 2 vCPU / 4 GB is generous.

**The real constraint is LLM concurrency and rate limits.** Per round, with `K` line items:

| | calls | notes |
| --- | --- | --- |
| Stage A coverage | 1 | whole invoice |
| Stage B pricing | K | parallel |
| Stage C ensemble | 3K | parallel |
| **Total, K = 30** | **~121** | inside ~45 s ⇒ ~3 calls/s sustained, ~30-way concurrency |

Token budget ≈ 300–500k input / ~50k output per round, most of the input served from cache
after the first item.

**Action item before the tournament:** confirm the account's requests-per-minute and
tokens-per-minute limits and raise them if needed. A 429 storm at T+20s is the one resource
failure that can actually cost us a round, and it will not show up when rehearsing on case 0
with a single invoice. Rehearse at full fan-out.

---

## 6. The return path

`POST` submission, with:

- **Bounded retries** with jitter; a hard local deadline that fires regardless of in-flight work.
- **Idempotency per (case, tier)** so a retry can never downgrade a submission.
- **Verify the write.** Re-read our submission after posting if the API allows it. "The POST
  returned 200" and "our numbers are what the server will score" are not the same claim.
- **Explicit gross-total assertion.** `a` and `b` must be gross totals for the whole line item —
  not net, not per-unit. VAT is a flat 19% systematic error if we get this wrong, which is larger
  than the entire margin between our `a` and our `b`. Assert `unit_price × qty × (1+vat) ≈ a`
  at the boundary and fail loudly.

---

## 7. Staying modular and improvable

Fix the round loop; make everything inside it swappable.

```python
class Estimator(Protocol):
    def estimate(self, case: Case, item: LineItem) -> Belief: ...   # samples, or (median, sigma)

class DecisionPolicy(Protocol):
    def decide(self, belief: Belief, opponents: OpponentModel) -> Submission:  # -> (a, b)
```

- `Belief` is a **distribution, never a point estimate.** §1's rules consume quantiles; an
  estimator that returns a single number cannot feed them. The 3-sample ensemble is not just
  variance reduction — the spread *is* the `σ` the decision rules need.
- **Everything to JSONL**: case id, parsed items, per-item belief, chosen `a`/`b`, which fallback
  rung fired and why, per-stage latency, submit status. This log is the dataset.
- **Replay harness.** `replay.py --estimator v4 --cases all` re-scores any estimator version
  offline against every past case. Improvement becomes measurable instead of argued.
- **Shadow mode.** Run the candidate estimator live, in parallel, log its output, submit the
  incumbent's. Zero-risk iteration during a live tournament — this is how we change the model
  mid-run without betting a round on it.

---

## 8. What we actually learn each round

We never observe `t`. We observe **interval-censored bounds** on it, and it is worth being
precise about which action yields which:

| Our role | What happened | What it proves |
| --- | --- | --- |
| Insurer | we rejected `a`, then got charged the `1.5a` penalty | `t ≥ a` |
| Insurer | we rejected `a`, no penalty | `t < a` |
| Issuer | our `a` earned nothing from anyone | `t < a` |
| Issuer | an opponent ate a penalty on our `a` | `t ≥ a` |
| Either | we accepted | **nothing** — acceptance is uninformative |

Two consequences GAMEPLAN misses:

1. **Rejections are our only labelled experiments.** A lower `b` buys information; a high `b`
   buys silence. There is a genuine explore/exploit tradeoff here, priced at `0.5a` per wrong
   rejection. Worth knowing about; probably not worth deliberately paying for beyond round 2.
2. **Fit the bias with interval-censored regression**, not by averaging point errors — the
   labels are bounds, not values. One global multiplicative correction `k` first, then per-trade
   corrections once there is enough data. Applying `k` is a one-line change if §7's interfaces
   hold.

---

## 9. Open questions — blocked on `API_HANDBOOK.md`

Not yet in the shared folder. These change the design, so look them up first:

1. **Can we `GET` our own current submission?** If yes, it is the single-writer coordination
   primitive (§3) and the write-verification mechanism (§6), for free.
2. **Exact key-release semantics** — does the key endpoint 404 or block before release, and does
   polling it early count as probing? Fair-play rules forbid obtaining keys before release; the
   polling window must be safely inside the rules. Ask the organisers if there is any doubt.
3. **Rate limits on the submission endpoint** — does staged submission risk throttling?
4. **Item identity** — how are line items keyed in the payload? Our parse must reproduce the
   server's item ordering exactly, or every price lands on the wrong item.
5. **Does the folder gain new cases mid-tournament?** If so the pre-sync in §3 needs a watcher,
   not a one-off copy.

Item 4 is the quiet one. A parser that silently shifts item indices produces a submission that
looks entirely healthy and is scored as garbage.
