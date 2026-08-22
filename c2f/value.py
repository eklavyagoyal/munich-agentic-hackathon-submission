"""Line item -> belief about the secret threshold t.

One call per item, all in parallel, so wall-clock is one call and not N. The deep pass
first spends one hop digesting the policy into an explicit exclusion list, because the
covered/related verdict flips t between 0 and its full value — a 100% error, versus the
~20% error of mispricing (GAMEPLAN §2.4).

Field order in the schema is load-bearing: coverage reasoning is produced *before* the
price, so the price is conditioned on the verdict rather than rationalised after it.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from . import llm
from .extract import Case, LineItem

PRICEBOOK = (Path(__file__).parent / "pricebook.md").read_text()

_SYSTEM = f"""You are a senior German P&C claims expert (Sachbearbeiter Sachschaden) \
valuing individual invoice line items.

For each item you decide three things, in this order:
1. COVERED — does this policy pay for this kind of work at all? Read the exclusions literally.
2. RELATED — does this item plausibly belong to THIS reported damage, in this scope? An item
   can be covered in principle yet unrelated in scope (a whole-floor renovation billed for a
   2 m2 stain is unrelated beyond those 2 m2).
3. PRICE — the highest NET price per unit a claims expert would still sign off, as a
   10th/50th/90th percentile range over your own uncertainty.

Judge against the price book below, not against your intuition about retail prices. Your p50
is the number that matters most; make it your genuine best estimate, neither cautious nor
generous. Widen p10..p90 honestly when the item is vague — downstream code uses that spread.

{PRICEBOOK}"""

_DIGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "damage_summary": {"type": "string", "description": "what happened, 2 sentences"},
        "damage_scope": {
            "type": "string",
            "description": "physical extent implied by the description: rooms, areas, parts",
        },
        "covered_perils": {"type": "array", "items": {"type": "string"}},
        "exclusions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "verbatim exclusions and limits from the policy",
        },
        "deductible": {"type": "string"},
    },
    "required": ["damage_summary", "damage_scope", "covered_perils", "exclusions", "deductible"],
    "additionalProperties": False,
}

_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "coverage_reasoning": {"type": "string", "description": "one sentence, cite the policy"},
        "covered": {"type": "boolean"},
        "related": {"type": "boolean"},
        "unit_price_p10": {"type": "number", "description": "NET price per unit, EUR"},
        "unit_price_p50": {"type": "number"},
        "unit_price_p90": {"type": "number"},
        "vat_rate": {"type": "number", "description": "0.19 unless the policy or invoice says otherwise"},
        "flag": {
            "type": "string",
            "description": "empty, or a short warning: 'quantity implausible', 'duplicate of pos 3', ...",
        },
    },
    "required": [
        "coverage_reasoning",
        "covered",
        "related",
        "unit_price_p10",
        "unit_price_p50",
        "unit_price_p90",
        "vat_rate",
        "flag",
    ],
    "additionalProperties": False,
}

_DIGEST_PROMPT = """POLICY:
```
{policy}
```

DAMAGE DESCRIPTION:
```
{damage}
```

Digest this claim: what is covered, what is excluded verbatim, and the physical scope the
damage description supports."""

_ITEM_PROMPT = """POLICY:
```
{policy}
```

DAMAGE DESCRIPTION:
```
{damage}
```
{digest}
FULL INVOICE (for duplicate and scope checks):
{invoice_lines}

VALUE THIS LINE ITEM:
  position:    {pos}
  description: {description}
  quantity:    {qty} {unit}

Give the NET price per {unit}, not the line total."""


@dataclass
class Estimate:
    item: LineItem
    covered: bool
    related: bool
    p10: float
    p50: float
    p90: float
    vat_rate: float
    reasoning: str = ""
    flag: str = ""
    source: str = "llm"

    def gross_median(self) -> float:
        """Our belief about t: gross total for the whole line. Trap 2 and 3 in GAMEPLAN §8."""
        return self.p50 * self.item.qty * (1 + self.vat_rate)

    def gross_quantiles(self) -> tuple[float, float]:
        scale = self.item.qty * (1 + self.vat_rate)
        return self.p10 * scale, self.p90 * scale

    @classmethod
    def unknown(cls, item: LineItem, reason: str) -> "Estimate":
        """Nothing usable came back. Zero price, but flagged loudly — run.py decides."""
        return cls(item, True, True, 0.0, 0.0, 0.0, item.vat_rate, reason, "NO ESTIMATE", "failed")


async def digest(case: Case, *, timeout: float = 20.0) -> str:
    """Explicit exclusion list, computed once and injected into every item call."""
    d = await llm.ask_json(
        _DIGEST_PROMPT.format(policy=case.policy[:40_000], damage=case.damage[:20_000]),
        schema=_DIGEST_SCHEMA,
        fast=False,
        timeout=timeout,
        system=_SYSTEM,
        images=case.images[:3],
    )
    return (
        "\nPOLICY DIGEST (pre-computed, trust it over your own re-reading):\n"
        f"  damage:     {d['damage_summary']}\n"
        f"  scope:      {d['damage_scope']}\n"
        f"  covered:    {'; '.join(d['covered_perils'])}\n"
        f"  EXCLUDED:   {'; '.join(d['exclusions'])}\n"
        f"  deductible: {d['deductible']}\n"
    )


async def _one(
    case: Case, item: LineItem, all_items: list[LineItem], digest_text: str, *, fast: bool, timeout: float
) -> Estimate:
    prompt = _ITEM_PROMPT.format(
        policy=case.policy[:40_000],
        damage=case.damage[:20_000],
        digest=digest_text,
        invoice_lines="\n".join("  " + i.label for i in all_items),
        pos=item.pos,
        description=item.description,
        qty=f"{item.qty:g}",
        unit=item.unit,
    )
    try:
        d = await llm.ask_json(
            prompt,
            schema=_ITEM_SCHEMA,
            fast=fast,
            timeout=timeout,
            system=_SYSTEM,
            images=case.images[:3] if not fast else None,
        )
    except Exception as e:
        llm.log.warning("valuation failed for pos %s: %s", item.pos, e)
        return Estimate.unknown(item, f"{type(e).__name__}: {e}")

    p10, p50, p90 = d["unit_price_p10"], d["unit_price_p50"], d["unit_price_p90"]
    if not p50 > 0:
        return Estimate.unknown(item, "model returned a non-positive p50")
    # Do not trust the ordering; a swapped p10/p90 would silently invert sigma.
    p10, p90 = min(p10, p50), max(p90, p50)
    return Estimate(
        item=item,
        covered=d["covered"],
        related=d["related"],
        p10=p10,
        p50=p50,
        p90=p90,
        vat_rate=d["vat_rate"] if 0 <= d["vat_rate"] < 1 else item.vat_rate,
        reasoning=d["coverage_reasoning"],
        flag=d["flag"],
        source="fast" if fast else "deep",
    )


async def value_case(
    case: Case,
    items: list[LineItem],
    *,
    fast: bool,
    digest_text: str = "",
    timeout: float = 25.0,
) -> list[Estimate]:
    """All items concurrently. A dead item degrades to Estimate.unknown, never to a hang."""
    return list(
        await asyncio.gather(
            *(_one(case, it, items, digest_text, fast=fast, timeout=timeout) for it in items)
        )
    )


def demo() -> None:
    from .decide import sigma_from_quantiles, submission

    it = LineItem(pos="2", description="Laminat verlegen", qty=18.5, unit="m2", vat_rate=0.19)
    e = Estimate(it, True, True, 28.0, 35.0, 44.0, 0.19)

    # Gross line total, not net, not per-unit.
    assert abs(e.gross_median() - 35.0 * 18.5 * 1.19) < 0.01, e.gross_median()
    lo, hi = e.gross_quantiles()
    assert lo < e.gross_median() < hi

    a, b = submission(e.gross_median(), sigma_from_quantiles(lo, hi))
    assert 0 < a < b < e.gross_median(), (a, b)

    # An uncovered item is worth nothing to charge and nothing to accept.
    unc = Estimate(it, False, True, 28.0, 35.0, 44.0, 0.19)
    assert submission(unc.gross_median(), 0.2, unc.covered, unc.related) == (0.0, 0.0)

    # A failed estimate must be visibly failed, never a quiet zero.
    u = Estimate.unknown(it, "timeout")
    assert u.source == "failed" and u.flag == "NO ESTIMATE" and u.gross_median() == 0.0

    print(f"value.py self-check ok — t≈{e.gross_median():.2f} gross -> a={a:.2f} b={b:.2f}")


if __name__ == "__main__":
    demo()
