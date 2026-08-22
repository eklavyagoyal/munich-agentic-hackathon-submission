"""The rule contract. This is the entire API a contributor needs to know.

Drop a file in `rules_user/` that defines one or more `Rule` subclasses (or any
object matching the protocol) and export them via a module-level `RULES` list.

Rules are PURE: no I/O, no network, no global state. Everything they may read
is in `Context`. That is what makes them replayable offline and safe to run in
a 60-second hot path.

Return `None` from `apply()` to abstain. Abstention is the normal case -- a rule
about flooring stays silent on windshields instead of passing values through.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from c2f.core.models import Context, Stage, Verdict


class RuleState(str, Enum):
    ACTIVE = "active"       # applied to real submissions
    SHADOW = "shadow"       # computed and displayed, NOT applied -- the default
    DISABLED = "disabled"


@runtime_checkable
class Rule(Protocol):
    name: str
    stage: Stage
    priority: int
    author: str

    def apply(self, ctx: Context) -> Verdict | None: ...


class BaseRule:
    """Convenience base. Subclass, set the class attributes, implement apply()."""

    name: str = "unnamed"
    stage: Stage = Stage.ADJUST
    priority: int = 0
    author: str = ""

    def apply(self, ctx: Context) -> Verdict | None:  # pragma: no cover
        raise NotImplementedError


@dataclass
class Registered:
    """A rule plus the lifecycle state the engine tracks for it."""

    rule: Rule
    state: RuleState = RuleState.SHADOW
    source: str = ""

    @property
    def name(self) -> str:
        return self.rule.name
