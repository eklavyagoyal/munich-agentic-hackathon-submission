# Team Oasis — Claim to Fame: approach, evidence, and an honest post-mortem

*QuantCo Agentic Hackathon Munich, 22–23 August 2026. Figures below are as of game 93
of 100; the last 20 rounds carry a 3× weight.*

A German-language companion with more architectural detail is at
`pipeline/docs/SUBMISSION.md` (authored by Luis Dehlwes). This document is the English
summary plus the succeeded/not-succeeded assessment.

---

## The game, and the two asymmetries that decide it

Every round, all 17 teams receive the same claim — policy, damage description, photo,
and an invoice with prices redacted. Each line item has a secret fair value `t`. Blind,
we submit `a` (what we charge every opponent as handyman) and `b` (the limit up to which
we accept incoming charges as insurer).

Two asymmetries dictate everything, and both took us too long to internalise:

1. **A fair charge (`a ≤ t`) is paid by every opponent — including the ones who reject
   it**, since rejecting still owes us `a` plus a 0.5a penalty. So undercharging is a
   silent, total loss, and *acceptance rate is a vanity metric*.
2. **Overbidding costs the issuer nothing directly.** You simply collect from the ~18%
   of reviewers who accept anyway. Undercharging forfeits a guaranteed 16×.

Together: never lower `a` out of caution, and treat `b` as a threshold problem — accept
only when `P(fair) > 2/3`, which follows from the 1.5× rejection penalty against the 1×
acceptance cost.

## Architecture

```
DATA        sync.py       every 5 min: schedule, official score matrix, keys, cases,
                          and 254,000+ transactions from ALL 17 teams -> SQLite
ANALYSIS    bounds.py     interval-censored t-bands derived from the whole field's flows
            calibrate/    backtests and policy sweeps with no LLM cost
            opt.py
DECISION    estimate.py   3-model LLM ensemble, median, text-only
            anchors.py    retrieval of proven price bands into the prompt
            digest.py     per-case policy digest (exclusions, caps)
            policy.py     t-hat -> (a, b); hot-reloaded from data/policy.json
RUNNER      play.py       key -> decrypt -> parse -> estimate -> decide -> submit
            submitter.py  the only module with write access: event log, double-submit
                          guard, echo verification, emergency fallback path
```

Two disciplines carried more weight than any model choice:

**Validate before trusting.** Our P&L reconstruction from raw transactions had to
reproduce the official score matrix to **0.0000** (1,530 cells) or no derived number was
used. That gate paid for itself twice — it caught a rule misreading, and it caught the
organisers switching on the 3× multiplier at game 81 unannounced. Without it,
mis-scaled bands would have quietly poisoned every anchor.

**Nothing untested under a live runner.** Every code change went backtest → game-0 dry
smoke → restart between rounds. Parameters, by contrast, are hot: `policy.json` is
re-read before every game, which let us make five validated policy changes inside one
hour of live play on a 12.6-minute round cadence.

## Why we succeeded — from 15th to 9th

- **The public transaction API was open to everyone; the alpha was in the pipeline.**
  Interval-censored bands, retrieval anchors, measured field curves, and exact
  counterfactuals on our own rejected charges — rejection flows reveal ground truth
  perfectly (a penalty proves the charge was fair; zero proves it was fraud).
- **Retrieval anchors were the single biggest modelling win**: estimation error against
  band-midpoint fell **44% → 29%**. They work because the tournament reuses line
  templates — 434 labelled items span only 243 distinct (description, unit) pairs, and
  49% of items have a near-duplicate in an earlier game. Gating on similarity is what
  makes it work: ungated, the same retrieval is worth nothing (+2,615, noise); gated, it
  is worth +251,429.
- **Game theory before machine learning.** The payoff asymmetries fixed the policy shape
  before any estimator question arose.
- **Per-case policy digest.** Coverage is decided per case, not per wording — game 48
  burned 18 of 27 items under one pool-exclusion clause we had not read.
- **Value-dependent acceptance limits.** Fraud purchases cluster on cheap items and
  wrong rejections on expensive ones, so a single global limit is wrong at one end by
  construction. Banding it cut fraud purchases from ~32k to ~1k per game.
- **More context made the models bolder, not better.** A text-only median ensemble beat
  every variant using the photo or the raw policy, reproduced twice. Calibration beat
  capacity.
- **Result:** issuer income since game 81 is **2nd of 17** (353,387, against Codacabana's
  354,708 and eyay's 340,147), with the field's best paid-rate.

## Why we did not succeed — we are still 651,030 down

- **We banked half the deficit before we started measuring.** Games 1–43 lost ~328k with
  LLM estimates, boolean coverage decisions, and no validation layer. The rebuild worked;
  it came too late to pay for the tuition.
- **One forgotten process cost more than every model error in the second half
  combined.** A stale runner on a third machine kept submitting; because `PUT` is
  last-write-wins, it overwrote a correct submission with zeros. **Game 82: −242,000 in
  a single 3×-weighted round.** Diagnosed forensically — our score matched the
  no-submit cluster to the cent despite the server having echo-confirmed our own values.
  "Never two runners" belongs in the architecture (read-only flags, event log, echo
  verification), not in anyone's discipline.
- **Estimate variance on big-ticket items is unsolved.** Two rounds returned *exactly
  zero* issuer income (~76k) because our estimate was above `t` on every line, while the
  rest of the field collected on accepted overcharges. The same variance produced
  +134,400 in the other direction three rounds later. We reduced the frequency; we never
  fixed the magnitude.
- **We are net negative overall**: income 2,707,516 against costs 3,358,546. Of 17,632
  reviewer decisions, 4,672 (26.5%) were wrong — 2,738 fair charges rejected and 1,934
  fraudulent ones bought.
- **We could not close the reviewer side.** Ten separate candidates were measured and
  killed. The wall is structural: a rejected fraudulent charge records an amount of
  zero, so the cost of raising `b` is unknowable in advance, and every bound therefore
  assumes maximum exposure and loses. Only once we recovered 63% of those amounts from
  *other teams'* acceptances could we price it exactly — and the answer was that our
  limit was already near-optimal in both directions.

## What we would tell ourselves at game 1

Build the data foundation first and the decision layer second. Validate every derived
number against the official truth before acting on it. Make the operational failure
modes impossible rather than merely discouraged. And measure before shipping: of roughly
fourteen ideas we believed in, four survived contact with a backtest — including several
that looked excellent offline and inverted in the live engine.

## Operations

```bash
python -m backend.app.sync --loop        # data foundation, every 5 min
python -m backend.app.play --game 0      # mandatory dry smoke before arming
python -m backend.app.play --watch --submit
```

`C2F_READONLY=1` on every non-runner machine makes the submitter raise instead of
writing. One submitter module; the event log reconstructs already-submitted games across
restarts; the emergency path submits fallback rates rather than nothing, because a 0/0
game is the most expensive possible outcome.

*No claim data — invoices, policies, damage descriptions, or images — is committed to
this repository, per the organisers' requirement.*
