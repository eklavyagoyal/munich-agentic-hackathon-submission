# Claim to Fame — Pipeline, Rule Engine & Live UI

Concrete build plan. Companion to [ARCHITECTURE.md](ARCHITECTURE.md) (strategy + hosting).
This document is about **software structure**: how the round runs, how anyone can drop in a rule
mid-tournament without endangering a round, and what the live UI is.

---



## 0. The two clocks

Everything follows from this. The tournament is not one loop, it is two:

| | **Hot path — 60 s** | **Cold path — ~9 min between cases** |
| --- | --- | --- |
| Owns | decrypt → parse → estimate → decide → submit | rule reload, calibration refit, shadow scoring, human review |
| Rule | nothing may block, nothing may be added | everything mutable happens *only* here |
| Failure | costs a round | costs nothing |

**Hard invariant: no code, config, or rule ever changes during the hot path.** The rule set is
frozen at `T−30s` and that snapshot is recorded with the round. This single constraint is what
makes "teammates add rules mid-tournament" safe rather than terrifying.

---

## 1. Process model

Two processes, deliberately.

```
┌─────────────────────────────────────────┐        ┌──────────────────────────┐
│  runner   (hot path, zero UI code)      │        │  ui  (FastAPI+WS)        │
│                                         │        │                          │
│  folder sync ─► case store (zips)       │ events │  tails events.jsonl      │
│  key poller  ─► decrypt ─► parse        ├───────►│  serves dashboard        │
│  estimate ─► RULE ENGINE ─► decide      │ jsonl  │  writes overrides.json   │
│  submit ─► verify                       │◄───────┤  (read by cold path only)│
└─────────────────────────────────────────┘        └──────────────────────────┘
```

**Why two.** The runner must survive anything the UI does. A `pip install` for a chart library,
a websocket that wedges, a teammate reloading the page fifty times — none of it can reach the
process that has 60 seconds to submit. The coupling is a **one-way append-only file**.

**Why not microservices.** 60-second budget. Every network hop is a new failure mode for zero
benefit. The runner is one asyncio process.

**Backpressure rule.** The runner *never* awaits the UI. Events go to a bounded queue; on
overflow it drops and increments a counter. A slow consumer must not be able to add a
millisecond to the hot path.

---

## 2. The event stream is the backbone

One append-only JSONL stream serves **four** consumers, so we instrument once:

1. the live UI,
2. post-mortem replay ("what did we think at T+22s?"),
3. the calibration dataset (§6),
4. the strategy write-up that the judges score.

```jsonc
{"ts": 1755861234.512, "round": 7, "case": "case-07", "seq": 41,
 "type": "item.decided",
 "payload": {"idx": 3, "a": 412.86, "b": 489.30,
             "trace": [{"stage":"prior","rule":"llm_ensemble","median":543.2,"sigma":0.24},
                       {"stage":"adjust","rule":"trade_bias_flooring","scale":0.94},
                       {"stage":"guard","rule":"pricebook_clamp","clamp":[120,900]}]}}
```

Event types: `round.scheduled` · `key.requested` · `key.received` · `case.decrypted` ·
`case.parsed` · `item.belief` · `rule.fired` · `item.decided` · `submission.built` ·
`submission.sent` · `submission.verified` · `round.closed` · `alert`.

**Every decided item carries its full trace.** In a 10-minute cycle you cannot debug what you
cannot see, and the trace is also exactly the "explain your methodology" artefact.

---

## 3. Ingest & decryption

```
cold path:  folder sync ──► verify each archive is well-formed ──► data/cases/*.zip
                            (wrong-password probe: confirms the archive parses)
T−2s:       poll key endpoint, jittered, bounded retries
T+0s:       key + case id ──► 7z x -p<key> ──► tmpfs ──► parse
```

- **Zips are pre-synced, never fetched in the hot path.** Only the key is time-gated.
- **Verify archives in advance.** A corrupt download discovered at T+1s is a lost round; the same
  discovery at T−5min is a re-download. Probe each archive with a deliberately wrong password —
  a well-formed archive answers "wrong password", a broken one answers something else.
- **Extract to tmpfs**, not disk. Milliseconds matter and the plaintext should not linger.
- **Case identity must be explicit.** We hold many archives; the key response must tell us which
  case it unlocks. If it does not, we need a naming convention agreed with the organisers — see
  open questions. Guessing by trying keys against archives in sequence is a latency trap.
- **Parse:** `pdftotext`/`pdfplumber` first, vision only as fallback. The invoices are
  machine-generated; running vision on a text-layer PDF is a self-inflicted wound.

---

## 4. The Rule Engine — the core of the modularity ask

### 4.1 Four stages, chosen for their algebra

```
COVERAGE ─► PRIOR ─► ADJUST ─► GUARD ─► decide(a,b)
 pick one   pick one  all, ×    all, ∩
```

| Stage | Semantics | Order matters? |
| --- | --- | --- |
| `COVERAGE` | is `t = 0`? Highest-priority non-abstaining rule wins | yes — priority |
| `PRIOR` | supplies the belief. Highest-priority non-abstaining rule wins | yes — priority |
| `ADJUST` | multiplicative scales, **all applied, product taken** | **no — commutative** |
| `GUARD` | clamps, **all applied, intersection taken** | **no — commutative** |

This is the whole trick. The classic way rule engines rot is contributors fighting over
execution order. Here the two stages people actually add to in bulk — `ADJUST` and `GUARD` — are
**order-independent by construction** (multiplication commutes, interval intersection commutes).
Two teammates can add calibration rules simultaneously and there is no merge conflict in
behaviour, only in arithmetic. Only the two "pick one" stages carry priority, and those change
rarely.

### 4.2 The contract

```python
class Rule(Protocol):
    name: str
    stage: Stage             # COVERAGE | PRIOR | ADJUST | GUARD
    priority: int = 0
    author: str = ""

    def apply(self, ctx: Context) -> Verdict | None: ...
```

```python
@dataclass(frozen=True)
class Context:               # read-only. Rules cannot mutate anything.
    case: Case; item: LineItem
    policy_text: str; damage_description: str
    belief: Belief | None    # what previous stages produced
    history: History         # past rounds + calibration
    opponents: OpponentModel

@dataclass(frozen=True)
class Verdict:               # every field optional — a rule contributes only what it knows
    covered: bool | None = None
    belief:  Belief | None = None          # PRIOR: replace
    scale:   float | None = None           # ADJUST: multiply
    clamp:   tuple[float, float] | None = None   # GUARD: intersect
    veto:    str | None = None             # force safe fallback, with reason
    note:    str = ""                      # shown in the UI trace
```

**Returning `None` means "no opinion".** Abstention is the default and it is what makes rules
compose — a rule about flooring stays silent on windshields instead of having to pass values
through.

Rules are **pure**: no I/O, no network, no global state. Everything they may read is in `Context`.
That is what makes them replayable offline (§6) and safe to run in the hot path.

### 4.3 Sandboxing — a teammate's bad rule must not cost a round

Rules are untrusted code in a 60-second critical path. Every rule executes behind:

- **Timeout** (50 ms). Pure functions have no excuse; a slow rule is disabled for the round.
- **Exception guard.** Any raise → rule disabled for the round, `alert` event, round continues.
- **Output validation.** `scale ∈ [0.1, 10]`, `clamp` finite and ordered, belief positive and
  finite. Out-of-range → discarded and logged, not clamped silently.
- **Post-conditions on the final result**, after all rules: `0 ≤ a < b`, both finite, `b` never
  `0` unless the item is genuinely uncovered. Violation → fall back to price-book and shout.

A rule can therefore make our numbers *worse*, but it **cannot make us miss a submission** —
which is the only unrecoverable failure in this game.

### 4.4 The lifecycle: how a rule gets in

```
  drop file in rules_user/          (any teammate, any time)
        │
        ▼  cold path only, never mid-round
  import + smoke test on case 0     ── fails ──► rejected, error shown in UI
        │
        ▼
  SHADOW (default)                  computed, traced, displayed — NOT applied
        │
        ▼  a human clicks Promote in the UI, seeing the diff it would have caused
  ACTIVE                            applied to real submissions
        │
        ▼  one click, takes effect next round
  DISABLED
```

**Shadow-by-default is the answer to "how can people add rules mid-tournament safely".** A new
rule's effect is visible on real cases, priced in euros, *before* it can touch a submission.
Nobody has to trust anybody. The UI shows: *"`trade_bias_flooring` would have moved item 3 from
412.86 → 388.09."* Promotion is an informed decision, not a leap.

The rule set active for a round is snapshotted into the event log, so any past round is
reproducible exactly.

### 4.5 Where the LLM sits

The LLM ensemble is **just the default `PRIOR` rule** (`priority = 0`). It is not privileged.
A price-book rule with `priority = 10` overrides it for trades we have solid data on; the LLM
covers the long tail. Same interface, same sandbox, same shadow lifecycle. Swapping models, or
dropping the LLM entirely for a category, is a one-line priority change.

---

## 5. The live UI

**During the round** — one screen, no scrolling, no clicking required to see the important thing:

- Big countdown + current stage; submission tier badges (`#1 sent T+14s ✓`, `#2 pending`).
- Item table: `desc · qty · unit · median · σ · a · b · rules fired`, **the three largest items
  pinned to the top** — that is where the money and the risk are.
- Rows colour-coded by σ. High uncertainty is where a human adds value in 10 seconds.
- **Manual override**: type a value into a cell → it becomes a top-priority `GUARD` veto for that
  item, in that round only, recorded in the trace with the person's name. ARCHITECTURE.md's
  "human window" needs an actual mechanism; this is it.
- Live event tail on the side.

**Between rounds:**

- Rule board: every rule with state (active/shadow/disabled), author, hit rate, and its
  cumulative euro effect. Promote/disable buttons.
- Calibration view: our estimates vs the interval bounds we have learned (§6).
- Leaderboard mirror + our per-round net.

**Stack: FastAPI + WebSocket + one static HTML page, vanilla JS, no build step.** A bundler is a
liability in a hackathon. ~150 lines of JS renders a live table off a websocket. SQLite holds
durable state (rounds, items, beliefs, outcomes) and gives us queryable calibration for free;
JSONL holds the raw stream.

---

## 6. Replay, shadow, and improvement

Because rules are pure and every input is in the event log, **the whole round is a function we
can re-run offline**:

```bash
replay --round 7 --rules rules_user/@HEAD      # what would we submit today?
replay --all --estimator v4 --shadow           # score a candidate over every past case
```

- **Shadow mode for estimators**, same as for rules: run the candidate live, log it, submit the
  incumbent. Zero-risk iteration during a live tournament.
- **Labels are interval-censored** (ARCHITECTURE.md §8): we never see `t`, only bounds, and only
  from *rejections* — acceptance teaches us nothing. Calibration must fit bounds, not average
  point errors.
- The fitted correction lands as an `ADJUST` rule. **Learning and hand-written rules use the same
  mechanism** — there is no separate "model update" path to get wrong.

---

## 7. Build order

Strictly sequential. Each step is useless until the previous one is boring.

| # | Deliverable | Gate |
| --- | --- | --- |
| 1 | Round trip on case 0: key → decrypt → parse → submit a constant | a submission lands. **Nothing else matters until this works.** |
| 2 | Event stream + JSONL + replay skeleton | every stage emits |
| 3 | Rule engine with 4 stages + sandbox + one hard-coded price-book rule | a bad rule cannot kill a round (test it deliberately) |
| 4 | LLM ensemble as `PRIOR` rule, returning a distribution | σ comes out non-degenerate |
| 5 | Staged submission (#1 baseline, #2 refined) + hard timer | timer fires under a simulated hang |
| 6 | Live UI | readable at a glance from two metres away |
| 7 | Shadow + promote lifecycle | a teammate lands a rule without touching the runner |
| 8 | Calibration fit → `ADJUST` rule | closes the loop |

Steps 1–5 are the tournament. 6–8 are the margin and the write-up.

---

## 8. Repo layout

```
c2f/
  core/        models.py  events.py  clock.py  invariants.py
  ingest/      folder_sync.py  keypoll.py  decrypt.py  parse.py
  estimate/    llm_ensemble.py  pricebook.py
  rules/       engine.py  protocol.py  sandbox.py  lifecycle.py
  rules_user/  ← teammates only ever touch this directory
  decide/      quantile.py
  submit/      client.py
  ui/          server.py  static/index.html
  replay/      harness.py
data/          cases/  events/  c2f.sqlite
```

`rules_user/` is deliberately outside the engine's own package: contributors need exactly one
directory, one protocol, and no knowledge of the runner.
