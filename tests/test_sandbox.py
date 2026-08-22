"""A teammate's bad rule may make our numbers worse. It must never cost a round."""
import time

from c2f.core.models import Case, Context, LineItem, Stage, Verdict
from c2f.rules.sandbox import RULE_TIMEOUT_S, run_rule

CASE = Case("c", "policy", "desc", (LineItem(1, "thing", 2.0, "m2"),))
CTX = Context(case=CASE, item=CASE.items[0])


class Raiser:
    name, stage, priority, author = "raiser", Stage.ADJUST, 0, "t"
    def apply(self, ctx): raise RuntimeError("kaboom")


class Hanger:
    name, stage, priority, author = "hanger", Stage.ADJUST, 0, "t"
    def apply(self, ctx):
        time.sleep(5)


class WrongType:
    name, stage, priority, author = "wrongtype", Stage.ADJUST, 0, "t"
    def apply(self, ctx): return {"scale": 0.5}


class OutOfRange:
    name, stage, priority, author = "oor", Stage.ADJUST, 0, "t"
    def apply(self, ctx): return Verdict(scale=1e6)


class Abstains:
    name, stage, priority, author = "abstains", Stage.ADJUST, 0, "t"
    def apply(self, ctx): return None


def test_exception_is_contained():
    o = run_rule(Raiser(), CTX)
    assert not o.ok and "kaboom" in o.error


def test_hung_rule_is_abandoned_not_awaited():
    t0 = time.perf_counter()
    o = run_rule(Hanger(), CTX)
    assert not o.ok and "timeout" in o.error
    assert time.perf_counter() - t0 < RULE_TIMEOUT_S * 10


def test_wrong_return_type_rejected():
    assert not run_rule(WrongType(), CTX).ok


def test_out_of_range_is_discarded_not_silently_clamped():
    o = run_rule(OutOfRange(), CTX)
    assert not o.ok and o.verdict is None


def test_abstention_is_normal():
    o = run_rule(Abstains(), CTX)
    assert o.ok and o.verdict is None
