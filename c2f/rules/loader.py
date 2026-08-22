"""Rule discovery and lifecycle (PIPELINE.md §4.4).

    drop file in rules_user/  ->  import + smoke test  ->  SHADOW  ->  ACTIVE

Loading happens ONLY on the cold path, never mid-round. A new rule enters in
SHADOW: computed, traced and displayed, but not applied. Someone promotes it
after seeing the diff it would have caused, priced in euros.

That is what makes "teammates add rules mid-tournament" safe. Nobody has to
trust anybody.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from c2f.core.models import Case, Context, LineItem, Stage
from c2f.rules.protocol import RuleState
from c2f.rules.sandbox import run_rule

STATE_FILE = "rules_state.json"

# The gate every rule must pass before it may be registered at all.
SMOKE_CASE = Case(
    case_id="smoke",
    policy_text="Policy covers water damage to floors. Excludes wear and tear.",
    damage_description="The water pipe in the living room broke.",
    items=(LineItem(0, "New installation of laminate incl. impact sound insulation", 18.0, "m2"),),
)


@dataclass
class LoadReport:
    loaded: list[str]
    rejected: list[dict[str, str]]

    def ok(self) -> bool:
        return not self.rejected


def _read_states(root: Path) -> dict[str, str]:
    f = root / STATE_FILE
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def write_state(root: Path, name: str, state: RuleState) -> None:
    states = _read_states(root)
    states[name] = state.value
    (root / STATE_FILE).write_text(json.dumps(states, indent=2, sort_keys=True), encoding="utf-8")


def _import_module(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(f"rules_user.{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _smoke(rule) -> str | None:
    """Run the rule once against a known-good case. Returns an error or None."""
    ctx = Context(case=SMOKE_CASE, item=SMOKE_CASE.items[0])
    if rule.stage in (Stage.ADJUST, Stage.GUARD):
        from c2f.estimate.pricebook import lookup
        ctx = Context(case=SMOKE_CASE, item=SMOKE_CASE.items[0],
                      belief=lookup(SMOKE_CASE.items[0]), covered=True)
    outcome = run_rule(rule, ctx)
    return outcome.error


def load_rules(engine, root: Path, states: dict[str, str] | None = None) -> LoadReport:
    """Import every rule in `root` and register it. Cold path only.

    `states` overrides rules_state.json. Pass `{}` to load everything as SHADOW
    regardless of what the machine has promoted -- which is what a test asserting
    the shadow default needs, since rules_state.json is gitignored and therefore
    differs per machine.
    """
    loaded: list[str] = []
    rejected: list[dict[str, str]] = []
    states = _read_states(root) if states is None else states

    for path in sorted(root.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            mod = _import_module(path)
        except Exception:  # noqa: BLE001 -- untrusted file
            rejected.append({"source": path.name, "rule": "-",
                             "error": traceback.format_exc(limit=2).strip().splitlines()[-1]})
            continue

        rules = getattr(mod, "RULES", None)
        if not rules:
            rejected.append({"source": path.name, "rule": "-",
                             "error": "module defines no RULES list"})
            continue

        for rule in rules:
            for attr in ("name", "stage", "priority", "author"):
                if not hasattr(rule, attr):
                    rejected.append({"source": path.name, "rule": getattr(rule, "name", "?"),
                                     "error": f"missing attribute {attr!r}"})
                    break
            else:
                err = _smoke(rule)
                if err:
                    rejected.append({"source": path.name, "rule": rule.name,
                                     "error": f"smoke test failed: {err}"})
                    continue
                state = RuleState(states.get(rule.name, RuleState.SHADOW.value))
                engine.register(rule, state=state, source=path.name)
                loaded.append(f"{rule.name}[{state.value}]")

    return LoadReport(loaded=loaded, rejected=rejected)
