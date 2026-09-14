# Claim to Fame — Gameplan

> Written in English on purpose: the code, the prompts and the final strategy write-up for
> QuantCo all end up in English, so this doc doubles as the seed for that write-up.

---

## 0. TL;DR — the one thing that matters

Read the payoff table carefully and the game collapses:

**As issuer (`a`):** if `a ≤ t`, you receive `a` from **every single opponent**, no matter what
their acceptance limit `b` is.

| opponent's decision | fair charge (`a ≤ t`) |
| ------------------- | --------------------- |
| accepts             | H gets `a`            |
| rejects             | H gets `a` (+ they eat a `0.5a` penalty) |

**As insurance (`b`):** accepting is right iff `a ≤ t`, rejecting is right iff `a > t`.
That is true pointwise, independent of what anyone else does.

### ⇒ There is no game theory against opponents. There is only one problem: **estimate `t`.**

No bluffing, no signalling, no counter-play. Nobody can punish you and you cannot manipulate
anybody, because everything is submitted blind and simultaneously. Two consequences:

1. **All engineering effort goes into estimating `t` accurately and submitting reliably.**
2. **Never submit the defaults (`a = 0`, `b = 0`).** `a = 0` earns nothing; `b = 0` rejects every
   fair claim and pays `1.5a` in penalties to everyone. That combination is the single worst
   possible submission — see §3.

---

## 1. Mechanics decoded

Per line item there are two secret numbers:

| symbol | meaning |
| ------ | ------- |
| `t` | fair-value threshold — max price a claims expert would accept. **`t = 0` if the item is not covered by the policy** (and, by the same logic, if it is unrelated to the damage). |
| `c` | payment cap, `c ≥ 4t`, never below an absolute floor. If accepted, the issuer receives `min(a, c)`. |

We submit two numbers per line item, both as **gross total for the whole line** (see the VAT trap in §8):

| symbol | meaning |
| ------ | ------- |
| `a` | what we charge every opponent |
| `b` | the most we are willing to pay when we receive that same line item |

Every team is matched against every other team in both roles. With `N` teams, each of our line
items is issued `N−1` times and reviewed `N−1` times.

### Our payoff, decomposed

```
net = income(a)  −  cost(b)
```

**income only depends on `a` and `t`:**

```
income(a) = a · (N−1)                          if a ≤ t     ← guaranteed, opponent-independent
income(a) = min(a,c) · #{opponents with b ≥ a}  if a > t     ← lottery, depends on the field
```

**cost only depends on `b`, `t` and the incoming charges `a_j`:**

```
per incoming charge a_j:
  a_j ≤ b  (accept)  →  we pay a_j          if a_j ≤ t
                        we pay min(a_j,c)   if a_j >  t
  a_j >  b  (reject)  →  we pay 1.5 · a_j    if a_j ≤ t   ← wrongful reject
                        we pay 0            if a_j >  t
```

Two clean, independent optimisation problems. Solve both below.

---

## 2. The math

### 2.1 Optimal charge `a`

Model our belief about `t` as lognormal with median `m` (our point estimate) and log-scale `σ`
(our uncertainty). Write `a = m · e^{zσ}`.

Ignore the fraud-lottery term for a moment (conservative — it only ever adds income), so

```
E[income] ∝ a · P(t ≥ a) = m·e^{zσ} · Φ(−z)
```

Differentiate and set to zero:

```
σ·Φ(−z) − φ(z) = 0    ⟺    φ(z) / Φ(−z) = σ
```

(inverse Mills ratio = σ). Solving numerically:

| our uncertainty σ | optimal z | **optimal `a` / m** | P(`a ≤ t`) |
| ----------------- | --------- | ------------------- | ---------- |
| 0.15 (±15 %)      | −1.45     | **0.80**            | 93 %       |
| 0.25              | −1.10     | **0.76**            | 86 %       |
| 0.35              | −0.84     | **0.75**            | 80 %       |
| 0.50 (±50 %)      | −0.51     | **0.78**            | 70 %       |

The result is remarkably flat in σ, which is exactly what you want under time pressure:

> ### 🎯 Rule A: charge `a = 0.75 × your median estimate of t`.
> Shade harder (0.65) only where the coverage/relatedness call itself is shaky.

Note what the flat curve means: **you do not need a good uncertainty estimate to get `a` right.**
You need a good *median*. Effort belongs in the median, not in the error bars.

### 2.2 Optimal acceptance limit `b`

Given an incoming charge `a`, let `q = P(a ≤ t)` be our belief that it is fair.

```
E[cost | accept] = q·a + (1−q)·min(a,c)  = a          (when a ≤ c)
E[cost | reject] = q·1.5a + (1−q)·0      = 1.5·a·q
```

Accept iff `a < 1.5·a·q`, i.e.

> ### 🎯 Rule B: accept iff you are **more than 66.7 % sure the charge is fair**.

A wrongful reject costs `0.5a`; a wrongful accept costs `a`. Errors are **2:1 asymmetric against
accepting**, hence the two-thirds bar rather than a coin flip.

Since `b` is a threshold and `P(t ≥ a)` decreases in `a`, the cutoff sits at the value where
`P(t ≥ b) = 2/3` — the **1/3-quantile** of our belief about `t`:

```
b* = m · e^{−0.431·σ}
```

| σ | **`b` / m** |
| --- | --- |
| 0.25 | 0.90 |
| 0.35 | 0.86 |
| 0.50 | 0.81 |

> ### 🎯 Rule B′: set `b = 0.87 × your median estimate of t` as the opening default.

**Then raise it after round 1.** The derivation above deliberately assumes the incoming charge is
an arbitrary draw. In reality opponents also shade downward (they are solving §2.1 too), so an
observed charge is *far* more likely to be fair than the prior suggests. Bayes then pushes `b`
up. Concretely: once round-1 data shows the field charging below `t`, move `b` toward
`1.0–1.1 × m`. Rejections are only worth it against genuine outliers.

**When `a > c` (absurd charges).** Then accepting costs only `c`, while wrongly rejecting a fair
claim costs `1.5a`. The bar drops to `q > c/(c + 0.5a)`. Irrelevant in practice — `a > c ≥ 4t`
means it is fraud with near-certainty — but it is why you should **never set `b = 0`**: the cap
bounds the downside of accepting, nothing bounds the downside of rejecting.

### 2.3 Both rules together

```
a = 0.75 · m        b = 0.87 · m  (opening)  →  1.0 · m  (once calibrated)
```

So `b > a`: we would accept our own invoices. That is correct and expected — the two numbers
answer different questions.

### 2.4 Uncovered / unrelated items

`t = 0` ⇒ any `a > 0` is fraud, and `c` collapses to the absolute floor, so overcharging pays
almost nothing even when accepted. And `b > 0` means accepting pure fraud.

> ### 🎯 Rule C: item not covered, or not related to the described damage ⇒ `a = 0` **and** `b = 0`.

**This is the single highest-leverage decision in the whole game.** A coverage call flips `t`
between `0` and its full value — a 100 % error. A mispriced item is a 20 % error. Spend
proportionally: get coverage right first, price second.

### 2.5 The cap exploit — hold in reserve

If a large share of the field sets `b` very high ("accept everything to dodge penalties"), then
charging `a ≈ c ≥ 4t` yields `4t · p` instead of `t · 1`. It beats honest play when more than
~25 % of opponents accept it.

**Do not open with this.** Round 1–2, play honest and *measure* `p` from the leaderboard's
Matchup / Transactions tabs. Only defect on evidence, and only on cheap items. It sacrifices the
guaranteed opponent-independent income for a lottery, and it reads badly in the style write-up.

---

## 3. Evidence from the example leaderboard (slide 6)

| Rank | Team | Income | Costs | Net |
| --- | --- | --- | --- | --- |
| 1 | Ingenious Inigo | 7087.50 | 802.24 | **+6285.26** |
| 2 | Hammer Hannes | 3737.10 | 2058.75 | **+1678.35** |
| 3 | Babo Bernhard | 0.00 | 2749.92 | −2749.92 |
| 4–6 | Turbo/Fire/Magic | 0.00 | 3247.38 | −3247.38 |

Three teams share an **identical** cost of 3247.38 with zero income. That is the fingerprint of
submitting the defaults: `a = 0` (no income) and `b = 0` (reject everything ⇒ pay `1.5a` to every
opponent on every fair claim). The spread between "submitted defaults" and "played well" is
**≈ 9500** — far larger than any plausible gap between a good and a mediocre price estimate.

> **Reliability outranks accuracy.** A crude submission that always lands beats a brilliant one
> that misses the 60-second window.

Second reading: both `7087.50` and `3737.10` divide exactly by 5 (= N−1), so both teams had all
charges `≤ t` and were paid by all five opponents. Inigo simply charged **1.9× more** than
Hannes and still stayed under `t`. Hannes left half the money on the table.

> **Over-shading is the silent killer.** It produces no penalty, no error, no warning — just
> missing income. This is the mistake careful teams make. `0.75 · m`, not `0.4 · m`.

---

## 4. Architecture

```
                        ┌── pre-tournament, offline ──────────────┐
                        │  • all encrypted zips downloaded        │
                        │  • price book built                     │
                        │  • prompts + pipeline rehearsed on      │
                        │    case 0 with a stopwatch              │
                        └─────────────────────────────────────────┘

 t+0s   case released ──► poll /key (started at t−3s, 250 ms interval, bounded retries)
 t+1s   7z decrypt (zip already on disk — nothing to download)
 t+2s   parse: policy.txt, description.txt, invoices.pdf → line items, images.png
 t+3s   ├─► FAST PASS   (Sonnet 5, one async call per line item, all in parallel)
 t+18s  │   └─► SUBMIT #1  ◄── safety net locked in. Deadline can no longer hurt us.
 t+19s  ├─► DEEP PASS   (Opus 5 + vision on images, 3-sample ensemble per item)
 t+45s  │   └─► diff vs submission #1, surfaced in the console
 t+45s  ├─► HUMAN WINDOW — one person eyeballs the 3 largest line items only
 t+56s  └─► SUBMIT #2 (final). Hard timer force-submits best-available at t+55s regardless.
 t+60s  window closes
```

Design decisions and why:

- **Submit twice.** "Later submissions overwrite earlier ones" is free option value. Submission #1
  removes all deadline risk; everything after it is pure upside. Do not treat the round as one
  atomic 60-second computation.
- **Pre-download every encrypted zip.** Only the *key* is time-gated, not the archive. This
  removes network I/O from the hot path entirely.
- **Text-layer PDF extraction first** (`pdftotext` / `pdfplumber`), vision only as fallback. The
  invoices are machine-generated and 100× faster to parse as text. Vision on a text-layer PDF is
  a self-inflicted latency wound.
- **Fan out per line item.** N parallel calls ⇒ latency of one call, not N. Pass shared context
  (policy + damage description) into each.
- **3-sample ensemble** on the deep pass: median for the estimate, spread for σ (which feeds
  §2.1/2.2). Cheap variance reduction and it gives the uncertainty for free.
- **Bounded timeouts, bounded retries, exponential backoff + jitter** on every remote call. Never
  block the pipeline on a hanging LLM call — a per-item deadline drops that item to the fallback
  estimate.
- **No hidden failures.** Every fallback taken is logged at WARN with the reason. A silently
  zeroed line item is money set on fire.
- **Structured JSON log per round** — case id, per-item estimate/σ/coverage verdict, latency
  breakdown per stage, submit status. This log *is* the calibration dataset in §6.

### Emergency fallback ladder

Never submit nothing. In descending order of quality:

1. Deep-pass estimate.
2. Fast-pass estimate.
3. Price-book lookup by item description keyword × parsed quantity.
4. Rough heuristic (`unit × qty × book rate for the trade`).
5. **Last resort: generous `b`, `a = 0`.** If we genuinely know nothing, accepting is
   bounded-bad (`min(a,c)`) while rejecting is the 3247.38 disaster from §3. Absolutely never
   fall back to `b = 0`.

---

## 5. Step-by-step plan

### Phase 0 — Registration (blocking, do first)

1. Walk up to the organisers with team name + Discord handle, get the `TEAM_API_KEY`.
2. Key goes into `.env` (already gitignored). Never committed, never pasted in Discord.
3. Get the shared folder link. **Read `API_HANDBOOK.md` immediately** — it is not in this repo and
   it defines the actual submission schema.
4. Note the round schedule and the leaderboard: <https://c2f.public.quantco.cloud/leaderboard/>

### Phase 1 — Prove the round trip (gate: nothing else matters until this works)

5. `pixi install && pixi run python starter_script.py` on case 0. Confirm a submission is
   accepted end-to-end.
6. Verify `7z` decryption works on every machine that might run the pipeline.
7. Write down the exact request/response schema, the auth header, and any rate limits.
8. Submit deliberate junk on case 0, then submit again — confirm overwrite semantics.
9. **Pre-download all encrypted zips** from the folder.

### Phase 2 — The pipeline (the reliability half)

10. API client: fetch key, decrypt, extract. Bounded timeouts + retries.
11. PDF → structured line items: `{idx, description, qty, unit, unit_price?, vat_rate}`.
    Validate on case 0 by hand, line by line.
12. Round orchestrator with the latency budget from §4 and a hard force-submit timer.
13. Structured logging + a one-screen console view (per item: estimate, σ, coverage, `a`, `b`).
14. **Rehearse a full round on case 0 with a stopwatch.** Target: submission #1 by t+20s.

### Phase 3 — Valuation (the accuracy half)

15. **Coverage/relatedness agent** (Rule C): policy.txt + description.txt + item → `covered`,
    `related`, confidence. Enumerate the policy's exclusions explicitly, then test each item
    against that list.
16. **Pricing agent**: item + qty + unit + damage context → net unit price as **p10 / p50 / p90**
    in EUR, plus the applicable VAT rate. Percentiles, not a point estimate — §2 needs `m` and σ.
17. **Price book** as grounding in the prompt (§7) — German trade rates, not the model's vibes.
18. Combine: `m = median(ensemble p50) × qty × (1 + vat)`, `σ` from the p10/p90 spread, then
    `a = 0.75m`, `b = 0.87m`; `a = b = 0` if not covered or not related.
19. Sanity gates that block a submission: `a ≤ b` is *not* required, but every item needs
    `0 ≤ a`, `0 ≤ b`, gross totals, and a plausible order of magnitude vs. the price book.

### Phase 4 — Run the rounds

20. One designated runner, one hot standby. Only ever **one** process submitting (last write wins
     — two racing processes is a self-inflicted footgun). Failover is manual and announced.
21. Every round: run, log, and eyeball the deep-pass diff during the human window.
22. Watch the leaderboard after each round.

### Phase 5 — Calibrate (§6) and write up (§9)

---

## 6. The calibration loop — where the real edge is

Rejections leak ground truth about `t`. Every round gives you labelled data for free:

**As issuer:** we charged `a` and got rejected.
- income still arrived ⇒ `a ≤ t` (wrongful reject) → **lower bound on `t`**
- income was 0 ⇒ `a > t` → **upper bound on `t`**

**As insurance:** we rejected an incoming `a`.
- we were billed `1.5a` ⇒ `a ≤ t` → **lower bound**
- we paid 0 ⇒ `a > t` → **upper bound**

Accepted transactions tell you nothing about `t` — only rejections do. So each round yields a set
of one-sided bounds on `t` for specific items.

Use them for two things:

1. **Global bias correction.** Are our medians systematically high or low? Fit one multiplicative
   correction factor `k` and apply `a = 0.75·k·m`. If we are never once rejected across a full
   round, we are almost certainly under-charging (see Hammer Hannes) — push `k` up.
2. **Field model.** Which opponents accept what? Estimates the acceptance rate `p` that gates the
   §2.5 decision, and tells us whether to raise `b`.

Keep a running table: `case → item → our m, our a, our b, outcome, implied bound on t`. Ten
rounds of this is a genuinely calibrated estimator, and it is the most compelling thing to put in
the write-up.

---

## 7. Price book (build before round 1)

`t` is German tradesperson pricing. Ground the model instead of letting it guess. Rough 2025/26
net figures to verify and extend:

| trade | hourly labour (net) |
| --- | --- |
| Maler / Lackierer | 45–65 €/h |
| Fliesenleger | 50–70 €/h |
| Bodenleger | 45–65 €/h |
| Elektriker | 60–85 €/h |
| Sanitär / Heizung | 65–95 €/h |
| Trockenbau | 45–65 €/h |
| KFZ-Werkstatt (markengebunden) | 90–180 €/h |
| Trocknungsgerät | 15–30 €/day |

Plus €/m² and €/piece for common materials (laminate, tiles, screed, skirting boards, paint,
windshield, bumper, …), and standard German invoice conventions:

- **19 % USt.** on almost everything; VAT may be stated per line.
- Anfahrtspauschale / Kleinmaterialpauschale are normal and usually legitimate.
- Entsorgung / Baustellenreinigung are normal line items.
- Watch for the classic inflations: doubled quantities, "Sonderzuschlag", a whole-room renovation
  billed for a 2 m² water stain, brand-new premium replacing an old worn part.

---

## 8. Traps checklist

| # | Trap | Guard |
| --- | --- | --- |
| 1 | **`b = 0` / defaults submitted** | Hard assert: no submission leaves the process with all-zero `b` unless every item is genuinely uncovered. This is the −3247 mistake. |
| 2 | **Net vs. gross.** Submitting net = a systematic 19 % under-estimate on *both* `a` and `b`. | Compute gross explicitly, log both, assert `gross > net`. |
| 3 | **Per-unit vs. line total.** Handout is explicit: submit the whole line. | Assert `total ≈ qty × unit_price`; log qty for every item. |
| 4 | **Quantity mis-parse** (18 m² read as 1.8) — a 10× error | Cross-check parsed line totals against the invoice's printed total. |
| 5 | **Over-shading** — no penalty, just missing income | §6 calibration. Zero rejections across a round is a red flag, not a success. |
| 6 | **Coverage miss** — 100 % error, the biggest single one | Separate high-effort step; enumerate policy exclusions explicitly. |
| 7 | **Missing the 60 s window** | Two-stage submit + hard force-submit timer at t+55. |
| 8 | **Two machines submitting** | One primary process, manual announced failover. |
| 9 | **Silent LLM failure → zeros** | Per-item deadline → explicit fallback ladder, WARN logged. Never a silent zero. |
| 10 | **Hammering the API for the key** | Bounded retries, backoff + jitter, start polling only ~3 s early. |
| 11 | **Key leak** | `.env`, gitignored. Not in Discord, not in screenshots, not in the write-up. |
| 12 | **Rounds run all night** | Scheduler + alerting, or an agreed rota. Missed rounds are −3247 each. |

---

## 9. Winning the "style" half

Judging weighs methodology. QuantCo's own slides say: *"Claims Agents & Statistical Modelling"*
and *"Human In the Loop Workplace — Feedback for AI"*. Mirror their thesis:

1. **The decision-theoretic derivation** (§2). The `q > 2/3` rule and the `0.75·m` shading factor,
   derived rather than guessed. This is the differentiator — most teams will hand-tune numbers.
2. **The calibration loop** (§6). Extracting one-sided bounds on a secret threshold from rejection
   outcomes, and closing the loop across rounds. This is literally their product.
3. **Human-in-the-loop by design** (§4). The agent handles the tail; a human reviews the three
   largest items in the last 10 seconds. Not "we let the LLM decide".
4. **Reliability engineering**: latency budget, two-stage submit, explicit fallback ladder, no
   silent failures. Show the log.
5. **A calibration plot**: our estimate vs. the implied `t` bounds, over rounds. One chart that
   proves the estimator improved.

Keep a `WRITEUP.md` growing from round 1 — do not write it at the end from memory.

---

## 10. Team split

| Role | Owns |
| --- | --- |
| **Ops / Runner** | API client, key fetch, decrypt, orchestrator, scheduler, the submit button. Owns the 60 s budget. |
| **Extraction** | PDF → line items, quantities, units, VAT. The trap-checklist items 2–4. |
| **Valuation** | Pricing agent, price book, prompts, ensemble. |
| **Coverage + Calibration** | Policy/relatedness agent (Rule C), leaderboard scraping, the §6 loop. |
| **Style** | `WRITEUP.md`, calibration chart, the final presentation. |

Small team? Merge Style into Coverage, and Extraction into Ops. **Never merge away the Runner.**

---

## 11. Go / no-go before round 1

- [ ] API key obtained, in `.env`, not committed
- [ ] `API_HANDBOOK.md` read; submission schema written down
- [ ] Round trip on case 0 succeeded; overwrite semantics confirmed
- [ ] All encrypted zips pre-downloaded; `7z` works on the runner machine
- [ ] Full rehearsal on case 0: submission #1 lands by **t+20s**
- [ ] Fallback ladder tested by deliberately breaking the PDF parser and the LLM call
- [ ] Assert in place: no all-zero-`b` submission can leave the process
- [ ] Net→gross conversion verified against case 0 by hand
- [ ] Runner + standby agreed; rota for overnight rounds
- [ ] Round-log writing to disk; leaderboard scraper ready

---

## Appendix — the two numbers, on a card

```
per line item:
  covered by policy AND related to the damage?
    no  →  a = 0,  b = 0
    yes →  m = median(net unit price) × qty × (1 + VAT)      ← gross line total
           a = 0.75 · m          (charge)
           b = 0.87 · m          (accept limit; raise toward 1.0·m once calibrated)

when in doubt: never b = 0.  Accepting is bounded-bad, rejecting is not.
```
