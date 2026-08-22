# Leaderboard API

<https://c2f.public.quantco.cloud/leaderboard/>

The public leaderboard is an Alpine.js page that reads a JSON API on the same origin.
These are the endpoints **the page itself calls** — this is the site's own public data
feed, the one the rules describe when they say *"all results are public afterwards"*.
Nothing here was discovered by scanning; it is read straight off the page's own source.

> Fair play: `GAME_DESCRIPTION.md` forbids probing the infrastructure. Polling these at
> the same sort of rate a browser tab would is normal use. Do not hammer them, and do
> not go looking for undocumented routes.

## Endpoints

| Endpoint | Params | Notes |
| --- | --- | --- |
| `GET /leaderboard/api/games` | `page`, `page_size`, `completed_only` | The full schedule. Works **before** the tournament starts. |
| `GET /leaderboard/api/matrix` | `page`, `game_limit` | Standings matrix. |
| `GET /leaderboard/api/performance` | `team` | 404 `"No completed rounds for that team"` until we have played. |
| `GET /leaderboard/api/matchup` | `team` | Head-to-head. |
| `GET /leaderboard/api/transactions` | `game_id`, `team` (**both required**) | Per-transaction results. |

Backend is FastAPI: a missing param returns `422` with a `detail` array naming it.
Paged responses share one envelope: `{items, page, page_size, total, total_pages}`.

## The schedule is public, exact, and complete

`GET /leaderboard/api/games?page_size=1000` already returns **all 100 games**, each as
`{id, start_time, status}`, with `status` currently `scheduled` for every one.

```
games        100
first        2026-08-22T13:00:00Z
last         2026-08-23T09:50:00Z
span         20.833 h
interval     757.576 s  =  12 min 37.6 s   (constant)
```

Two consequences:

1. **We never guess when a round starts.** ARCHITECTURE.md §3 worried about clock drift
   against a 60-second window. That problem is solved: poll this endpoint, take
   `start_time` for the next `scheduled` game, and derive the local offset from the
   HTTP `Date` header. No hardcoded cadence, no drift.
2. **The tournament runs overnight.** 13:00 today to 09:50 tomorrow, and **52 of the
   100 games fall between 21:00 and 08:00 UTC**. The always-on runner in
   ARCHITECTURE.md §3 stops being insurance and becomes a requirement: more than half
   the tournament plays itself while nobody is at a keyboard, and "Consistency: the
   more rounds it plays cleanly, the better" is a judged criterion.

Measured against the live endpoint on 2026-08-22, our own clock was **1.27 s ahead of
the server**. That is 2% of the submission window given away for free, before any
network latency. Take the offset from the `Date` header, every round.

## `transactions` is the calibration and opponent data

ARCHITECTURE.md §8 asks for exactly this: we never observe the secret threshold `t`,
only interval-censored bounds, and **only from rejections** — acceptance teaches us
nothing. `transactions?game_id=&team=` is where those bounds come from, and it is also
the only way to measure the opponent field's acceptance behaviour, which sets how far
above our median we can afford to charge.

Its response shape is unknown until the first game completes. Confirm the field names
before wiring the calibration fit to it.

## Open

- Whether `transactions` exposes other teams' rows or only our own. If only ours, the
  opponent model is limited to what our own charges reveal.
- Whether `status` distinguishes `running` from `completed`, which is what a
  round-scheduler wants to trigger on.
