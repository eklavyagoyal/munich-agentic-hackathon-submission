"""LLM ensemble: the PRIOR/COVERAGE estimator (build order step 4).

Runs OFF the hot path. The engine is synchronous and rules must be pure, so N
sequential LLM calls inside `engine.evaluate` would both violate that contract and
blow the 60s budget. Instead every item (and every ensemble sample) is fetched
concurrently *before* the engine loop, and `rules_user/llm_prior.py` is a pure
dict lookup over the result. Wall clock is one call, not N.

Two things the price book cannot do, and the reason this exists:
  - RELATEDNESS. "46 m2 repainting" is a legitimate rate and a fraudulent line when
    the damage description says one 18 m2 room. Only reading the case catches that.
  - the long tail of descriptions no keyword table will ever cover.

The ensemble spread IS the sigma the decision rules need, so it comes for free.

VAT: routed through `pricebook.gross()` so the 19% lives in exactly one place, per
that module's invariant. A non-standard VAT line would be mispriced; see ASKS.md.
"""
from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass

from c2f.core.models import SIGMA_FLOOR, Belief, Case, LineItem, PriorEstimate
from c2f.estimate import llm, pricebook

# 10th..90th percentile spans 2 * 1.2816 sigma in log space.
_P10_P90_Z = 2 * 1.2815515655446004

SYSTEM = f"""You are a senior German P&C claims expert (Sachbearbeiter Sachschaden) \
valuing individual invoice line items for an insurer.

For each item decide, in this order:
1. COVERED — does this policy pay for this kind of work at all? Read exclusions literally.
2. RELATED — does this item belong to THIS reported damage, at THIS scope? An item can be
   covered in principle yet unrelated in scope: a whole-floor renovation billed for a 2 m2
   stain is unrelated beyond those 2 m2, and a quantity larger than the damage description
   supports is the most common inflation.
3. PRICE — the highest NET price per unit a claims expert would still sign off, as a
   10th/50th/90th percentile range over your own uncertainty.

Judge against the price book below, not retail intuition. Your p50 matters most: make it
your genuine best estimate, neither cautious nor generous. Widen p10..p90 honestly when
the item is vague — downstream code turns that spread into how hard it shades the charge,
so a dishonestly narrow band costs us money.

{pricebook.prompt_text()}"""

_DIGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "damage_summary": {"type": "string", "description": "what happened, 2 sentences"},
        "damage_scope": {
            "type": "string",
            "description": "physical extent the description supports: rooms, areas, m2, parts",
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
        "flag": {
            "type": "string",
            "description": "empty, or a short warning: 'quantity exceeds damage scope', "
            "'duplicate of item 3'",
        },
    },
    "required": [
        "coverage_reasoning",
        "covered",
        "related",
        "unit_price_p10",
        "unit_price_p50",
        "unit_price_p90",
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

# The per-item call gets the DIGEST, not the policy. Sending policy[:40_000] plus
# damage[:20_000] with every sample meant the same 60k characters went out once per
# item per sample -- 51 times for a 17-item case, about 765k input tokens in one
# burst. Measured: 53.9s for 17 items and only 2 estimates returned, against a 52s
# hard deadline, so the whole tier was useless in a live round. The digest call
# exists precisely so the item calls do not need the raw policy; it just was not
# being used that way.
_ITEM_PROMPT = """{digest}
DAMAGE DESCRIPTION (excerpt):
```
{damage}
```

FULL INVOICE (for duplicate and scope checks):
{invoice}

VALUE THIS LINE ITEM:
  item:        {idx}
  description: {description}
  quantity:    {qty} {unit}

Give the NET price per {unit}, not the line total."""


@dataclass(frozen=True)
class _Sample:
    covered: bool
    related: bool
    p10: float
    p50: float
    p90: float
    reasoning: str
    flag: str


def _label(it: LineItem) -> str:
    return f"  [{it.idx}] {it.qty:g} {it.unit} — {it.description}"


def _declared_sigma(s: _Sample) -> float:
    if s.p10 <= 0 or s.p90 <= s.p10:
        return 0.0
    return (math.log(s.p90) - math.log(s.p10)) / _P10_P90_Z


async def _digest(case: Case, timeout: float) -> str:
    d = await llm.ask_json(
        _DIGEST_PROMPT.format(
            policy=case.policy_text[:40_000], damage=case.damage_description[:20_000]
        ),
        schema=_DIGEST_SCHEMA,
        fast=False,
        timeout=timeout,
        system=SYSTEM,
        images=case.image_paths[:3],
    )
    return (
        "\nPOLICY DIGEST (pre-computed; trust it over your own re-reading):\n"
        f"  damage:     {d['damage_summary']}\n"
        f"  scope:      {d['damage_scope']}\n"
        f"  covered:    {'; '.join(d['covered_perils'])}\n"
        f"  EXCLUDED:   {'; '.join(d['exclusions'])}\n"
        f"  deductible: {d['deductible']}\n"
    )


async def _sample(
    case: Case, item: LineItem, digest: str, *, fast: bool, timeout: float
) -> _Sample | None:
    """One valuation call. None on any failure — the caller decides across samples."""
    prompt = _ITEM_PROMPT.format(
        damage=case.damage_description[:1_500],
        digest=digest,
        invoice="\n".join(_label(i) for i in case.items),
        idx=item.idx,
        description=item.description,
        qty=f"{item.qty:g}",
        unit=item.unit or "unit",
    )
    try:
        d = await llm.ask_json(
            prompt,
            schema=_ITEM_SCHEMA,
            fast=fast,
            timeout=timeout,
            system=SYSTEM,
            images=() if fast else case.image_paths[:3],
        )
    except llm.NoBackend:
        return None
    except Exception as e:
        llm.log.warning("valuation failed for item %s: %s", item.idx, e)
        return None

    p50 = float(d["unit_price_p50"])
    if not math.isfinite(p50):
        llm.log.warning("item %s: non-finite p50", item.idx)
        return None
    if p50 <= 0:
        # A zero price is an ANSWER, not a failure: the model is saying the line is
        # worth nothing. Discarding it threw away the sharpest per-item signal we
        # have. Measured on game 8: the four items priced at zero had proven
        # thresholds of t < 84.33, t < 1.00, t < 1.00, t < 1.00, while the four it
        # priced were all t >= 400. Kept as a zero sample so _combine can count it.
        return _Sample(covered=bool(d["covered"]), related=bool(d["related"]),
                       p10=0.0, p50=0.0, p90=0.0,
                       reasoning=str(d.get("reasoning", ""))[:400], flag="worthless")
    # Never trust the ordering: a swapped p10/p90 would silently invert sigma.
    return _Sample(
        covered=bool(d["covered"]),
        related=bool(d["related"]),
        p10=min(float(d["unit_price_p10"]), p50),
        p50=p50,
        p90=max(float(d["unit_price_p90"]), p50),
        reasoning=str(d["coverage_reasoning"])[:300],
        flag=str(d["flag"])[:120],
    )


def _combine(item: LineItem, samples: list[_Sample], source: str) -> PriorEstimate:
    """Ensemble -> one belief. Sigma is the WIDER of ensemble disagreement and the
    model's own declared band: agreement across samples does not make a vague item
    precise, and a confident lone sample does not make it certain either."""
    # Zero-priced samples carry no magnitude, so they must not enter the geometric
    # mean -- a single zero would drag it to zero. They are counted instead, and the
    # belief is built from whatever actually named a price.
    zeros = [s for s in samples if s.p50 <= 0]
    priced = [s for s in samples if s.p50 > 0]
    # TOTAL sample count, kept apart from the priced count computed below. Reporting
    # the priced count as `samples` while worthless_votes counted zeros made a mixed
    # 2-zero/1-priced item read "2 of 1", so every mixed item tripped a majority test
    # that should have failed it.
    n_total = len(samples)
    n = n_total
    if not priced:
        # The whole ensemble says worthless. No magnitude claim, but the vote is the
        # point: a GUARD can lower b on this item while leaving the charge alone.
        return PriorEstimate(
            belief=None,
            covered=sum(s.covered for s in zeros) * 2 > len(zeros),
            related=sum(s.related for s in zeros) * 2 > len(zeros),
            worthless_votes=len(zeros),
            note=zeros[0].reasoning,
            flag="worthless",
            samples=n_total,
        )
    samples = priced
    gross = [pricebook.gross(s.p50 * max(item.qty, 0.0)) for s in samples]
    base = Belief.from_samples(gross, source=source)  # geometric mean + ensemble spread

    declared = sorted(_declared_sigma(s) for s in samples)
    declared_med = declared[len(declared) // 2]
    ensemble_sigma = base.sigma if len(samples) > 1 else 0.0
    sigma = min(max(ensemble_sigma, declared_med, SIGMA_FLOOR), 3.0)

    cov_votes = sum(s.covered for s in samples)
    rel_votes = sum(s.related for s in samples)
    n = len(samples)
    flags = [s.flag for s in samples if s.flag]
    split = ""
    if cov_votes not in (0, n):
        split += f" [covered split {cov_votes}/{n}]"
    if rel_votes not in (0, n):
        split += f" [related split {rel_votes}/{n}]"

    return PriorEstimate(
        belief=Belief(median=base.median, sigma=sigma, source=source),
        covered=cov_votes * 2 > n,
        related=rel_votes * 2 > n,
        worthless_votes=len(zeros),
        note=samples[n // 2].reasoning,
        flag=((flags[0] + " ") if flags else "") + split.strip(),
        samples=n_total,
    )


async def prefetch(
    case: Case,
    *,
    fast: bool = False,
    samples: int = 3,
    timeout: float = 25.0,
    digest: bool = True,
) -> dict[int, PriorEstimate]:
    """Value every line item concurrently. Returns {} when no backend is configured,
    which leaves the price book as the PRIOR — degraded, never zero."""
    if llm.backend() == "none":
        llm.log.warning("no model backend — LLM prior abstains, price book takes over")
        return {}

    # `fast` selects cheap reasoning effort; it used to ALSO force a single sample,
    # which made every vote a coin flip -- the same item voted "worthless" in one run
    # and priced at 5,950 in the next. Those are separate concerns, so they are
    # separate knobs now. Measured on case 8, the largest at 39 items: 1 sample takes
    # 5.5s and 3 take 9.9s against a 52s budget. The old coupling was saving 4.4s and
    # costing us a reproducible detector.
    n = max(1, samples)
    digest_text = ""
    # The digest is ONE call per case, not per item, so fast mode can afford it -- and
    # cannot afford to skip it. The item prompt was changed to carry the digest
    # INSTEAD of the raw policy (the raw policy was being resent per sample and blew
    # the deadline), so skipping the digest in fast mode left the model judging
    # coverage with no policy context at all. That is every production round.
    if digest:
        try:
            digest_text = await _digest(case, min(18.0, timeout))
        except Exception as e:
            llm.log.warning("policy digest unavailable (%s) — valuing without it", e)

    async def one(item: LineItem) -> tuple[int, PriorEstimate] | None:
        got = [
            s
            for s in await asyncio.gather(
                *(_sample(case, item, digest_text, fast=fast, timeout=timeout) for _ in range(n))
            )
            if s is not None
        ]
        if not got:
            return None  # abstain; the price book PRIOR covers it
        return item.idx, _combine(item, got, f"llm:{llm.model_id()}x{len(got)}")

    results = await asyncio.gather(*(one(it) for it in case.items))
    out = {idx: est for r in results if r is not None for idx, est in (r,)}
    llm.log.warning("llm prior: %d/%d items estimated", len(out), len(case.items))
    return out


def prefetch_sync(case: Case, **kw) -> dict[int, PriorEstimate]:
    """For the synchronous runner. Never raises: a dead estimator must not cost a round."""
    try:
        return asyncio.run(prefetch(case, **kw))
    except Exception as e:
        llm.log.error("LLM prefetch failed entirely (%s) — price book PRIOR stands", e)
        return {}
