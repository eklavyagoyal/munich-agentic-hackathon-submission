"""A parser that silently shifts item indices produces a submission that looks
entirely healthy and is scored as garbage. Every failure here must be loud."""
import pytest

from c2f.ingest.parse import ParseError, parse_line_items

GOOD = """
LINE ITEMS
POS.  DESCRIPTION                                           QTY  UNIT
 1    Remove water-damaged laminate in living room           18   m2
 2    New installation of laminate incl. sound insulation    18   m2
 3    Replace skirting boards                                25   lm
Net
plus VAT
Total amount
"""


def test_parses_all_rows():
    items = parse_line_items(GOOD)
    assert [i.idx for i in items] == [1, 2, 3]
    assert [i.unit for i in items] == ["m2", "m2", "lm"]
    assert items[0].qty == 18.0
    assert items[2].description == "Replace skirting boards"


def test_totals_are_not_line_items():
    assert len(parse_line_items(GOOD)) == 3


def test_blank_invoice_refused():
    with pytest.raises(ParseError, match="no line items"):
        parse_line_items("nothing to see here")


def test_dropped_leading_row_is_caught():
    """The quiet killer: rows 1-2 fail to match, row 3 parses, and a single
    item passes a contiguity check trivially."""
    with pytest.raises(ParseError, match="expected 1"):
        parse_line_items(" 3    Replace skirting boards      25   lm")


def test_gap_in_positions_is_caught():
    with pytest.raises(ParseError, match="contiguous"):
        parse_line_items(" 1  A thing   5  m2\n 3  Another one   2  lm")


def test_decimal_quantities():
    items = parse_line_items(" 1  Drying equipment rental    3,5  d")
    assert items[0].qty == pytest.approx(3.5)
