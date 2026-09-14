# ui/ — the live round dashboard

What we watched during a round. Next.js, reads everything from `tools/dashboard.py`
on `:8080` and nothing else.

```bash
npm install          # once per machine; node_modules is not in the repo
npm run dev          # http://localhost:3000
```

It leads with the only number that decides this game — **money in our account** — then
the standings we are trying to beat, then the round detail: timeline in milliseconds,
what came out of the decryption and in what format, every line item with the module that
set its bid, and submission latency.

**It lives on :3000, not :8080.** Port 8080 answers with a plain no-build fallback page
that keeps working if node dies at 03:00 — if you are looking at that, you are on the
wrong port.

**The UI never talks to the leaderboard.** Every upstream call goes through the Python
process, which fetches once per 90 seconds and shares that with every open tab, and backs
off five minutes on an error. Ten people watching on ten laptops cost the organisers one
request per 90s, not ten, and no retry storm can start in a browser. Secrets are scrubbed
server-side, so a decryption key cannot end up on a projector.

Two processes on purpose: `tools/dashboard.py` tails `data/events/tournament.jsonl` and
never imports the runner, so nothing a browser does can reach the process that has 60
seconds to submit.

`--team` on the dashboard is what unlocks the opponent panels — `performance` and
`matchup` are per-team endpoints and 404 until we are registered and have played a round.

For the post-hoc analysis surface — the 100-round race, capital-flow tomography, the
17×17 market ledger — see [`viz/`](../viz/README.md) instead. This one is for live play.
