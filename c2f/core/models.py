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
    idx: int                  # OUR ordinal, 1..N, contiguous by construction
    description: str
    qty: float
    unit: str
    pos: str = ""             # position as PRINTED ("1", "2a", "1.1") -- payload identity
    trade: str = ""
    vat_rate: float = 0.19

    def __post_init__(self) -> None:
        if not self.pos:
            object.__setattr__(self, "pos", str(self.idx))

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
    # How many ensemble samples priced the item at ZERO, out of `samples`. Measured
    # on game 8: the four items the model priced at zero had proven thresholds of
    # t < 84.33, t < 1.00, t < 1.00 and t < 1.00, while the four it did price were
    # all t >= 400. It is the sharpest per-item discriminator found so far, and it
    # used to be discarded as a failed sample.
    worthless_votes: int = 0
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
    # Cap the ACCEPTANCE LIMIT alone, leaving the charge untouched. `clamp` cannot
    # express this: it applies to both a and b, and decide() then repairs b <= a by
    # lowering a. That coupling is ours, not the game's -- API_HANDBOOK:82 requires
    # only that both values be finite and nonnegative.
    #
    # It exists because the two sides of a worthless item want opposite things.
    # Charging high on one earns real money: roughly half the field accepts our
    # over-charge, and 13,005.30 of our income across games 1-7 came from charges
    # proven fraudulent. Accepting on the same item just buys their fraud. Measured
    # oracle value of keeping a and setting b=0 on worthless items: +14,575.16 over
    # 15 games, against +4,475.46 for zeroing both.
    accept_ceiling: float | None = None
    veto: str | None = None
    note: str = ""


@dataclass(frozen=True)
class Decision:
    idx: int
    a: float
    b: float
    covered: bool
    belief: Belief | None
    # True when a rule deliberately capped b below a. Without this flag the
    # invariant check cannot tell a considered "charge high, accept nothing" from
    # the accident it exists to catch -- and the accident is game 1's -8,273.70.
    accept_capped: bool = False
    trace: tuple[dict[str, Any], ...] = ()


def _money(x: float) -> float:
    """Finite, nonnegative, 2dp. The API returns 422 for anything else."""
    if not math.isfinite(x) or x < 0:
        return 0.0
    return round(x, 2)


@dataclass(frozen=True)
class Submission:
    case_id: str
    tier: int
    decisions: tuple[Decision, ...]

    def payload(self) -> list[dict[str, Any]]:
        """The PUT body, exactly as API_HANDBOOK.md specifies: a BARE ARRAY keyed on
        `index`. It was previously an {case_id, items: [...]} envelope keyed on `idx`,
        which the API rejects with 422.

        Values are clamped finite and nonnegative here rather than trusted, because a
        single NaN reaching the wire is a 422 for the WHOLE submission -- every line
        item then falls back to the game defaults of 0/0, which is the worst possible
        outcome (reject everything, pay the 1.5a penalty to everyone).
        """
        return [
            {
                "index": d.idx,
                "charge_price": _money(d.a),
                "acceptance_limit": _money(d.b),
            }
            for d in self.decisions
        ]


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
