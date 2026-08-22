"""Snap an unrecognised line item onto the nearest trade -- MEASURED NEGATIVE, unused.

RESULT FIRST: this does not pay, at any threshold. Nothing calls it. It is kept
because the measurement is worth more than the code, and because the scaffolding
(unit gate, keyword index, evaluation harness) is what an embeddings retry would
need.

Swept over 162 unknown items across games 1-20, comparing each fuzzy-matched band
against the unit-blind generic band, scored by distance to the item's proven bracket:

    thresh  claimed  better  worse  same
      0.42       20       6      9     3
      0.50       12       5      5     1     <- best case, a wash
      0.55        5       1      3     1
      0.60        2       1      0     1     <- touches 2 items
      0.65        0       0      0     0

WHY IT FAILS, because the reason generalises. The pipeline this idea comes from
mapped unstructured German product text onto 1,738 predefined features, and its
taxonomy DENSELY COVERED its domain -- a screw's material really is one of the
allowed values. Ours is 17 trades against an open universe of claim line items: 142
unknown items across 122 distinct descriptions, where the correct trade frequently is
not in the book at all. Lexical similarity to a taxonomy that lacks the answer does
not abstain, it returns a confident wrong neighbour, and a wrong trade prices the item
on the wrong band.

It does agree with match_rate wherever match_rate has an answer (flooring, scaffold,
plumbing, overhead, hvac all confirmed), and it correctly abstains on obvious
non-trades. So the matcher is not broken. The taxonomy is too coarse for the job, and
that is not fixable by tuning a cutoff.

Original design notes follow.

Snap an unrecognised line item onto the nearest trade in the price book.

The measured problem this attacks: 142 unknown line items across 122 DISTINCT
descriptions. The vocabulary is open, so no keyword table closes it -- adding the
59th, 60th, 61st rate chases a tail that does not end. Every one of those items gets
the unit-blind generic band instead, which is how 31 of 39 items in one case all
received the same price.

The approach is lifted from a taxonomy-normalisation pipeline that mapped
unstructured German product text onto 1,738 predefined features: a deterministic
waterfall, with a fuzzy layer for whatever the exact layers miss. That pipeline used
Aho-Corasick and MiniLM embeddings because it had 3.1M products and a large
taxonomy. Ours is 228 keywords over 17 trades, and the descriptions are one line
each, so character trigrams and a dot product do the same job with the standard
library and no model download. Cost is microseconds, which matters because this has
to run in tier 1 where the LLM cannot go.

DELIBERATELY SUBORDINATE. It fires ONLY when match_rate found nothing, so an exact
keyword match always wins and this can add coverage but never override a known
answer. A wrong trade would price an item on the wrong band, so the threshold is set
high and the rule that consumes this loads SHADOW until tools/score.py says
otherwise.
"""
from __future__ import annotations

import math
from collections import Counter
from functools import lru_cache

from c2f.core.models import LineItem
from c2f.estimate.pricebook import RATES, Rate, unit_class

# Below this cosine, we have no opinion. Chosen high on purpose: the cost of pricing
# an item on the wrong trade's band is a mispriced acceptance limit, and the
# fallback (the unit-aware generic band) is a defensible answer rather than a bad one.
MIN_SIMILARITY = 0.42

# German folding, so "gerüst" and "geruest" reach the same trigrams. The book already
# lists such pairs by hand, which is a sign the matcher should do it instead.
_FOLD = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
                       "Ä": "ae", "Ö": "oe", "Ü": "ue"})


def _grams(text: str) -> Counter:
    """Character trigrams of a folded, alphanumeric-only string.

    Character n-grams rather than words because trade text is compound-heavy and
    inflected: "Sockelleisten" should reach "sockelleiste", and "insulation removal"
    should reach "removal". Word tokens miss both.
    """
    t = text.translate(_FOLD).lower()
    t = "".join(c if c.isalnum() else " " for c in t)
    t = f" {' '.join(t.split())} "
    if len(t) < 3:
        return Counter()
    return Counter(t[i:i + 3] for i in range(len(t) - 2))


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    small, large = (a, b) if len(a) <= len(b) else (b, a)
    dot = sum(n * large[g] for g, n in small.items() if g in large)
    if not dot:
        return 0.0
    na = math.sqrt(sum(n * n for n in a.values()))
    nb = math.sqrt(sum(n * n for n in b.values()))
    return dot / (na * nb)


@lru_cache(maxsize=1)
def _keyword_index() -> tuple[tuple[Rate, str, Counter], ...]:
    """Trigram profile per (rate, keyword). Built once; the book is static."""
    return tuple((rate, kw, _grams(kw))
                 for rate in RATES for kw in rate.keywords if len(kw) >= 4)


def best_rate(item: LineItem) -> tuple[Rate, float] | None:
    """Nearest trade by trigram cosine, or None when nothing is close enough.

    Honours the same unit gate as match_rate: a rate quoted per piece must not price
    a line billed per hour. That check is not cosmetic -- ignoring it once priced a
    2.5-hour windshield fitting at the per-unit windshield rate, about 5x the truth.
    """
    profile = _grams(item.description)
    if not profile:
        return None
    want = unit_class(item.unit)
    best: tuple[Rate, float] | None = None
    for rate, _kw, kw_profile in _keyword_index():
        if want and rate.unit and unit_class(rate.unit) != want:
            continue
        score = _cosine(profile, kw_profile)
        if best is None or score > best[1]:
            best = (rate, score)
    if best is None or best[1] < MIN_SIMILARITY:
        return None
    return best
