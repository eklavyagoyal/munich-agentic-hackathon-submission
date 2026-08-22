# How we work on this repo during the tournament

## One person changes the code

**Eklavya owns `c2f/`, `tools/`, `rules_user/` and `tests/`.** Everyone else
writes findings into [`analysis/`](analysis/) and does not touch the code.

This is not about trust. It is about the clock. A game starts every 12 minutes
and 38 seconds, the runner is live on one machine, and `main` is what it runs.
A change that looks harmless can cost a round — game 1 scored **−8273.70** for
eleven of seventeen teams because one invoice row printed its quantity as an
en-dash and the parser raised instead of coping. Nobody predicted that from
reading the code. The fewer hands on the hot path while it is running, the fewer
ways there are to find out.

So the split is:

| | who | where |
| --- | --- | --- |
| Change behaviour | Eklavya | `c2f/`, `tools/`, `rules_user/`, `tests/` |
| Everyone else | anyone | `analysis/` only |

If you have found something that should change the code, **write it up in
`analysis/` with the evidence**. Eklavya reads that folder and implements what
holds up. A finding with numbers behind it is more useful than a patch nobody
has time to review mid-round.

## What counts as a finding

Something that would change what we bid, or what we accept. The bar is that a
reader can check it without redoing your work.

Good: *"On game 2 line item 1 we charged 43.97; AsianSuperNerds charged 310.00
and Codacabana 286.99, and both collected. Our estimate of `t` is low by roughly
a factor of 7 on flooring work. Query and table attached."*

Not useful: *"I think our prices are too low."*

## Why this matters more than it looks

The scoring is asymmetric and both halves run off the same belief about `t`
(see [docs/MODEL_BRIEF.md](docs/MODEL_BRIEF.md)):

- **As issuer**, a fair charge (`a ≤ t`) is paid by *every* opponent — including
  the ones who reject it, since rejecting still owes us `a`. Charge above `t` and
  we earn nothing. Undercharging is a total, silent loss that never surfaces as
  an error anywhere.
- **As reviewer**, accepting costs `a`; wrongly rejecting costs `1.5a`. So an
  estimate that is too low makes us undercharge *and* over-reject at the same
  time.

That is why an analysis that pins down a real price is worth more than most code
changes. It fixes both sides at once.

## Do not submit from a second machine

`PUT` is last-write-wins. A backup posting its fallback at T+55s does not add
redundancy — it replaces the primary's better answer from T+50s. Exactly one
machine runs `tools/serve.py --activate`.

On every other machine, put this in `.env`:

```
C2F_READONLY=1
```

`LiveApi.submit` then raises instead of putting, and `serve.py` says so at
startup. Watching, backtesting and analysis all still work.

## Never commit case data

The organisers' folder stays out of git — `.gitignore` denies everything inside
it by default, with the five docs as named exceptions. Discord (14:35,
Hailong@QuantCo): checked-in claim data is a ranking penalty.
