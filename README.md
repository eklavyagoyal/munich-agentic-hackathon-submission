# Claim to Fame

QuantCo hackathon challenge. Rules: [GAME_DESCRIPTION.md](GAME_DESCRIPTION.md).

| Doc | What it covers |
| --- | --- |
| [GAMEPLAN.md](GAMEPLAN.md) | Strategy, price book, calibration loop |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Independent re-derivation of the math, hosting, compute sizing |
| [PIPELINE.md](PIPELINE.md) | Round loop, rule engine, live UI, build order |
| [ASKS.md](ASKS.md) | What we still need from the organizers and from each other |

## Run it

No credentials needed — the pipeline runs end-to-end against a local encrypted
fixture and a mock API.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
PYTHONPATH=. .venv/bin/python tools/make_fixture.py
PYTHONPATH=. .venv/bin/python tools/run_demo.py --activate
PYTHONPATH=. .venv/bin/python -m pytest tests/ -q
```

`pdftotext` is required for invoice parsing (`brew install poppler`).

## Add a rule

Drop a file in `rules_user/`. That is the entire contributor surface — you do
not need to touch the runner.

```python
from c2f.core.models import Context, Stage, Verdict
from c2f.rules.protocol import BaseRule

class MyRule(BaseRule):
    name, stage, priority, author = "my_rule", Stage.ADJUST, 0, "you"

    def apply(self, ctx: Context) -> Verdict | None:
        if "laminate" not in ctx.item.description.lower():
            return None                 # abstain — the normal case
        return Verdict(scale=0.95, note="flooring runs ~5% under book")

RULES = [MyRule()]
```

Four stages: `COVERAGE` (is `t=0`?) · `PRIOR` (supply a belief) · `ADJUST`
(multiply) · `GUARD` (clamp / veto). `ADJUST` and `GUARD` are commutative, so
your rule cannot conflict with someone else's by ordering.

**New rules load as `SHADOW`**: computed, traced and shown, but never applied
until someone promotes them in `rules_state.json`. A rule that raises, hangs or
returns nonsense is disabled for the round — it can make our numbers worse, it
cannot cost us a submission.

## Estimating `t`

Everything reduces to one problem. A fair charge (`a ≤ t`) is paid by every
opponent regardless of their `b`, and `b = t` is optimal pointwise — so there is
no opponent-modelling component to this game, only estimation. Three estimators
feed the `PRIOR` stage, in ascending order of what they can see:

| estimator | sees | when it speaks |
| --- | --- | --- |
| `pricebook_prior` | description, qty, unit | a keyword rate matches, units compatible |
| `llm_prior` | + policy, damage scope, photos, whole invoice | a model key is configured |
| `calibration_bias` | + what past rounds proved about `t` | after the first outcomes land |

`llm_prior` is the only one that can judge **relatedness** — "46 m² of repainting"
is a fair rate and a fraudulent line when the damage is one 18 m² room. It runs off
the hot path: all items and all ensemble samples are fetched concurrently before
the engine loop and handed in via `Context.prefetch`, so the rules stay pure and
wall clock is one call rather than N. With no key it abstains and the price book
takes over — degraded, never zero.

## Calibration

We never observe `t`, only interval-censored bounds, and **only from rejections** —
acceptance proves nothing. `c2f/calibrate.py` fits those bounds to a global
multiplicative correction, then per-trade once a trade has enough of them.

```bash
python -m c2f.calibrate data/events/*.jsonl --outcomes outcomes.jsonl
```

Watch for "no upper bounds at all": never being caught overcharging is a warning,
not a win. It means we are probably leaving half the money on the table, and the
standings cannot show it.

## Status

Build order steps 1–4 done: round trip, event stream, rule engine + sandbox, and
the LLM ensemble as `PRIOR`/`COVERAGE`. Calibration fitting is in and wired to an
`ADJUST` rule; its transaction adapter is the one piece still guessed.

**Blocked:** no team API key, folder link, or `API_HANDBOOK.md` yet — see
[ASKS.md](ASKS.md). `LiveApi` in `c2f/submit/client.py` is the seam; PIPELINE.md
§9 lists what to look up first. No model key either, so the LLM prior has never
run against a live model — the price-book path is what has actually been exercised.
