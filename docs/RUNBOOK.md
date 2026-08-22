# Runbook — how a submission actually happens

Everything needed to run this on a different machine with nothing but the team API
key and this file. No claim data, no keys, and no invoice text appears here or should
ever be added to it.

---

## 0. The one rule that matters

**Exactly one machine may submit.** `PUT` is last-write-wins, and the tournament API
has no compare-and-set. A second machine posting its weaker fallback at T+55s does not
add redundancy — it *overwrites* the primary's better answer from T+50s. That is a
silent regression: both machines log a successful round.

On the single submitting machine, nothing special is needed. **On every other machine:**

```bash
echo "C2F_READONLY=1" >> .env
```

`LiveApi.submit` then raises `ReadOnlyMachine` instead of writing, and `serve.py` says
so at startup. Backtesting, analysis, scoring and the dashboard all still work. The
exception is deliberately loud, because a silent no-op looks exactly like a successful
round in the event log.

If you are taking over as the submitting machine, **stop the old one first** and
confirm its process is gone before starting yours.

---

## 1. Prerequisites

| | |
| --- | --- |
| Python | 3.12 (developed on 3.12.7) |
| Team API key | `TEAM_API_KEY`, from the organisers |
| Case archives | the organisers' shared folder, AES-encrypted zips |
| Model key | optional — `OPENAI_KEY` or `ANTHROPIC_API_KEY`; without one the price book still produces numbers |
| Disk | archives plus a SQLite DB; a few hundred MB is plenty |

`7z` is a useful fallback for archive extraction but is not required — `pyzipper`
handles AES zips in-process.

---

## 2. Setup

```bash
git clone <repo> && cd <repo>
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
# or: uv pip install --python .venv/bin/python -r requirements.txt
```

Create `.env` in the repo root:

```
TEAM_API_KEY=<your team key>
OPENAI_KEY=<optional model key>
# C2F_READONLY=1      <-- set this on EVERY machine that is not the submitter
```

`.env` is gitignored. Never commit it, and never paste the key into a commit message,
issue, or agent transcript.

Put the encrypted case archives where the scheduler looks. It auto-discovers a
`cases/` directory; the documented layout from the organisers' starter script is
`case_{game_id:02d}.zip` (so `case_07.zip`), and several other spellings are tolerated.
The archives directory must stay **out of git** — `.gitignore` denies everything inside
it by default. Checked-in claim data is a ranking penalty from the organisers.

Verify before going live:

```bash
.venv/bin/python -m pytest -q                            # expect 216 passed, ~2s
PYTHONPATH=. .venv/bin/python tools/serve.py --plan       # schedule, plays nothing
```

`--plan` prints the game count, the cadence, the measured clock skew against the
server, and the next start time. It submits nothing, so it is always safe to run.

---

## 3. Run it

```bash
cd <repo>
nohup env PYTHONPATH=. .venv/bin/python -u tools/serve.py > logs/daemon.log 2>&1 < /dev/null &
disown
```

**Do not pass `--activate`.** Rule promotion is governed by
`rules_user/rules_state.json`, not by a command-line flag. At startup the log states
which rules loaded and in which mode; confirm it matches what you expect:

```
rules      : calibration_bias[active], policy_exclusion[active], pricebook_prior[active],
             sanity_clamp[active], worthless_accept_guard[active], ...[shadow]
           : 5 active / 4 shadow, per rules_user/rules_state.json
llm backend: openai (request retention ON)
running. ctrl-c to stop.
```

A rule in `shadow` is evaluated and logged but **cannot change what is submitted**.
That is the safe default: a rule absent from `rules_state.json` loads as shadow.

Restarting is safe *between* rounds only — see §6.

---

## 4. What happens in one round

The scheduler wakes 3s before the published start time so the process is warm and
polling the instant the key exists. Fetching a key before release is off limits.

| T | step | notes |
| --- | --- | --- |
| −3s | wake, begin polling for the key | `GET /api/games/{id}/key` |
| ~0s | key released, archive decrypted | AES zip, password = the key |
| ~0s | parse the invoice | deterministic regex; PDFs all carry text layers, so no OCR |
| ~1s | price every line item from the price book | pure lookup, no network |
| **15s** | **submission #1 (tier 1)** | `baseline_at_s` — a complete, defensible answer |
| 15–52s | model ensemble prices what the price book could not cover | 3 samples per item |
| **52s** | **submission #2 (tier 2)** | `hard_deadline_s` — fires regardless |

Two properties make this safe:

- **Tier 1 always stands.** If tier 2 fails for any reason — provider error, timeout,
  invariant violation, every sample abstaining — the tier-1 submission remains the live
  answer. Tier 2 can only improve on it or be discarded.
- **Tier 2 is skipped rather than rushed.** With under `min_tier2_budget_s` (10s)
  remaining it does not start.

Only items the price book cannot cover go to the model, so the per-round call count
varies a lot — 1 item in one round, 19 in another.

### Never submit nothing

The worst outcome is silence: game 1 scored **−8,273.70** because a parse error raised
and nothing was submitted. A fair charge is paid by *every* opponent including the ones
who reject it, so submitting nothing forfeits all income and pays the 1.5× rejection
penalty everywhere. There is an explicit fallback rung that emits a defensible answer
for every line item rather than skipping the round.

Related invariant: a `NaN` reaching the wire is a 422 for the **whole** submission,
after which every line item falls back to the server's 0/0 defaults — reject
everything, pay 1.5a to everyone. Values are therefore clamped finite and nonnegative
at the boundary rather than trusted.

---

## 5. The API contract

Base URL `https://c2f.public.quantco.cloud`, overridable with `C2F_BASE`.

**Auth is `X-API-Key`, not `Authorization: Bearer`.** A Bearer header 401s on every
call.

| method | path | purpose |
| --- | --- | --- |
| `GET` | `/api/games/list` | schedule and game ids |
| `GET` | `/api/games/{game_id}/key` | per-game decryption key, at release time |
| `PUT` | `/api/games/{game_id}/submissions` | submit |

**`PUT`, not `POST`.** POST loses every submission.

The body is a **bare array** keyed on `index` — not an envelope, and not `idx`:

```json
[
  {"index": 1, "charge_price": 120.00, "acceptance_limit": 240.00},
  {"index": 2, "charge_price": 45.50,  "acceptance_limit": 91.00}
]
```

An `{case_id, items: [...]}` envelope is rejected with 422.

`index` is our 1..N ordinal, contiguous by construction. The server ignores an index it
does not know, so a spare index is harmless — but a **missing** row costs 1.5a on every
fair charge against it, which is why the parser fills gaps rather than dropping rows.

The `PUT` response echoes back the stored rows, so verification comes free with the
write. There is no read-back `GET`, and no window in which we believe a submission
landed that did not.

---

## 6. Restarting safely

1. `date -u` and `tools/serve.py --plan` — get the next start time.
2. **Never restart within 120s either side of a round start.** Restart mid-gap only;
   the gap is ~12.6 minutes, so there is plenty of room.
3. After restarting, confirm the new process start time is **later** than the mtime of
   whatever you changed — otherwise it is still running the old code:
   ```bash
   ps -o lstart=,pid= -p $(pgrep -f tools/serve.py | head -1)
   stat -f "%Sm  %N" <the file you changed>
   ```
4. Confirm the rule counts in the log.

Preserve the old log rather than truncating it — it holds the round history:

```bash
mv logs/daemon.log "logs/daemon.log.until-$(date -u +%H%M%S)"
```

**Do not chain a restart behind a commit in one shell command.** Commits here can take
minutes because of repo hooks; the commit itself lands quickly and the hook is what
hangs, so verify with `git log` rather than the exit code — and never let a restart sit
behind one, which once nearly left the daemon down through a round.

---

## 7. Verifying it worked

```bash
PYTHONPATH=. .venv/bin/python tools/score.py --actual    # realised score per game
```

`--actual` reproduces the realised scores to the cent, which is what makes the scorer
trustworthy — use it rather than rebuilding a scorer. `charge` and `limit` **sums are
not euro impact**: a higher charge earns 16× when fair and nothing when not.

Per-round confirmation, straight from the event log:

```bash
grep '"type":"submission.sent"' data/events/tournament.jsonl | tail -4
grep '"level":"error"' data/events/tournament.jsonl
```

Every round must show a `submission.sent`. A round without one is the failure that
matters most; investigate immediately.

The `unpriced` column in `score.py` counts rejected-fraud charges whose amounts are
invisible. **Any change that raises the acceptance limit is an upper bound, not a
result** — those rows would start being paid at a size nobody can observe.

---

## 8. Failure modes seen in practice

| symptom | cause | response |
| --- | --- | --- |
| round with no `submission.sent` | parse raised, or the process was down | the single worst outcome; check the daemon first, then the parser |
| 401 on every call | `Authorization: Bearer` instead of `X-API-Key` | fix the header |
| submissions silently lost | `POST` instead of `PUT` | use `PUT` |
| 422 on the whole submission | envelope body, `idx` instead of `index`, or a NaN | send a bare array, clamp values |
| a line item missing from the payload | parser dropped a row | costs 1.5a per fair charge; gaps are filled, not dropped |
| two machines both "succeeding" | second writer overwriting the first | `C2F_READONLY=1` everywhere but one |
| tier 2 never fires | under 10s of budget left, or the model abstained | benign — tier 1 stands |
| model calls invisible in the provider dashboard | request retention is opt-in and defaults off | `C2F_STORE_LOGS`, see §9 |

---

## 9. Environment reference

| variable | effect |
| --- | --- |
| `TEAM_API_KEY` | **required.** Sent as `X-API-Key`. |
| `C2F_READONLY` | `1` makes `submit` raise instead of writing. Set on every non-submitting machine. |
| `C2F_BASE` | override the API base URL. |
| `OPENAI_KEY` / `OPENAI_API_KEY` | model key. Without one the price book still produces numbers. |
| `ANTHROPIC_API_KEY` | alternative backend. |
| `C2F_BACKEND` | force `openai` \| `anthropic` \| `none`. `none` disables model calls entirely. |
| `C2F_MODEL` | override the model id. |
| `C2F_STORE_LOGS` | `0`/`false`/`no`/`off`/blank stops asking the provider to retain requests. Default on. With it off the request is byte-identical to not setting it at all. |

Note on `C2F_BACKEND=none`: `tools/backtest.py` defaults to it, so a backtest of
anything model-dependent needs `--allow-model-network` or it is a silent no-op that
"passes" in seconds with the model never invoked. Always pass `--shadow` or `--promote`
as well.

Note on `C2F_STORE_LOGS`: retention means prompts **persist** in a browsable
third-party dashboard, and item prompts carry invoice line text. That text is already
transmitted to obtain a price; retention keeps a copy. Turn it off if that is not
wanted.

---

## 10. Do not

- **Do not submit from a second machine.** §0.
- **Do not commit claim data** — invoice PDFs, policies, damage descriptions, or
  verbatim line-item text, in files *or* commit messages. The organisers apply ranking
  penalties. Refer to items as "game 12 item 4".
- **Do not run `tools/play_once.py` against a scheduled game.** The daemon is the
  single writer.
- **Do not submit by hand.**
- **Do not pass `--activate`.** Promotion lives in `rules_user/rules_state.json`.
- **Do not promote a rule on an unmeasured hunch.** New rules land shadow; promote only
  after `tools/score.py` shows a gain across *all* played games, not a subset.

---

## 11. Files worth knowing

| path | what it is |
| --- | --- |
| `tools/serve.py` | the daemon. `--plan` inspects the schedule safely. |
| `tools/score.py` | euro scoring. `--actual` self-validates against realised scores. |
| `tools/thresholds.py` | the only sanctioned source of proven value brackets. Hand-rolled SQL has inverted the answer twice. |
| `tools/backtest.py` | replay. Needs `--shadow`/`--promote`, plus `--allow-model-network` for model paths. |
| `c2f/submit/client.py` | the API seam. `LiveApi` holds the contract in §5. |
| `c2f/runner.py` | the round: timings in `RoundConfig`, and the never-submit-nothing fallback. |
| `c2f/ingest/parse.py` | invoice parsing. The most load-bearing file — game 1 was lost here. |
| `rules_user/rules_state.json` | which rules are active vs shadow. Gitignored, so it is per-machine. |
| `data/events/tournament.jsonl` | append-only event log. Source of truth for what happened. |
| `docs/MODEL_BRIEF.md` | the payoff matrix, and why undercharging is the expensive mistake. |
