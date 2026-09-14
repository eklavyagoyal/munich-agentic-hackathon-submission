# Oasis Tournament Observatory

A local-only, read-only dashboard for the Claim-to-Fame tournament. It reads the
harvester database through SQLite's read-only URI mode, tails the append-only event
log, obtains threshold brackets only by running `tools/thresholds.py --jsonl`, and
decrypts case documents only into `viz/runtime/`.

No frontend dependency install or build step is required.

## Analytical surfaces

- Animated 17-team cumulative race, rank-pressure heatmap, phase ledger, and shock markers.
- Shock-adjusted standings under median pace, within-team P10/P90 winsorisation,
  removal of each team's three best rounds, and removal of its three worst rounds.
- A seeded finish-line simulator that resamples complete seventeen-team round vectors
  through game 100, preserving contemporaneous cross-team shocks. It exposes Oasis's
  P10/P25/P50/P75/P90 score cone, all-rank probability distribution, rival-by-rival
  finish odds, target-specific per-round edge requirements, Monte Carlo margin, and
  every simulation denominator. A strictly temporal one-step walk-forward audit reports
  interval coverage, median error, rank-event Brier score, and its constant-rate baseline.
- A paired Rival Gap Studio that compares Oasis with any team on exactly the same played
  games. Its bridge proves the score identity as issuer-income edge plus reviewer-cost
  edge; a round-gap tape, income×cost quadrant, decision-denominated efficiency ladder,
  absolute-gap concentration, leave-one-round-out stress, and deterministic whole-game
  bootstrap expose whether the observed gap is broad or dominated by shocks. Every
  round links back to its game anatomy, and the claim-free receipt labels the result as
  payoff accounting rather than model causality.
- Executive briefing tape, anomaly radar, global command palette, and local identifier-only watchlist.
- Per-game settlement waterfall, euro-weighted payoff matrix, searchable evidence ledger,
  and side-by-side game fingerprints.
- A sanitized round flight recorder showing ingestion, reasoning, two-tier submission,
  recorded boundary deltas, submission-call latency, 52-second tier-two headroom, and
  explicit coverage when historical operational events were never logged.
- A no-hidden-failures operations command deck that distinguishes tournament progress
  from the local recorder horizon, degrades explicitly on played-game or wall-clock
  staleness, and audits ten-stage coverage for every played or recorded game. Separate
  tier-one circles and tier-two squares expose the 2-second observed target and
  52-second hard wall with exact denominators; per-stage P10/median/P90 envelopes retain
  their own timestamp coverage. Missing local boundaries remain unknown rather than
  becoming invented failures, and a claim-free receipt captures the full evidence
  boundary for handoff.
- An animated round replay theatre that merges allow-listed pipeline milestones with
  every timestamped belief, active/SHADOW rule firing, and item decision. Its scrubber,
  speed controls, per-item state board, exact boundary receipt, keyboard stepping, and
  accessible ledger reconstruct only what existed at or before the selected sequence.
- Per-item capital-flow tomography: observed Oasis issuer settlement versus observed
  reviewer settlement, net contribution, gross-flow concentration, hidden-fraud counts,
  four sorting lenses, and a complete accessible ledger.
- Per-item belief/rule receipt, all counterparties, threshold geometry, shadow decisions,
  and an evidence-bounded client-only counterfactual laboratory.
- A selected-item peer-forensics workspace with three explicit retrospective cohort
  contracts, strictly lower-game summaries, separately ghosted same-game/future
  hindsight, per-metric empirical midranks and quantile envelopes, a focusable temporal
  tape, and robust numeric analogue geometry. Every metric keeps its own non-missing
  denominator; peers never use text similarity and are never called semantic matches,
  substitutes, predictions, or valuation recommendations.
- Linked PDF/policy/photo reader with source-page navigation and local lexical highlighting.
- Economics, decision stream, error ridgelines, value regimes, overcharge response,
  Pareto concentration, opponent behaviour, source performance, and integrity matrix.
- A strictly temporal stability and drift observatory across six independently
  denominated metrics. Every game is scored only against earlier observations using a
  robust median and the larger of MAD- and IQR-based dispersion; favourable, adverse,
  zero-variance, warm-up, and missing states remain distinct. A separate bounded
  Jensen-Shannon series measures belief-source composition change against aggregated
  prior item counts. Both views deep-link to games, provide accessible ledgers, and
  export a claim-free reproducibility receipt without calling a change point causal.
- A bounded belief-calibration studio grounded in the production `Belief` contract:
  lognormal gross-EUR median and log-space sigma. It compares 50%–99% central
  intervals with sanctioned floors and finite ceilings while preserving partial
  identification: forced misses are lower bounds, non-misses are only compatible
  coverage upper bounds, and guaranteed capture uses the two-sided denominator.
  Source, value-regime, logged-game, and per-item geometry views expose sharpness and
  directional failures without converting proof brackets into exact labels; all
  records deep-link and export a claim-free retrospective receipt.
- A two-role item cartography that joins the provable issuer foregone-income lower
  bound to observed reject-fair and accept-fraud reviewer settlement on the same
  game/item identifiers. Its joint log-EUR atlas, temporal tape, failure-mode matrix,
  heavy-tail scanner, value-regime burden bars, source × value routing lattice,
  complete accessible ledgers, filters, and claim-free receipt all reconcile to one
  fixed item universe. Routing cells expose both focus value per item and total scale
  so a rare severe cell cannot be confused with a common mild one. The additive “evidence load” is labelled as a
  triage index rather than causal avoidable loss, while every rejected-fraud attempted
  amount stays unpriced and visible only as a group count.
- A claim-free 17×17 tournament market-microstructure ledger covering every ordered
  issuer→reviewer edge. Four matrix lenses expose observed reviewer settlement,
  acceptance rate, asymmetric wrong-decision cost, and the non-zero-sum fair-rejection
  penalty wedge. A dense, array-encoded temporal cube retains all 272 directed edges for
  every played game. Its scrubber animates either exact single-round frames or cumulative
  through-game accounting, with a selected-team score cursor and a focused-pair pulse.
  A selected-team inspector reconciles issued income, reviewer cost, net, outcome anatomy,
  all sixteen bilateral relationships, every edge-frame rollup, and every game to official
  score. Hidden rejected-fraud sizes remain explicitly absent and all flow views are
  labelled observed lower-bound accounting rather than causal exploitation.
- A game × item evidence-loss atlas with independently denominated lenses for hidden or
  unresolved field charges, open ceilings, missing beliefs/decisions/rule traces/replay,
  and unavailable local documents. Every gap links to the underlying item receipt.
- A temporal income-versus-reviewer-cost phase space with log-spaced actual-EUR axes,
  break-even geometry, item-volume encoding, deep-linked cohort filters, and the exact
  observed Pareto frontier under “maximise income, minimise reviewer cost”.
- A global charge-to-floor landscape with evidence filters, a source × value risk
  lattice, an exact four-branch payoff instrument, and sixteen longitudinal opponent
  dossiers whose review cells reconcile to the underlying decisions.
- A global reviewer decision laboratory backed by a separate claim-free materialized
  ledger. It audits one Oasis review × opponent charge group at a time, supports four
  independent sanctioned-floor-bucket shifts to `b`, reprices only exact fair switches
  and fraud lower-bound crossings whose candidate settlement is provable, and keeps
  potentially exposed hidden fraud groups unpriced. The surface includes an observed
  four-cell matrix, paired-cost waterfall, decision-margin geometry, temporal impact,
  isolated bucket sensitivity curves, a clickable breakpoint ledger, accessible tables,
  and a denominator-complete audit receipt.
- A two-sided cohort comparison studio for before/now or evidence-slice research. Each
  side independently filters temporal games, belief source, sanctioned-floor bucket,
  and proven state; reports fixed-denominator valuation SCORE plus asymmetric reviewer
  economics; exposes game/item overlap and tail records; and runs a reproducible
  whole-game cluster bootstrap. Identical game sets are paired, different game sets are
  sampled independently, and every result is labelled retrospective and non-causal.
- A rule and SHADOW observatory covering every logged firing. It shows only exact
  logged `from`/`to` counterfactual pairs, separately reports before/candidate scores
  on one fixed proven-floor denominator, maps evidence-state transitions, and exposes
  unpriced opposing charge groups whenever an acceptance limit rises.
- An item-deduplicated SHADOW portfolio composer that retains the latest logged
  candidate per rule/game/item, contrasts before/full/routed SCORE on one denominator,
  applies only observable source/direction/peer/b-movement/stability gates, maps
  pairwise rule opposition, sweeps all safety gates, audits routed delta game by game,
  and exposes every routed or blocked item in a falsification ledger. A claim-free,
  caveated JSON handoff receipt can be copied locally. A promotion firewall keeps
  strict temporal testing, ≥0.90 expensive-item precision, deadline latency, provider
  fallback, and hidden-b exposure visibly unresolved or blocked. The whole surface is
  explicitly retrospective evidence—not tournament impact or a temporal backtest.
- Append-only local submission tape, tournament countdown, explicit recorder-freshness
  state, and separate liveness/readiness semantics.

The current game, item, comparison game, strategy filters, selected opponent, market
team, matrix lens, replay mode and replay game, paired rival and matched-game window,
belief-calibration interval/source/value/window, selected-item peer cohort/metric,
two-role cartography filters/focus, cohort
definitions and bootstrap contract, rule
variant, portfolio rule and observable routing gates, robustness lens, and capital-flow
sort, temporal drift specification, and compact finish-simulation specification are encoded as non-claim analytical
URL parameters. The link button copies that
local state without including descriptions, policy text, damage text, or media paths.

Press `Command/Ctrl+K` to search every materialised game/item/team or run a navigation
command. Press `E` for the in-app evidence dictionary covering formulas, denominators,
bounds, observability states, operational timing, and comparative metrics. Press `?`
for the complete keyboard map.

## Start

From the repository root:

```bash
.venv/bin/python -m viz.server --port 8090
```

Then open <http://127.0.0.1:8090>. The server refuses non-loopback binding unless
`--allow-non-loopback` is passed explicitly.

## Safety model

- The production SQLite file is opened with `mode=ro` and `PRAGMA query_only=ON`.
- The leaderboard is read only from the existing local dashboard on port 8080, with
  a bounded timeout, a slow refresh interval, and stale-cache degraded mode.
- Thresholds are produced by the sanctioned tool against a consistent local snapshot
  created from a read-only production connection.
- Document decryption happens in an isolated subprocess whose working directory is
  `viz/runtime/`; its environment contains no API credentials.
- APIs never accept filesystem paths. Media is served through manifest-generated,
  allow-listed tokens with traversal checks and inline-only content disposition.
- Liveness and readiness are separate. Missing live leaderboard data is an explicit
  degraded mode; missing database or threshold data fails readiness.
- Operational telemetry is a non-critical dependency with five explicit states:
  current, behind played rounds, stale by clock, timestamp unavailable, or unavailable.
  A stale recorder makes the application degraded without falsely making historical
  analytics unreadable. Its status never represents daemon health.
- Document availability is materialised from key/archive presence without exposing key
  values. Missing keys are shown before any worker is launched and enter explicit,
  non-critical degraded mode while transaction analytics remain available.
- The watchlist persists only `game:item` identifiers in browser local storage. Claim
  descriptions are never written there.
- Flight-recorder payloads are allow-listed: event type, sequence, normalized UTC time,
  bounded counts/durations/tier/status, and Boolean outcomes only. Alert messages, rule
  notes, case identifiers, decision traces, and claim fields never enter the payload.
- Operations payloads use a separate exact field contract. Both materialization checks
  and the browser reconcile played/recorded/missing games, latest horizons, freshness
  state, stage observation counts, coverage, tier deadline denominators, failure totals,
  and alert-severity counts. Extra row fields, negative timing, duplicate stages,
  impossible status labels, or denominator drift fail closed into a visible telemetry
  contract error.
- Replay payloads use a second strict allow-list: item identifier, sequence/time,
  belief median/sigma/source, rule name/SHADOW flag/from-to pair, and final a/b/coverage.
  Materialization verifies ordering, known-item membership, field allow-listing, counts,
  and reconciliation of the final replay state with the item API.
- Reviewer-laboratory payloads are description-free and field-allow-listed. Their cell,
  matrix, cost, limit-audit, and conservative-eligibility partitions are checked during
  `--check`; hidden fraud never receives a reconstructed charge or counterfactual euro cost.
- Market payloads contain only public team identifiers and aggregate numeric settlement
  evidence. The browser rejects malformed identities, duplicate frames, incomplete edge
  ledgers, invalid decision partitions, and decision totals that do not reconcile. `--check`
  enforces complete all-history edges and per-game frames, exact field allow-lists,
  decision partitions, edge/frame/team/timeline money reconciliation, and €0.01
  official-score agreement.
- Generic event `ms` fields are labelled as reported values, not stage durations.
  Submission-call `ms` is separately labelled latency; cross-event timing comes only
  from normalized logged timestamps.
- Temporal-monitoring baselines are computed in the browser from materialized,
  claim-free aggregates. Contract tests mutate future observations and prove earlier
  limits do not change, exercise zero-dispersion handling, and bound Jensen-Shannon
  divergence to `[0,1]`. Missing values never enter another game’s baseline.
- Belief-calibration intervals are computed in the browser from the description-free
  item index using the verified production lognormal formula. Contract tests prove
  that floor-only evidence can never become a high-side miss or guaranteed capture,
  widening is evaluated on a fixed item denominator, and overlap stays unresolved.
- Two-role cartography joins only description-free game/item identifiers. Contract
  tests reconcile every selected item to its game rollup and issuer-state × reviewer-
  direction taxonomy, preserve exact reject-fair/accept-fraud observed costs, and prove
  that value-regime and source × value partitions retain the same item universe and
  hidden rejected fraud contributes counts but no fabricated euro amount. Synthetic
  contracts cover empty-focus, sparse, game-concentrated, limited-recurrence, and
  repeated-evidence routing states.
- Item peer forensics runs entirely over description-free global item and reviewer
  evidence. Contract tests mutate future peer economics and decision geometry and prove
  that strictly prior summaries and prior-only analogue scaling remain byte-identical
  while hindsight outputs change, exclude the selected item from every peer denominator,
  and require at least two common numeric dimensions before exposing an analogue.

## Checks

```bash
.venv/bin/python -m viz.server --check
.venv/bin/python -m unittest discover -s viz/tests -v
node --check viz/static/app.js
node viz/check_peer_snapshot.js
```

Tests use generated synthetic records only. No claim fixture belongs in this tree.
