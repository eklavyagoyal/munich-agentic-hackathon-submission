# What runs where, and what crosses between us

**Written:** 22 Aug 2026, 15:41 UTC. Description only — no code changed. Correct
me where I have guessed; I can see Eklavya's machine only through what it pushes.

---

## The one-line version

**Eklavya's machine plays the tournament and publishes what happened. Our machine
reads that, opens the cases, and writes findings back.** Nothing we run can
submit, and nothing we run writes to a shared branch except `analysis/`.

---

## Two machines

### Eklavya's — the only one that touches the tournament

| process | what it does | where the output goes |
| --- | --- | --- |
| `tools/serve.py --activate` | plays every round: decrypt → parse → price → `PUT` | the tournament API |
| `keywatch.py` | fetches each decryption key at `start_time + 70s` | `keys` branch |
| `tools/autopilot.py` | tails the runner's event log, waits for `round.played`, then harvests and publishes | drives the two below |
| `tools/harvest.py` | pulls the public leaderboard feed | `data/c2f.sqlite` |
| `tools/publish.py` | writes per-game JSON by git plumbing | `inputs` + `results` branches |

`keywatch.py` is not in the repo, so that name comes from the `keys` branch
README rather than from reading it.

**He is the single writer, and that is deliberate.** `PUT` is last-write-wins, so
a second machine submitting does not add redundancy — it would replace his answer
with its own.

### Ours — reads everything, plays nothing

| process | interval | what it does |
| --- | --- | --- |
| `tools/cases.py --watch` | 1 min | fetch `keys`+`inputs`, take new keys, decrypt new cases, attach our bid |
| `tools/sync.py --watch` | 5 min | pull `keys`+`inputs`, rebase our branch onto `main` |
| `tools/harvest.py --watch` | 5 min | Eklavya's harvester, run locally: results into SQLite + the valuation dataset |
| `tools/dashboard.py` | — | local case API on `127.0.0.1:8080` |
| `next dev` | — | the case analysis UI on `:3000` |

`serve.py` has never run here. We were never armed.

Two independent locks make that true rather than merely intended:
`C2F_READONLY=1` in our `.env` makes `LiveApi.submit` raise, and `backtest.py`
hands the runner a `MockApi` that has no HTTP client at all.

---

## What crosses between us

```
        Eklavya                     shared branches                 us
  ──────────────────────────────────────────────────────────────────────────
  serve.py plays ──────────►  keys/game-NNN.json      ──────────►  cases.py
  publish.py ──────────────►  inputs/game-NNN.json    ──────────►  cases.py
  publish.py ──────────────►  results/game-NNN.json   ──────────►  (reference)
  owns the code ───────────►  main                    ──────────►  sync.py
                              main:analysis/          ◄──────────  us, findings
                              analysis-tooling        ◄──────────  us, our tools
  ──────────────────────────────────────────────────────────────────────────
  the public leaderboard feed  ─────────────────────►  harvest.py (read-only)
```

**In, to us:** `keys`, `inputs`, `results`, `main`, and the public leaderboard.

**Out, from us:** `analysis/` on `main`, and our own `analysis-tooling` branch.
That is the entire list.

**Out of nobody:** everything under `data/` — decrypted policies, invoices,
photos, the decryption keys, the SQLite database. `data/` is gitignored and the
case API binds to `127.0.0.1` only. Checked-in claim data is a ranking penalty
(Discord, Hailong@QuantCo, 14:35), and these files are that data in plaintext.

---

## Where things live on our disk

```
data/                     gitignored in full — never leaves this machine
  c2f.sqlite              games, scores, transactions
  keys.json               decryption keys, pulled from the keys branch
  harvest/keys.json       -> symlink to ../keys.json, so Eklavya's harvester
                             finds them without a TEAM_API_KEY
  harvest/line_items.jsonl the valuation dataset his harvester builds
  open/game-NNN/          decrypted case: policy, description, invoice PDF,
                          invoices.pdf.txt, photo, and submission.json (our bid)
  backtest/               replay output, for --diff
```

---

## Two things I noticed while writing this

**1. `tools/sync_keys.py` on `main` overlaps our `sync.py` + `cases.py`.** Both
pull `main` and the `keys` branch and decrypt new cases. Ours also attaches our
bid from `inputs` and runs on a one-minute timer; his prints a decrypted-vs-not
summary. Nobody needs two, and whichever goes should go on purpose rather than by
one of us quietly stopping to run it.

**2. `results/README.md` still says the branch is written by `tools/export.py`.**
That was mine, from when this machine was publishing. It is not any more —
`publish.py` writes it now and `export.py` is deleted. The README should say so,
otherwise the next person goes looking for a tool that does not exist.


---

## Corrections from the machine that runs it (Eklavya, 15:43 UTC)

Accurate throughout except one line, and that line matters.

**`serve.py` no longer runs with `--activate`.** It runs bare, and
`rules_user/rules_state.json` governs promotion: 4 rules ACTIVE, 4 SHADOW. The
change was made at 15:02 because `--activate` promotes EVERY loaded rule
unconditionally, including one that appeared since the last restart. That stopped
being hypothetical when an untracked interval-valuation PRIOR at priority 20
turned up in `rules_user/` — restarting to pick up a price-book fix would have put
an unreviewed model in charge of every number we submit. The state file is
gitignored, so it is per-machine, which is correct: promotion is an operational
decision, and a fresh clone defaulting everything to SHADOW is the safe direction.

Anyone restarting the runner: do **not** add `--activate` to make rules fire. If
the startup line says `0 active`, the fix is to write `rules_user/rules_state.json`,
not to pass the flag.

Currently SHADOW and deliberately so: `interval_valuation_prior` (failed its own
pre-registered gates), `unparsed_row_prior`, `llm_prior`, `llm_coverage`. The last
one stays shadow permanently — zeroing an item measured -3,182.79 even when the
item was provably worthless, because roughly half the field pays our over-charge on
it.

**`results/README.md` fixed** — it now names `tools/publish.py`. Thank you, that
would have sent someone hunting for a deleted file.

**On the `sync_keys.py` overlap:** yours does strictly more (attaches the bid, runs
on a timer) and mine only prints a summary, so yours should win. But `cases.py` and
`sync.py` are not on `main`, so deleting `sync_keys.py` today would leave `main`
with nothing at all. Land those two on `main` and I will delete mine in the same
change — one deliberate swap rather than two half-states.

**One thing to add to your "out of nobody" list:** agent session transcripts. They
are checkpointed to the submission repo, so pasting decrypted invoice text into an
agent session publishes it just as surely as committing the file. Eleven verbatim
phrases have already had to be redacted from `analysis/` for this reason, and the
folder README now says so.
