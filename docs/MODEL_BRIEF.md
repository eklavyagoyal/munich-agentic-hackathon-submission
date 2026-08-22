# Research + implementation brief: a valuation model for Claim-to-Fame

**Audience:** a deep research/coding session with repo access.
**Written:** 2026-08-22 ~15:25 CEST, after games 1 and 2 of 100.
**Team:** `Oasis`. 17 teams. One game every 757.6 s until 2026-08-23 09:50 UTC.

Everything in §3 was measured, not assumed. Do not re-derive it; do challenge it if
you find contrary evidence, and say so explicitly.

---

## 0. What to produce

A **per-line-item valuation model** that outputs a posterior over the secret fair
threshold `t`, plus the plumbing to train it from tournament data that is already
available. Concretely:

1. A dataset builder that reconstructs every completed game into
   `(features, censored bounds on t)` rows.
2. A model that predicts `t` (a distribution, not a point) from the line item and
   its case context.
3. A `rules_user/` rule that consumes it, loading as SHADOW, with a written
   promotion criterion.
4. A backtest that reports what our score *would* have been on all completed
   games, versus the price book we run today.

Deliverables in §8. Constraints in §7 are hard — read them before designing.

---

## 1. The game, exactly

Per line item there is a secret threshold `t` = the maximum a claims expert would
sign off. **If the item is not covered by the policy, `t = 0`.** There is also a
secret payment cap `c ≥ 4t`, shared across teams.

For every line item we submit two numbers, as **gross totals for the whole line
item** — not net, not per-unit:

- `a` = charge price, what we bill every other team as handyman `H`.
- `b` = acceptance limit, the most we will pay as insurer `I`.

Every ordered pair of teams transacts on every line item. Payoffs:

|                        | `a ≤ t` (fair)                  | `a > t` (fraud)                    |
| ---------------------- | ------------------------------- | ---------------------------------- |
| `a ≤ b` price accepted | `I` pays `a`, `H` gets `a`      | `I` pays `min(a,c)`, `H` gets same |
| `a > b` price rejected | `I` pays `1.5a`, `H` gets `a`   | `I` pays `0`, `H` gets `0`         |

Two consequences that drive everything:

**As insurer, accept iff `P(a ≤ t) > 2/3`.** Accepting costs `a` when fair and
`min(a,c)` when fraud; rejecting costs `1.5a` when fair and `0` when fraud. With
`a ≤ c`, accept is better iff `(1−p)a < 0.5pa`, i.e. `p > 2/3`. So `b` belongs at
the **1/3-quantile** of our posterior for `t`. The existing code does this and it
is correct — verify the derivation, do not casually change it.

**As handyman, a fair charge is risk-free.** If `a ≤ t` we receive `a` from every
opponent whether they accept or reject. Above `t` we receive `min(a,c)` only from
opponents whose `b ≥ a`, and nothing from the rest.

**Open strategic question — this is worth real analysis.** Because `c ≥ 4t`,
deliberately charging into the fraud zone can pay if enough of the field
over-accepts. Expected revenue is `a·1` for `a ≤ t` versus
`min(a,c)·F(a)` for `a > t`, where `F(a)` is the fraction of teams with `b ≥ a`.
`F` is **measurable** from the transactions endpoint (§4). Our current strategy
charges `0.75 ×` the median estimate, which never tests this. Quantify whether a
higher charge beats it given the field's *actual* acceptance behaviour, and note
that `F` will shift as other teams fix their own bugs. Recommend a policy, with
the evidence.

---

## 2. What exists today

Rule engine over four stages: `COVERAGE` (is `t = 0`?) → `PRIOR` (supply a
belief) → `ADJUST` (multiply) → `GUARD` (clamp/veto). `ADJUST` and `GUARD` are
commutative, so rules cannot conflict by ordering. New rules dropped into
`rules_user/` load as **SHADOW** — computed and logged, never applied — until
explicitly promoted.

| file | role |
| --- | --- |
| `c2f/estimate/pricebook.py` | 34 German trade rates; keyword match + unit compatibility. The only estimator running today. |
| `c2f/decision/quantile.py` | belief `(median, sigma)` → `(a, b)`. The 2/3 rule lives here. |
| `c2f/estimate/ensemble.py` | LLM prior, fetched off the hot path. Abstains with no key. |
| `c2f/estimate/llm.py` | the only file that knows a model provider |
| `c2f/ingest/parse.py` | pdftotext → line items; gap filling and unit synonyms |
| `c2f/runner.py` | the round loop; staged submission at 15 s and 52 s |
| `c2f/scheduler.py` | the always-on loop |
| `c2f/calibrate.py` | fits `t` from round outcomes — **written against a guessed wire format, never run against real data** |
| `c2f/submit/client.py` | the real API |
| `tools/play_once.py` | play one game off-schedule; exit code reflects whether the server stored our numbers |
| `tools/dashboard.py` + `ui/` | read-only dashboard, localhost |

Tests: 134 passing. Run `PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`.

**The model plugs in as a PRIOR rule in `rules_user/`.** Do not restructure the
engine. Do not touch `c2f/runner.py`'s hot path without a stated reason.

---

## 3. Established facts — measured, with numbers

**Scoring reality so far.** Game 1: **−8273.70**. We submitted nothing (see
below), so every line item defaulted to `a = 0, b = 0`. Game 2: submitted
successfully, 7 items, `a` total 307.79 / `b` total 322.76, HTTP 200, echo
verified, 2.03 s end to end.

**Game 1's loss decomposes exactly.** Transactions show our rejected-charge sum
was `5515.80`, and `5515.80 × 1.5 = 8273.70` — the leaderboard's paid figure to
the cent. Therefore **every charge we rejected was in the fair zone**, each
costing us `1.5a`. Our `b = 0` rejected 45 fair claims. As issuer we received
`0.00` on 288 rows because we charged nothing.

**Most of the field was also broken in round 1.** Per line item, only 3–4 of 16
issuers charged a nonzero amount. Expect this to change as teams fix bugs; do not
tune against round-1 field behaviour.

**Invoices contain no prices.** Columns are `POS. | DESCRIPTION | AMOUNT | UNIT |
TOTAL` and the money columns are empty — zero money-shaped tokens in case 1. So
this is valuation from scratch, not judging a stated price. `AMOUNT` is the
quantity.

**Case contents** (case 1, sizes): `description.txt` 987 B, `policy.txt` 51 009 B,
`invoices.pdf` 44 078 B, `photo.jpg` 3 251 441 B. **The photo is currently
ignored entirely.** `GAME_DESCRIPTION.md` calls the image `images.png`; the real
archive had `photo.jpg`. Handle both.

**Invoices are in English**, at least so far (`pcs`, `hrs`, `m²`, `m`), while the
price book's keywords are predominantly German. Case 2 matched **zero** of the 34
entries, so all 7 items fell to the generic band. This is the single biggest
known source of valuation error.

**Case shapes seen.** Case 0: 1 item (degenerate test game). Case 1: 18 items,
one printed with en-dashes for qty and unit. Case 2: 7 items, no keyword matches.

**Two parser failure modes already cost or nearly cost rounds** — both fixed,
both worth understanding before you touch `parse.py`:
- A dash in the qty/unit column dropped the row, contiguity failed, `ParseError`
  raised *before* the first submission, and the round submitted nothing. That is
  the whole of game 1.
- Filling gaps only up to the highest *parsed* position silently shrank the
  invoice; with every unit token mangled, 18 items became 3. Now the count comes
  from the printed positions (longest contiguous run from 1).

**Fatal paths that remain** (deliberately — we cannot know the item count): no
`pdftotext`, no text layer in the PDF, or zero rows parsed. A scanned image-only
invoice still submits nothing. **This is an open task, see §8.**

**Timing.** Cadence 757.6 s. Submission window is short: game 2 started 13:12:37
UTC and was closed (`403 Game has already ended`) about six minutes later. Our
round takes ~2 s, so latency is not the constraint — but **there is no retroactive
fix.** Every round is one shot.

**Clock.** Use `Leaderboard.server_now()`, corrected from the HTTP `Date` header.
Our clock has measured up to 1.6 s off.

---

## 4. The data — you have more than you think

**Decryption keys remain fetchable after a game ends.** Verified: games 1 and 2
both returned keys minutes after closing; game 3 correctly returned
`403 Game has not started yet`. So the entire tournament is **harvestable
offline** — no need to capture anything inside the 60-second window.

`GET /api/games/{id}/key` with header `X-API-Key` returns `{"decryption_key": …}`.
All 101 encrypted archives are already on disk at `public-cases-ehl/cases/case_NN.zip`.

**Ground truth comes from `GET /leaderboard/api/transactions`** (unauthenticated),
required params `game_id` and `team`. Envelope
`{items, page, page_size, total, total_pages}`; rows:

```json
{"issuer": "Alpha", "reviewer": "Oasis", "line_item_index": 1,
 "accepted": true, "amount": 0.0}
```

Counts confirm the structure: game 1 → 576 rows = 18 items × 32, game 2 → 224 =
7 × 32, where 32 = 2 × (17 − 1). Filtered to rows involving `team`, so per line
item we see ourselves as reviewer against 16 issuers **and** as issuer against 16
reviewers. `amount` is the charge `a`; the 1.5× penalty is applied in the
leaderboard totals, not in this field — confirm this holds on later games.

**This means we observe other teams' charge prices.** That is a direct read on
the field's collective estimate of `t`, per line item.

Also available: `/leaderboard/api/standings`, `/performance`, `/matchup`,
`/games`. All paged with the same envelope. A missing param returns `422`.

---

## 5. Turning transactions into labels

We never observe `t`. We observe interval-censored evidence. Derive it carefully —
this is the crux and the existing `c2f/calibrate.py` was written against a guessed
format, so treat it as a sketch, not a spec.

Signals per line item, per issuer charge `a`:

- **A rejected charge whose payment was `1.5a`** proves `a ≤ t`: a **lower bound**.
  (Fraud rejections cost the insurer `0`, so a nonzero rejection payment is
  positive proof the charge was fair.) This is how we know game 1's rejections
  were all fair.
- **An accepted charge** tells you about the *reviewer's* `b`, not about `t`
  directly — `a ≤ b`. Do not confuse the two. Aggregated across reviewers this
  gives you `F(a)`, the field's acceptance curve, which §1's strategic question
  needs.
- **Issuer behaviour** across 16 teams gives a distribution of independent
  estimates of `t`. Teams that survive many rounds are presumably better
  calibrated; consider weighting by their standing.

Work out precisely which combinations are identifying, and write down the
likelihood you are fitting. State your assumptions about what other teams'
strategies are, and how sensitive your bounds are to them.

Aim: `~1000` labelled line items by tournament end (100 games × ~10 items), and
about 25 items usable **right now** from games 1–2, growing every 12.6 minutes.

---

## 5a. RESOLVED: transactions give an exact fair/fraud label

Measured on game 2 (Oasis as issuer, 43.97 charged on all 7 items), the
`accepted` x `amount > 0` cross-tab has three cells and no fourth:

```
accepted=False  amount>0   n=15     rejected, yet the issuer was still paid
accepted=False  amount=0   n=71     rejected, nothing flowed
accepted=True   amount>0   n=26     accepted and paid
```

`amount` is what the issuer **received**. Read against the payoff matrix in §1
that is an exact classifier, not an estimate:

- **rejected AND paid** is only possible in the fair column: `I` pays `1.5a` and
  `H` gets `a`. Therefore **`a <= t`**.
- **rejected AND unpaid** is only possible in the fraud column. Therefore
  **`a > t`**.
- accepted tells you `a <= b` for that reviewer, and nothing about `t` on its own.

So for every `(issuer, line_item)` pair where at least one reviewer rejected, we
learn which side of `t` that charge fell on — **exactly**. With 16 other issuers
per line item, `t` is bracketed:

```
max(charges known fair)  <=  t  <  min(charges known fraud)
```

Collect both bounds per item. This is a far stronger signal than the
interval-censoring the original design assumed, and it is available for every
completed game right now.

**Ground truth already extracted, game 2** (our uniform 43.97 charge):

| items | outcome | inference |
| --- | --- | --- |
| 1, 4 | paid by all 16 (`703.52`) | `t >= 43.97` |
| 2, 3, 5, 6, 7 | paid by 1-2 of 16 | `t < 43.97` |

**Five of seven line items had a threshold under EUR 44.** Items not covered by
the policy have `t = 0` by definition, so a large share of line items are
plausibly uncovered or near-worthless. Any model that predicts a single central
price per item will be wrong on most of them. Establish the mass at/near zero
before tuning magnitudes — a unimodal log-normal prior cannot express
"usually nothing, occasionally EUR 600".

**Where we stand (after 3 games, 17 teams).** Rank 10. Income 1802.77, costs
13419.93, net **-11617.16**. Seven teams have submitted nothing at all: income
0.00, costs 13417.59, net -13417.59 — that is the do-nothing baseline, and our
costs are within EUR 3 of it, meaning our acceptance limits reject nearly every
fair claim and eat the `1.5a` penalty just as if we had submitted zeros. The
leader is at income 45934.56, costs 7695.67, net **+38238.89**: they earn 25x our
income while paying 43% less.

**The asymmetry that follows, and it is not symmetric at all.** As issuer there is
**no penalty for charging above `t`** — an over-charge simply forgoes income
(`H` gets `0`), it never costs us. As insurer, accepting a fraudulent charge
costs real money. So:

- `a` can be aggressive; its only cost is opportunity cost, because a fair charge
  is paid by all 16 reviewers (`16a`) while an over-charge collects only from the
  few whose `b` is high enough.
- `b` is where the money is lost, and it deserves the conservative treatment.

Today both are derived from the same belief and move together. Consider
decoupling them, especially for low-confidence beliefs where the source is
`pricebook:unknown:*`.

**Caveat on our own recent change, flag for the backtest.** At ~15:15 CEST the
unknown-item prior was raised from a flat EUR 58.30 to the book's per-unit support
(EUR 319.31 for an unknown piece), which also raised `b` from 46.11 to 215.72.
Given that 5 of 7 items in game 2 sat below EUR 44, that may increase our exposure
to accepting fraud. It went live for game 3 onward. **Measure it** rather than
assuming either way: compare our costs and income per item on games 1-2 versus
3 onward. Do not tune on a single game.

---

## 6. Modelling

Compare candidates honestly and recommend one, with a backtest (§8). Suggested
frontier, cheapest first:

1. **Fix the price book's reach.** English/German keyword coverage, more trades,
   better unit handling. Cheap, interpretable, no training data needed. Probably
   the best value per hour right now — quantify it before doing anything clever.
2. **Unit-conditional priors from data.** We already default unknown items to the
   book's full support per unit (`h 45–190`, `m2 3–110`, `stk 60–1200`,
   `lm 8–18`, `pauschal 20–90`, `tag 15–32`, net per unit of quantity). Replace
   those with posteriors fitted from the censored bounds.
3. **A regression on text features** — TF-IDF or character n-grams over the
   description, plus `qty`, `unit`, trade — predicting `log t`. Quantile
   regression is a natural fit since we need a distribution, and the 1/3-quantile
   is exactly what `b` wants. Must run offline, CPU-only, in well under a second.
4. **Coverage classification** (`t = 0`) as its own model. `policy.txt` is 51 KB
   of exclusions and `description.txt` says what was actually damaged; an item
   unrelated to the damage has `t = 0`. Getting a covered item wrong here is very
   expensive in both directions. Textual entailment between the item description,
   the damage report and the policy's exclusion clauses.
5. **The scope check** — flag line items whose quantity exceeds what the damage
   supports (46 m² of repainting for an 18 m² room). Deterministic, needs no
   credentials, and is the one thing the absent LLM was buying that plain
   string-and-number work recovers. Not yet started.
6. **The photo.** 3.25 MB per case, entirely unused. Worth stating whether any
   offline signal is extractable cheaply, or whether to drop it explicitly.

Sanity requirements for whatever you build: it must produce a **median and a
sigma** (the decision layer consumes a log-normal-ish belief), it must **abstain**
rather than guess when out of distribution, and abstention must fall back to the
price book.

---

## 7. Hard constraints — do not violate

- **Never commit claim data.** Discord, 14:35 today: repos will be made public and
  checked-in claim data (invoice PDFs, policies) carries a **ranking penalty**.
  Decrypted files go only to gitignored paths (`data/`, `logs/`). Do not paste
  invoice or policy text into commit messages, issues, or agent transcripts —
  agent sessions are checkpointed to the submission repo. See
  `fixtures/synth/README.md`.
- **Exactly one process may submit.** One API key per team, PUT is last-write-wins.
  A second writer can overwrite a better submission with a worse one. The daemon
  runs on one machine only; everyone else works against `MockApi`.
- **The hot path is frozen during a round.** No code, config, or rule changes; the
  rule set is snapshotted at round start so any round is reproducible from the
  event log. Restart the daemon only in the ~12-minute gap between games, and
  verify afterwards that the process start time is later than the file mtime.
- **Never let one bad round kill the loop.** Every failure is caught, logged and
  counted, and the loop advances. There is no exception worth stopping 100 games
  for.
- **Prefer submitting a rough number to submitting nothing.** Omitted items score
  `a = 0, b = 0`, which rejects every fair claim *and* pays `1.5a` on each. That
  is strictly worse than a bad estimate.
- **Budget.** One minute per round, wall clock, including key fetch, decrypt,
  parse and submit. Tier 1 must land within ~15 s; anything slower is upside only.
- **No credentials for the model.** There is no LLM key and none is coming. Work
  offline, CPU-only. `llm_prior` and `llm_coverage` abstain cleanly and cost
  nothing.
- Rules land in `rules_user/` as SHADOW. Promotion is a deliberate, separate act.

---

## 8. Deliverables and acceptance criteria

1. **`tools/harvest.py`** — for every completed game: fetch key, decrypt to a
   gitignored path, parse, fetch transactions, and write one row per line item
   with features and censored bounds. Idempotent, resumable, safe to run while the
   daemon is live (read-only w.r.t. the API except key fetches).
2. **A written label derivation** (§5): the likelihood, the identifying
   assumptions, and a sensitivity note.
3. **The model**, plus `rules_user/<name>.py` exposing it as a PRIOR rule that
   abstains out of distribution.
4. **A backtest over all completed games** reporting our actual score versus
   (a) the price book we run today and (b) your model, using the real payoff matrix
   in §1 and the observed field behaviour. This is the number that decides whether
   we promote. Report it honestly, including variance across games.
5. **A promotion criterion** stated in advance: what the backtest must show.
6. **A recommendation on the charge policy** (§1's strategic question), with the
   measured acceptance curve `F(a)`.
7. **The image-only-PDF gap** (§3): either close it (OCR, or infer the item count
   another way) or state clearly that it stays open and why.

Every claim in your report needs the command or file:line that produced it. If you
could not verify something, say so; do not fill gaps with plausible reasoning.

---

## 9. Non-goals

- Do not restructure the rule engine, the scheduler, or the submission client.
- Do not add a service, container, queue, or database. Files and a git repo.
- Do not add a dependency for what a few lines can do. `pandas`/`scikit-learn` are
  justified for real modelling; a framework is not.
- Do not build opponent-specific modelling beyond the aggregate acceptance curve
  `F(a)` — 17 teams over 100 games is thin data for per-team behaviour.
- Do not tune against games 1–2 field behaviour. The field is still fixing bugs.
- Do not deploy the UI anywhere public.

---

## 10. Open questions to resolve empirically

1. ~~Does `amount` stay the base charge?~~ **RESOLVED — see §5a.** It is what the
   issuer received, and it yields an exact fair/fraud label per transaction.
2. Does `transactions` expose rows for pairs not involving us? The counts say no
   (32 = 2×16 per item), which caps opponent modelling at what our own
   transactions reveal.
3. Can `t` be pinned tightly, or only bounded? What is the width of the interval
   after a few games, per unit class?
4. How much of the valuation error is coverage (`t = 0`) versus magnitude? These
   need different fixes; measure the split before investing in either.
5. Are invoices always English, or does the language vary by case? This decides
   how much German keyword work is worth.
6. Does `c ≥ 4t` ever bind in observed data — i.e. is anyone charging above `4t`?
7. Does game `status` distinguish `running` from `completed`? A scheduler would
   rather trigger on that than on wall-clock arithmetic.
