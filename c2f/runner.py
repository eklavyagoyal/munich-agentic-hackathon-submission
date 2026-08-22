"""The round loop (PIPELINE.md §0, §3).

Hard invariant: no code, config or rule changes during the hot path. The rule
set is frozen and snapshotted at round start, so any past round is exactly
reproducible from the event log.

Staged submission: "later submissions overwrite earlier ones" is free option
value. Submission #1 retires all deadline risk; everything after it is upside.
"""
from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from c2f.core.events import EventBus
from c2f.core.models import Case, Context, Decision, History, OpponentModel, Submission
from c2f.core.invariants import InvariantError, check_decision
from c2f.decide.quantile import decide
from c2f.estimate.pricebook import lookup
from c2f.ingest import decrypt, parse
from c2f.rules.engine import RuleEngine
from c2f.submit.client import ApiClient


@dataclass
class RoundConfig:
    round_no: int
    case_id: str
    archive: Path
    baseline_at_s: float = 15.0     # submission #1
    hard_deadline_s: float = 52.0   # submission #2 fires regardless


class RoundFailure(RuntimeError):
    pass


class Runner:
    def __init__(self, api: ApiClient, engine: RuleEngine, bus: EventBus,
                 history: History | None = None,
                 opponents: OpponentModel | None = None) -> None:
        self.api = api
        self.engine = engine
        self.bus = bus
        self.history = history or History()
        self.opponents = opponents or OpponentModel()

    # -- the emergency rung: never submit nothing -------------------------
    def _fallback_decisions(self, case: Case) -> tuple[Decision, ...]:
        out = []
        for item in case.items:
            belief = lookup(item)
            a, b = decide(belief, covered=True)
            out.append(Decision(idx=item.idx, a=a, b=b, covered=True, belief=belief,
                                trace=({"stage": "fallback", "rule": "pricebook"},)))
        return tuple(out)

    def _evaluate(self, case: Case, deadline: float) -> tuple[Decision, ...]:
        decisions: list[Decision] = []
        for item in case.items:
            if time.monotonic() > deadline:
                # Out of time: everything not yet evaluated drops to the book.
                self.bus.emit("alert", level="warn",
                              msg=f"deadline hit at item {item.idx}, remaining -> pricebook")
                belief = lookup(item)
                a, b = decide(belief, covered=True)
                decisions.append(Decision(item.idx, a, b, True, belief,
                                          ({"stage": "fallback", "rule": "deadline"},)))
                continue

            ctx = Context(case=case, item=item, history=self.history,
                          opponents=self.opponents)
            res = self.engine.evaluate(ctx)
            d = res.decision
            if d.belief is not None:
                self.bus.emit("item.belief", idx=item.idx, median=round(d.belief.median, 2),
                              sigma=round(d.belief.sigma, 3), source=d.belief.source)
            for entry in d.trace:
                self.bus.emit("rule.fired", idx=item.idx, **entry)
            for diff in res.shadow_diffs:
                self.bus.emit("rule.fired", shadow=True, **diff)
            for alert in res.alerts:
                self.bus.emit("alert", level="warn", **alert)
            self.bus.emit("item.decided", idx=item.idx, a=round(d.a, 2), b=round(d.b, 2),
                          covered=d.covered, trace=list(d.trace))
            decisions.append(d)
        return tuple(decisions)

    def _submit(self, case_id: str, tier: int, decisions: tuple[Decision, ...]) -> Submission:
        for d in decisions:
            try:
                check_decision(d.a, d.b, d.covered)
            except InvariantError as e:
                raise RoundFailure(f"item {d.idx} violates invariants: {e}") from e

        sub = Submission(case_id=case_id, tier=tier, decisions=decisions)
        self.bus.emit("submission.built", tier=tier, n_items=len(decisions),
                      total_a=round(sum(d.a for d in decisions), 2),
                      total_b=round(sum(d.b for d in decisions), 2))
        t0 = time.perf_counter()
        result = self.api.submit(sub)
        self.bus.emit("submission.sent", tier=tier, ok=result.ok, status=result.status,
                      ms=round((time.perf_counter() - t0) * 1000, 1), detail=result.detail)
        if not result.ok:
            self.bus.emit("alert", level="error", msg=f"submission tier {tier} failed")
            return sub

        # "The POST returned 200" and "our numbers are what the server will
        # score" are not the same claim.
        try:
            echo = self.api.get_submission(case_id)
            ok = echo is not None and echo.get("items") == sub.payload()["items"]
            self.bus.emit("submission.verified", tier=tier, ok=ok)
        except NotImplementedError:
            self.bus.emit("submission.verified", tier=tier, ok=None,
                          detail="read-back not supported by API")
        return sub

    def run_round(self, cfg: RoundConfig) -> list[Submission]:
        self.bus.bind(cfg.round_no, cfg.case_id)
        start = time.monotonic()
        self.engine.begin_round()
        self.bus.emit("round.scheduled", case=cfg.case_id,
                      rules=self.engine.snapshot())      # frozen for this round

        key = self.api.fetch_key(cfg.case_id)
        self.bus.emit("key.received", case=cfg.case_id,
                      ms=round((time.monotonic() - start) * 1000, 1))

        with tempfile.TemporaryDirectory(prefix="c2f-") as tmp:
            files = decrypt.extract(cfg.archive, key, Path(tmp))
            self.bus.emit("case.decrypted", files=[f.name for f in files],
                          ms=round((time.monotonic() - start) * 1000, 1))

            case = parse.build_case(cfg.case_id, files)
            self.bus.emit("case.parsed", n_items=len(case.items),
                          items=[{"idx": i.idx, "desc": i.description,
                                  "qty": i.qty, "unit": i.unit} for i in case.items])

            sent: list[Submission] = []
            decisions = self._evaluate(case, deadline=start + cfg.baseline_at_s)
            sent.append(self._submit(cfg.case_id, 1, decisions))

            # Tier 2 seam: the LLM ensemble lands here (build order step 4).
            # Until then tier 1 is our best answer and we do not resubmit --
            # a lower-quality write must never overwrite a higher-quality one.

        self.bus.emit("round.closed", elapsed_s=round(time.monotonic() - start, 2))
        return sent
