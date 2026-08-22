"""Post-conditions on a decision. These run after every rule has had its say.

A rule may make our numbers worse. A rule must never make us miss or corrupt a
submission -- that is the only unrecoverable failure in this game.
"""
from __future__ import annotations

import math

# From GAME_DESCRIPTION: b=0 rejects every incoming charge, including fair ones,
# and pays 1.5a to every opponent on every fair item. It is the single worst
# submission possible and is only ever correct for a genuinely uncovered item.
MAX_PLAUSIBLE_EUR = 1_000_000.0


class InvariantError(ValueError):
    pass


def check_decision(a: float, b: float, covered: bool) -> None:
    for name, v in (("a", a), ("b", b)):
        if not math.isfinite(v):
            raise InvariantError(f"{name} is not finite: {v}")
        if v < 0:
            raise InvariantError(f"{name} must be >= 0, got {v}")
        if v > MAX_PLAUSIBLE_EUR:
            raise InvariantError(f"{name} implausibly large: {v}")

    if not covered:
        if a != 0.0 or b != 0.0:
            raise InvariantError(f"uncovered item must be a=b=0, got a={a} b={b}")
        return

    if b == 0.0:
        raise InvariantError("b=0 on a covered item: rejects every fair claim (see §3)")
    if a >= b:
        # We must always be willing to accept our own charge.
        raise InvariantError(f"a must be < b, got a={a} b={b}")
