"""What the book does when it recognises nothing -- which is most of the time.

Game 2 priced all seven line items at EUR 58.30, the unit-blind default, and the
acceptance limit that came out of it (46.11) sat below almost every fair claim.
"""
from __future__ import annotations

import pytest

from c2f.core.models import LineItem
from c2f.estimate.pricebook import GENERIC, GENERIC_BY_UNIT, lookup, match_rate, unit_class

UNKNOWN = "no keyword in the book matches this text"


def item(unit: str, qty: float = 1.0, desc: str = UNKNOWN) -> LineItem:
    return LineItem(idx=1, description=desc, qty=qty, unit=unit)


def test_hrs_is_recognised_as_hours():
    """`hr`, `hour` and `hours` were mapped but `hrs` was not, and an unrecognised
    unit switches OFF the unit-compatibility check -- which is how an hourly line
    gets priced with a per-piece rate."""
    assert unit_class("hrs") == "h"


def test_unknown_item_is_priced_by_its_unit_not_a_flat_number():
    per_piece = lookup(item("pcs")).median
    per_hour = lookup(item("hrs")).median
    assert per_piece > 4 * 58.30, f"per-piece unknown still near the flat default: {per_piece}"
    assert per_piece != per_hour, "unit is being ignored again"
    assert lookup(item("pcs")).source == "pricebook:unknown:stk"


def test_unknown_scales_with_quantity():
    one, five = lookup(item("hrs", 1)).median, lookup(item("hrs", 5)).median
    assert five == pytest.approx(one * 5)


def test_wide_band_means_high_sigma():
    """Ignorance must show up as uncertainty, so the decision layer can price it."""
    assert lookup(item("pcs")).sigma > 0.5


def test_every_unit_in_the_book_has_a_generic_band():
    for rate in GENERIC_BY_UNIT.values():
        assert rate.low > 0 and rate.high > rate.low


def test_a_real_keyword_still_beats_the_generic():
    matched = match_rate(item("lm", desc="Sockelleisten erneuern"))
    assert matched is not GENERIC
    assert matched.trade == "flooring"
