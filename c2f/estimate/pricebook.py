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
    # False for rates that are real but unrepresentative of "some unknown line billed
    # per piece": _generic_by_unit takes min(low)/max(high) over the unit, so one
    # cheap rate re-prices every unmatched item of that unit in every future game.
    # Measured: adding service rows without this moved four games by -7,497 EUR;
    # with it, +2,711.
    in_generic: bool = True


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
    # --- water damage: drying --------------------------------------------
    # Per-day unit covers "14 Tage Trocknung"; per-stk covers "2 Stk Bautrockner".
    # Longer keywords (room drying, condensation dryer) beat these on total-job lines.
    Rate("drying",   "tag", 15, 32, ("trocknungsgerät", "trocknungsgeraet", "bautrockner",
                                     "technisch trocknen", "drying unit", "dehumidif",
                                     "trocknung", "drying")),
    # Total drying-service job lines (not per day / not per piece of kit).
    # Game 5 items 10-11: t >= 366-510; generic:stk gave a=93, these give ~274-385.
    Rate("drying",   "stk", 200, 500, ("condensation dryer", "kondensationstrockner",
                                       "drying period rental", "trocknermiete")),
    Rate("drying",   "stk", 250, 650, ("room drying", "technische trocknung",
                                       "technical drying")),
    # --- water damage: leak detection ------------------------------------
    Rate("leak",     "h", 90, 145, ("leckageortung", "leckage", "rohrfreilegung",
                                    "leak detection", "leak location")),
    # Per-job call-outs. Longer keywords beat "leak detection" above.
    # Game 5 items 1-2: t >= 402-450; generic:stk gave a=239, these give ~309-155.
    Rate("leak",     "stk", 200, 600, ("leak detection call-out", "electro-acoustic",
                                       "leckortung pauschal")),
    Rate("leak",     "stk", 100, 300, ("moisture measurement", "feuchtemessung",
                                       "moisture check")),
    # --- water damage: plumbing flat jobs --------------------------------
    # Pipe access/repair billed per job rather than per hour.
    # Game 5 items 5-8: t >= 247-600; generic:stk gave a=239-44, these give ~191-64.
    Rate("plumbing", "stk", 120, 380, ("pipe run", "pipe freeing", "freeing the affected",
                                       "rohrfreilegung")),
    Rate("plumbing", "stk", 150, 420, ("confirmed leak", "pipe repair", "repair of the leak",
                                       "copper supply pipe")),
    Rate("plumbing", "stk", 80, 250, ("copper pipe section", "transition fittings",
                                      "pipe section and", "replacement pipe")),
    Rate("plumbing", "stk", 80, 200, ("pipe insulation", "rohriso", "insulation removal"),
         in_generic=False),
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
    # --- electronics (power-surge cases 2, 4, 6) -------------------------
    Rate("electronics", "stk", 300, 1200, ("television", "fernseher", "tv set",
                                           "flat screen tv", "smart tv")),
    Rate("electronics", "stk", 200, 800, ("speaker system", "lautsprecher", "soundbar",
                                          "loudspeaker system")),
    Rate("electronics", "stk", 150, 600, ("av receiver", "hifi receiver",
                                          "audio receiver", "heimkinoreceiver")),
    Rate("electronics", "stk", 60, 250, ("router", "netzwerkgerät", "network device")),
    Rate("electronics", "stk", 200, 700, ("dvd player", "blu-ray", "media player")),
    Rate("electronics", "stk", 10, 50, ("hdmi cable", "hdmi-kabel", "remote control",
                                        "fernbedienung", "mains plug", "power lead"),
         in_generic=False),
    # --- furniture & carpentry flat jobs ----------------------------------
    # Game 5 items 13-16: t >= 150-400.
    Rate("carpentry", "stk", 60, 180, ("wooden kitchen table", "water-damaged wooden",
                                       "kitchen table removal", "furniture removal transport")),
    Rate("carpentry", "stk", 180, 480, ("replacement table", "ersatztisch",
                                        "supply of replacement", "kitchen table replacement")),
    Rate("carpentry", "pauschal", 80, 260, ("delivery and assembly", "lieferung und montage",
                                            "table assembly", "furniture assembly",
                                            "assembly of the replacement")),
    Rate("overhead", "stk", 50, 180, ("cleaning of the installation", "area cleaning",
                                      "reinigung der arbeitsstelle")),
    # --- overheads --------------------------------------------------------
    Rate("overhead", "pauschal", 30, 90, ("anfahrt", "fahrtkosten", "travel", "callout")),
    Rate("overhead", "stk", 150, 450, ("entsorgung", "container", "abfall", "disposal", "skip")),
    Rate("overhead", "m2", 3, 8, ("baustellenreinigung", "endreinigung", "reinigung",
                                  "site cleaning", "final clean")),
    Rate("overhead", "pauschal", 20, 90, ("kleinmaterial", "verbrauchsmaterial",
                                          "consumables", "sundries")),
    Rate("scaffold", "m2", 8, 20, ("gerüst", "geruest", "scaffold")),
    # --- services (small per-item lines, in_generic=False) ---------------
    # Cheap lines that must not drag the unknown:stk band from 60-1200 downward.
    # Measured: without in_generic=False these rows moved four games by -7,497 EUR.
    Rate("services", "stk", 15, 50, ("vehicle costs", "fahrtkosten", "anfahrt"),
         in_generic=False),
    Rate("services", "stk", 10, 60, ("shipping", "versand", "lieferung"),
         in_generic=False),
    Rate("services", "stk", 70, 200, ("diagnostic", "diagnose", "gutachten",
                                      "surge-failure report", "inspection report"),
         in_generic=False),
)

GENERIC = Rate("unknown", "", 20, 120, ())


def _generic_by_unit() -> dict[str, Rate]:
    """The unknown-item band per unit, taken from the book's own full support.

    A unit-blind default priced game 2 at EUR 58.30 for every one of seven line
    items -- the same number a single-item test case got -- because no keyword
    matched. It is the wrong shape of guess: we do not know what the work is, but
    we do know whether it is billed per hour, per square metre or per piece, and
    the book already says what each of those costs. Per piece that default was
    5.5x too low, which set the acceptance limit below almost every fair claim.

    Full support (min low, max high) rather than an average, because the honest
    statement is "it could be any of these": the wide band raises sigma, and the
    decision layer prices that uncertainty instead of us pretending to precision.
    """
    by: dict[str, list[Rate]] = {}
    for r in RATES:
        if r.unit and r.in_generic:
            by.setdefault(unit_class(r.unit), []).append(r)
    return {u: Rate(f"unknown:{u}", u, min(r.low for r in rs), max(r.high for r in rs), ())
            for u, rs in by.items()}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().strip())


# Unit synonyms, so a rate quoted per m2 is not applied to a line billed per hour.
_UNITS: dict[str, str] = {
    "m2": "m2", "m²": "m2", "qm": "m2", "sqm": "m2",
    "m3": "m3", "m³": "m3", "cbm": "m3",
    "lm": "lm", "lfm": "lm", "m": "lm", "rm": "lm",
    "h": "h", "std": "h", "stunde": "h", "stunden": "h", "hour": "h", "hours": "h", "hr": "h",
    "hrs": "h", "std.": "h", "akh": "h",
    "tag": "tag", "tage": "tag", "day": "tag", "days": "tag", "d": "tag",
    "stk": "stk", "st": "stk", "stück": "stk", "stueck": "stk", "pcs": "stk",
    "pc": "stk", "piece": "stk", "ea": "stk",
    "pauschal": "pauschal", "psch": "pauschal", "pausch": "pauschal",
    "pausch.": "pauschal", "lump": "pauschal", "flat": "pauschal",
    "flat rate": "pauschal", "flat-rate": "pauschal", "flatrate": "pauschal",
}


def unit_class(unit: str) -> str:
    """Canonical unit, or "" when we do not recognise it (which matches anything)."""
    return _UNITS.get(_norm(unit).rstrip("."), "")


GENERIC_BY_UNIT: dict[str, Rate] = _generic_by_unit()


def match_rate(item: LineItem) -> Rate:
    """Longest keyword match whose unit is COMPATIBLE with the line item's.

    The unit check is not cosmetic. Without it a "Windschutzscheibe Einbau, 2.5 h"
    line matched the per-Stk windshield rate and was priced at 400-900 x 2.5 -- about
    5x the truth. Overestimating is the expensive direction on both sides at once: we
    charge into the fraud zone (earning nothing) and we accept fraud as insurer.

    A unit mismatch returns GENERIC, so PricebookPrior abstains and the LLM prior --
    which can read that the line is labour, not a part -- handles it instead. That is
    the correct division of labour, not a silent wrong number.
    """
    text = _norm(item.description)
    want = unit_class(item.unit)
    best: tuple[int, Rate] | None = None
    for rate in RATES:
        # "" on either side means "no opinion about units", so it stays compatible.
        if want and rate.unit and unit_class(rate.unit) != want:
            continue
        for kw in rate.keywords:
            if kw in text and (best is None or len(kw) > best[0]):
                best = (len(kw), rate)
    return best[1] if best else GENERIC


def gross(net: float) -> float:
    return net * (1.0 + VAT_RATE)


def lookup(item: LineItem) -> Belief:
    """Gross-total belief for one line item."""
    rate = match_rate(item)
    if rate is GENERIC:
        # No keyword matched, or the units were incompatible. Fall back to what the
        # book says about this unit rather than to a unit-blind flat number.
        rate = GENERIC_BY_UNIT.get(unit_class(item.unit), GENERIC)
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
