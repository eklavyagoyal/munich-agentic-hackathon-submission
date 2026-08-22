"""The four-stage rule engine (PIPELINE.md §4.1).

    COVERAGE -> PRIOR -> ADJUST -> GUARD -> decide(a, b)
     pick one   pick one  all, x   all, n

The stage algebra is the point. ADJUST composes by multiplication and GUARD by
interval intersection -- both commutative -- so the two stages contributors
actually add to in bulk are order-independent by construction. Two teammates
can land calibration rules simultaneously without their behaviour depending on
who imported first. Only the "pick one" stages carry priority, and those change
rarely.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable

from c2f.core.models import Belief, Context, Decision, Stage, Verdict
from c2f.decide.quantile import decide
from c2f.core.invariants import InvariantError, check_decision
from c2f.rules.protocol import Registered, RuleState
from c2f.rules.sandbox import run_rule


@dataclass
class EngineResult:
    decision: Decision
    shadow_diffs: list[dict[str, Any]] = field(default_factory=list)
    alerts: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class _Merged:
    covered: bool
    belief: Belief | None
    clamp: tuple[float, float] | None
    veto: str | None
    trace: list[dict[str, Any]]


class RuleEngine:
    def __init__(self, fallback: Callable[[Context], Belief]) -> None:
        # The emergency rung of the ladder: used when no PRIOR rule speaks, or
        # when a veto fires. Anchored, never generous, never zero.
        self._fallback = fallback
        self._rules: list[Registered] = []
        self._disabled_this_round: set[str] = set()
        self.alerts: list[dict[str, Any]] = []

    # -- registration ----------------------------------------------------
    def register(self, rule, state: RuleState = RuleState.SHADOW, source: str = "") -> None:
        self._rules.append(Registered(rule=rule, state=state, source=source))

    def set_state(self, name: str, state: RuleState) -> bool:
        for r in self._rules:
            if r.name == name:
                r.state = state
                return True
        return False

    @property
    def rules(self) -> list[Registered]:
        return list(self._rules)

    def snapshot(self) -> list[dict[str, str]]:
        """Recorded with every round so any past round is exactly reproducible."""
        return [
            {"name": r.name, "stage": r.rule.stage.value, "priority": str(r.rule.priority),
             "state": r.state.value, "author": r.rule.author, "source": r.source}
            for r in self._rules
        ]

    def begin_round(self) -> None:
        self._disabled_this_round.clear()
        self.alerts.clear()

    # -- evaluation ------------------------------------------------------
    def _active(self) -> list[Registered]:
        return [r for r in self._rules
                if r.state is RuleState.ACTIVE and r.name not in self._disabled_this_round]

    def _shadow(self) -> list[Registered]:
        return [r for r in self._rules
                if r.state is RuleState.SHADOW and r.name not in self._disabled_this_round]

    def _run(self, reg: Registered, ctx: Context) -> Verdict | None:
        outcome = run_rule(reg.rule, ctx)
        if not outcome.ok:
            # Disabled for the REST OF THE ROUND, not permanently: the cold path
            # decides whether it stays off.
            self._disabled_this_round.add(reg.name)
            self.alerts.append({"rule": reg.name, "error": outcome.error,
                                "elapsed_ms": round(outcome.elapsed_ms, 2)})
            return None
        return outcome.verdict

    def _merge(self, regs: Iterable[Registered], ctx: Context) -> _Merged:
        regs = list(regs)
        trace: list[dict[str, Any]] = []

        def stage_rules(stage: Stage) -> list[Registered]:
            return sorted([r for r in regs if r.rule.stage is stage],
                          key=lambda r: -r.rule.priority)

        # --- COVERAGE: highest-priority non-abstaining wins ---------------
        covered = True
        for reg in stage_rules(Stage.COVERAGE):
            v = self._run(reg, ctx)
            if v is not None and v.covered is not None:
                covered = v.covered
                trace.append({"stage": "coverage", "rule": reg.name,
                              "covered": covered, "note": v.note})
                break
        ctx = replace(ctx, covered=covered)
        if not covered:
            return _Merged(False, None, None, None, trace)

        # --- PRIOR: highest-priority non-abstaining wins -------------------
        belief: Belief | None = None
        for reg in stage_rules(Stage.PRIOR):
            v = self._run(reg, ctx)
            if v is not None and v.belief is not None:
                belief = v.belief
                trace.append({"stage": "prior", "rule": reg.name,
                              "median": round(belief.median, 2),
                              "sigma": round(belief.sigma, 3), "note": v.note})
                break
        if belief is None:
            belief = self._fallback(ctx)
            trace.append({"stage": "prior", "rule": "fallback:pricebook",
                          "median": round(belief.median, 2), "sigma": round(belief.sigma, 3)})
            self.alerts.append({"rule": "-", "error": "no PRIOR rule produced a belief"})
        ctx = replace(ctx, belief=belief)

        # --- ADJUST: all apply, product taken (commutative) ---------------
        for reg in stage_rules(Stage.ADJUST):
            v = self._run(reg, ctx)
            if v is not None and v.scale is not None:
                belief = belief.scaled(v.scale)
                trace.append({"stage": "adjust", "rule": reg.name,
                              "scale": round(v.scale, 4), "note": v.note})
        ctx = replace(ctx, belief=belief)

        # --- GUARD: all apply, intersection taken (commutative) -----------
        clamp: tuple[float, float] | None = None
        veto: str | None = None
        for reg in stage_rules(Stage.GUARD):
            v = self._run(reg, ctx)
            if v is None:
                continue
            if v.clamp is not None:
                clamp = v.clamp if clamp is None else (max(clamp[0], v.clamp[0]),
                                                       min(clamp[1], v.clamp[1]))
                trace.append({"stage": "guard", "rule": reg.name, "clamp": list(v.clamp),
                              "note": v.note})
            if v.veto is not None:
                veto = v.veto
                trace.append({"stage": "guard", "rule": reg.name, "veto": v.veto})

        if clamp is not None and clamp[1] <= clamp[0]:
            # Contradictory guards. Drop the clamp rather than produce nonsense.
            self.alerts.append({"rule": "-", "error": f"contradictory clamps {clamp}, dropped"})
            clamp = None
        return _Merged(covered, belief, clamp, veto, trace)

    def _decide(self, m: _Merged, idx: int) -> Decision:
        a, b = decide(m.belief, m.covered, m.clamp, vetoed=m.veto is not None)
        try:
            check_decision(a, b, m.covered)
        except InvariantError as e:
            # Last line of defence. A rule may make our numbers worse; it may
            # never make us emit a corrupt submission.
            self.alerts.append({"rule": "-", "error": f"invariant: {e} -> safe fallback"})
            base = m.belief.median if m.belief else 0.0
            a, b = (0.0, base) if (m.covered and base > 0) else (0.0, 0.0)
        return Decision(idx=idx, a=a, b=b, covered=m.covered, belief=m.belief,
                        trace=tuple(m.trace))

    def evaluate(self, ctx: Context, include_shadow: bool = True) -> EngineResult:
        active = self._active()
        decision = self._decide(self._merge(active, ctx), ctx.item.idx)

        diffs: list[dict[str, Any]] = []
        if include_shadow:
            for reg in self._shadow():
                cand = self._decide(self._merge(active + [reg], ctx), ctx.item.idx)
                if (round(cand.a, 2), round(cand.b, 2)) != (round(decision.a, 2), round(decision.b, 2)):
                    diffs.append({"rule": reg.name, "idx": ctx.item.idx,
                                  "from": [round(decision.a, 2), round(decision.b, 2)],
                                  "to": [round(cand.a, 2), round(cand.b, 2)]})
        return EngineResult(decision=decision, shadow_diffs=diffs, alerts=list(self.alerts))
