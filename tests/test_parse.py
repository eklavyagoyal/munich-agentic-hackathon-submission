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


def test_long_units_are_not_dropped():
    """`pauschal` (8 chars) and `Pauschale` (9) appear on nearly every German trade
    invoice. Dropping the row would trip the contiguity check and fail the whole
    case -- turning one unparsed unit into a lost round."""
    txt = """
POS  BESCHREIBUNG                                        QTY   UNIT
1    Wasserschaden-Laminat entfernen, Wohnzimmer         18    m2
2    Sockelleisten erneuern                              25    lm
3    Estrich technisch trocknen                          14    Tag
4    Anfahrtspauschale                                   1     pauschal
5    Kleinmaterial                                       1     Pauschale
6    Entsorgung Altmaterial                              1     Stk
Netto
"""
    items = parse_line_items(txt)
    assert [i.idx for i in items] == [1, 2, 3, 4, 5, 6]
    assert items[3].unit == "pauschal"
    assert items[4].unit == "Pauschale"


def test_a_description_word_is_still_not_mistaken_for_a_unit():
    """Widening the unit pattern must not let a trailing description word match."""
    txt = """
POS  BESCHREIBUNG                                        QTY   UNIT
1    Laminat entfernen                                   18    m2
"""
    items = parse_line_items(txt)
    assert len(items) == 1 and items[0].unit == "m2"
    assert items[0].description == "Laminat entfernen"
