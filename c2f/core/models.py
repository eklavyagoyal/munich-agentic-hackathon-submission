"""Core data model. Everything the pipeline passes around is defined here.

`Belief` is deliberately a *distribution*, never a point estimate: the decision
rules in `c2f.decision.quantile` consume quantiles, so an estimator that returns a
single number cannot feed them.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from enum import Enum
from statistics import NormalDist
from collections.abc import Mapping
from typing import Any

_N = NormalDist()

# A 3-sample ensemble that happens to agree does not mean the true uncertainty is
# 5%. This floor keeps us honest; it is a calibration target, not a constant of
# nature -- fit it against the interval bounds in ARCHITECTURE.md §8.
SIGMA_FLOOR = 0.10
SIGMA_LONE_SAMPLE = 0.35


class Stage(str, Enum):
    """Rule stages, ordered. See PIPELINE.md §4.1.

    COVERAGE and PRIOR are *pick one* (priority decides).
    ADJUST and GUARD are *apply all* and commutative, so contributors never
    have to argue about ordering.
    """

    COVERAGE = "coverage"
    PRIOR = "prior"
    ADJUST = "adjust"
    GUARD = "guard"


@dataclass(frozen=True)
class LineItem:
    idx: int
    description: str
    qty: float
    unit: str
    trade: str = ""

    @property
    def key(self) -> str:
        return f"{self.idx}"


@dataclass(frozen=True)
class Case:
    case_id: str
    policy_text: str
    damage_description: str
    items: tuple[LineItem, ...]
    image_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class Belief:
    """Lognormal belief about the secret fair value `t`, as a gross total in EUR.

    `median` is the point of central tendency; `sigma` is the spread in log
    space (so sigma=0.25 is roughly +/-25%).
    """

    median: float
    sigma: float
    source: str = ""

    def __post_init__(self) -> None:
        if not math.isfinite(self.median) or self.median < 0:
            raise ValueError(f"belief median must be finite and >= 0, got {self.median}")
        if not math.isfinite(self.sigma) or not (0 < self.sigma <= 3.0):
            raise ValueError(f"belief sigma must be in (0, 3], got {self.sigma}")

    def quantile(self, q: float) -> float:
        if not 0.0 < q < 1.0:
            raise ValueError(f"quantile q must be in (0,1), got {q}")
        return self.median * math.exp(self.sigma * _N.inv_cdf(q))

    def scaled(self, factor: float) -> Belief:
        return replace(self, median=self.median * factor)

    @classmethod
    def from_samples(cls, samples: list[float], source: str = "") -> Belief:
        """Build a belief from an ensemble. The *spread is the point* -- it is
        the sigma the decision rules need, obtained for free."""
        pos = [s for s in samples if math.isfinite(s) and s > 0]
        if not pos:
            raise ValueError("no positive finite samples")
        logs = [math.log(s) for s in pos]
        mu = sum(logs) / len(logs)
        if len(logs) > 1:
            var = sum((x - mu) ** 2 for x in logs) / (len(logs) - 1)
            sigma = max(math.sqrt(var), SIGMA_FLOOR)
        else:
            sigma = SIGMA_LONE_SAMPLE  # a lone sample tells us nothing about spread
        return cls(median=math.exp(mu), sigma=min(sigma, 3.0), source=source)


@dataclass(frozen=True)
class PriorEstimate:
    """A belief computed OFF the hot path, before the engine runs.

    Exists so an I/O-bound estimator (the LLM ensemble) can feed the rule engine
    without a rule doing I/O: the fetch happens once per round, concurrently for all
    items, and the rule that reads this is a pure dict lookup. Any field may be None,
    meaning the estimator had no opinion on it.
    """

    belief: Belief | None = None
    covered: bool | None = None
    related: bool | None = None
    note: str = ""
    flag: str = ""
    samples: int = 0


@dataclass(frozen=True)
class Verdict:
    """What a rule may contribute. Every field is optional -- a rule returns
    only what it actually knows, and `None` from `apply()` means "no opinion"."""

    covered: bool | None = None
    belief: Belief | None = None
    scale: float | None = None
    clamp: tuple[float, float] | None = None
    veto: str | None = None
    note: str = ""


@dataclass(frozen=True)
class Decision:
    idx: int
    a: float
    b: float
    covered: bool
    belief: Belief | None
    trace: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class Submission:
    case_id: str
    tier: int
    decisions: tuple[Decision, ...]

    def payload(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "items": [
                {"idx": d.idx, "charge_price": round(d.a, 2), "acceptance_limit": round(d.b, 2)}
                for d in self.decisions
            ],
        }


@dataclass(frozen=True)
class History:
    """Past rounds and calibration state, exposed read-only to rules."""

    bounds: dict[str, tuple[float, float]] = field(default_factory=dict)
    trade_bias: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class OpponentModel:
    """What we have learned about the field. Opening default assumes nothing."""

    accept_rate: float | None = None
    observed_charges: tuple[float, ...] = ()


@dataclass(frozen=True)
class Context:
    """Read-only input to a rule. Rules cannot mutate anything, which is what
    makes them replayable offline and safe to run in the hot path."""

    case: Case
    item: LineItem
    belief: Belief | None = None
    covered: bool | None = None
    history: History = field(default_factory=History)
    opponents: OpponentModel = field(default_factory=OpponentModel)
    # Estimates fetched before the round's engine loop, keyed by LineItem.idx.
    # Written exactly once per round and never during it, so rules stay pure.
    prefetch: Mapping[int, PriorEstimate] = field(default_factory=dict)

    @property
    def policy_text(self) -> str:
        return self.case.policy_text

    @property
    def damage_description(self) -> str:
        return self.case.damage_description
