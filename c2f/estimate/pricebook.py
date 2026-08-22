"""Deterministic price book -- the emergency rung of the fallback ladder and
the baseline PRIOR until the LLM ensemble lands.

VAT IS EXPLICIT AND SEPARATE. Submissions must be the GROSS TOTAL for the whole
line item (GAME_DESCRIPTION), never net and never per-unit. Getting this wrong
is a flat 19% systematic error -- larger than the entire margin between our `a`
and our `b`, so it is handled in exactly one place and asserted at the boundary.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from c2f.core.models import Belief, Context, LineItem

VAT_RATE = 0.19


@dataclass(frozen=True)
class Rate:
    trade: str
    unit: str
    low: float       # net EUR per unit
    high: float
    keywords: tuple[str, ...]


# Net German trade rates. Keywords cover DE and EN -- the sample invoice is
# English but the policy text may not be.
RATES: tuple[Rate, ...] = (
    Rate("flooring", "m2", 8, 18, ("laminat entfern", "remove laminate", "ausbau laminat",
                                   "demontage bodenbelag", "remove water-damaged laminate")),
    Rate("flooring", "m2", 25, 45, ("laminat verleg", "laminat neu", "install laminate",
                                    "new installation of laminate", "bodenbelag verleg")),
    Rate("flooring", "lm", 8, 18, ("sockelleiste", "skirting", "fussleiste", "fußleiste")),
    Rate("drying",   "stk", 60, 180, ("trocknung", "drying", "bautrockner", "dehumidif")),
    Rate("painting", "m2", 8, 20, ("malerarbeit", "streichen", "paint", "anstrich")),
    Rate("plumbing", "h", 60, 110, ("sanitaer", "sanitär", "klempner", "plumb", "rohr")),
    Rate("electric", "h", 65, 120, ("elektro", "electric")),
    Rate("generic",  "h", 45, 95, ("stunde", "hour", "arbeitszeit", "labour", "labor")),

    # --- flooring, extended ---------------------------------------------
    Rate("flooring", "m2", 30, 55, ("parkett schleifen", "parkett versiegel", "sand parquet")),
    Rate("flooring", "m2", 45, 110, ("parkett", "parquet", "dielenboden")),
    Rate("flooring", "m2", 15, 40, ("teppich", "carpet")),
    Rate("flooring", "m2", 45, 95, ("fliesen leg", "fliesen neu", "fliesen", "tiling", "tile")),
    Rate("screed",   "m2", 20, 36, ("estrich entfern", "estrich rückbau", "estrich rueckbau",
                                    "remove screed")),
    Rate("screed",   "m2", 25, 48, ("estrich", "screed")),
    # --- walls ------------------------------------------------------------
    Rate("drywall",  "m2", 45, 82, ("trockenbau", "gipskarton", "rigips", "drywall")),
    Rate("painting", "m2", 5, 11, ("tapete entfern", "tapete lös", "strip wallpaper")),
    Rate("painting", "m2", 8, 20, ("tapezier", "tapete", "wallpaper")),
    # --- water damage specifics ------------------------------------------
    Rate("drying",   "tag", 15, 32, ("trocknungsgerät", "trocknungsgeraet", "bautrockner",
                                     "technisch trocknen", "drying unit", "dehumidifier day")),
    Rate("leak",     "h", 90, 145, ("leckageortung", "leckage", "rohrfreilegung",
                                    "leak detection", "leak location")),
    # --- trades by the hour ----------------------------------------------
    Rate("painting", "h", 45, 68, ("maler", "lackier", "painter")),
    Rate("carpentry", "h", 55, 84, ("zimmerer", "schreiner", "tischler", "carpenter", "joiner")),
    Rate("roofing",  "h", 60, 88, ("dachdecker", "roofer")),
    Rate("flooring", "h", 45, 70, ("bodenleger", "floor layer")),
    # --- vehicle ----------------------------------------------------------
    Rate("vehicle",  "stk", 400, 900, ("windschutzscheibe", "frontscheibe", "windshield",
                                       "windscreen")),
    Rate("vehicle",  "stk", 500, 1200, ("stoßfänger", "stossfaenger", "bumper")),
    Rate("vehicle",  "stk", 200, 650, ("seitenspiegel", "außenspiegel", "aussenspiegel",
                                       "wing mirror", "side mirror")),
    Rate("vehicle",  "stk", 100, 250, ("abschlepp", "towing", "tow truck")),
    Rate("vehicle",  "stk", 400, 1100, ("lackierung", "respray", "refinish")),
    Rate("vehicle",  "h", 110, 190, ("markengebunden", "vertragswerkstatt", "dealer workshop")),
    # --- overheads --------------------------------------------------------
    Rate("overhead", "pauschal", 30, 90, ("anfahrt", "fahrtkosten", "travel", "callout")),
    Rate("overhead", "stk", 150, 450, ("entsorgung", "container", "abfall", "disposal", "skip")),
    Rate("overhead", "m2", 3, 8, ("baustellenreinigung", "endreinigung", "reinigung",
                                  "site cleaning", "final clean")),
    Rate("overhead", "pauschal", 20, 90, ("kleinmaterial", "verbrauchsmaterial",
                                          "consumables", "sundries")),
    Rate("scaffold", "m2", 8, 20, ("gerüst", "geruest", "scaffold")),
)

GENERIC = Rate("unknown", "", 20, 120, ())


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().strip())


def match_rate(item: LineItem) -> Rate:
    text = _norm(item.description)
    best: tuple[int, Rate] | None = None
    for rate in RATES:
        for kw in rate.keywords:
            if kw in text and (best is None or len(kw) > best[0]):
                best = (len(kw), rate)
    return best[1] if best else GENERIC


def gross(net: float) -> float:
    return net * (1.0 + VAT_RATE)


def lookup(item: LineItem) -> Belief:
    """Gross-total belief for one line item."""
    rate = match_rate(item)
    qty = max(item.qty, 0.0)
    lo, hi = gross(rate.low * qty), gross(rate.high * qty)
    if lo <= 0 or hi <= lo:
        return Belief(median=max(gross(GENERIC.low * max(qty, 1.0)), 1.0),
                      sigma=0.6, source="pricebook:degenerate")
    median = math.sqrt(lo * hi)
    # Treat [lo, hi] as a ~90% interval: +/-1.645 sigma in log space.
    sigma = min(max((math.log(hi) - math.log(lo)) / (2 * 1.645), 0.12), 1.0)
    return Belief(median=median, sigma=sigma, source=f"pricebook:{rate.trade}")


def fallback(ctx: Context) -> Belief:
    return lookup(ctx.item)


def prompt_text() -> str:
    """The book as grounding text for the LLM valuation prompt.

    Rendered from RATES rather than duplicated in a prompt string, so the model and
    the deterministic fallback can never disagree about what the book says.
    """
    lines = [
        "PRICE BOOK — German trades 2025/26, NET per unit (EUR).",
        "What a claims expert would still sign off, not the cheapest quote.",
        "",
        f"{'trade':<10} {'unit':<9} {'low':>7} {'high':>7}  matches",
    ]
    for r in RATES:
        lines.append(
            f"{r.trade:<10} {r.unit:<9} {r.low:>7.0f} {r.high:>7.0f}  {r.keywords[0]}"
        )
    lines += [
        "",
        f"VAT: {VAT_RATE:.0%} USt is standard on trade work; quote NET, we add VAT downstream.",
        "Anfahrt, Entsorgung, Kleinmaterial and Baustellenreinigung are normal line items.",
        "Helper hours bill ~60-70% of the journeyman rate. Emergency callout surcharges of",
        "25-50% are legitimate when the damage description implies one.",
        "",
        "Inflations to catch: quantities exceeding what the damage description supports;",
        "a whole-room renovation billed for a localised stain; brand-new premium parts",
        "replacing worn ones; unexplained 'Sonderzuschlag'; the same work billed twice under",
        "two descriptions. Betterment (neu fuer alt) is normally reduced, not paid in full.",
    ]
    return "\n".join(lines)
