# Claim to Fame

QuantCo hackathon challenge. Rules: [GAME_DESCRIPTION.md](GAME_DESCRIPTION.md).

| Doc | What it covers |
| --- | --- |
| [GAMEPLAN.md](GAMEPLAN.md) | Strategy, price book, calibration loop |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Independent re-derivation of the math, hosting, compute sizing |
| [PIPELINE.md](PIPELINE.md) | Round loop, rule engine, live UI, build order |

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

## Status

Build order steps 1–3 done (round trip, event stream, rule engine + sandbox).
Step 4 is the LLM ensemble as the default `PRIOR` rule.

**Blocked:** no team API key, folder link, or `API_HANDBOOK.md` yet. `LiveApi`
in `c2f/submit/client.py` is the seam; see PIPELINE.md §9 for what to look up
first.
