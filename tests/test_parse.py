"""A parser that silently shifts item indices produces a submission that looks
entirely healthy and is scored as garbage. Every failure here must be loud."""
import shutil
import subprocess
from pathlib import Path

import pytest

from c2f.ingest.parse import ParseError, parse_line_items, pdf_to_text

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


def test_dropped_leading_row_is_filled_not_raised():
    """The quiet killer: rows 1-2 fail to match and row 3 parses alone. Raising
    here cost us game 1 -- an omitted line item scores charge 0 / limit 0, which
    rejects every fair claim and pays the penalty on it. A rough bid beats that,
    so the gap is filled and every printed position gets a number."""
    items = parse_line_items(" 3    Replace skirting boards      25   lm")
    assert [i.pos for i in items] == ["1", "2", "3"]
    assert [i.idx for i in items] == [1, 2, 3]
    assert items[2].qty == 25
    assert items[0].description == "(row not parsed)"


def test_gap_in_positions_is_filled():
    items = parse_line_items(" 1  A thing   5  m2\n 3  Another one   2  lm")
    assert [i.pos for i in items] == ["1", "2", "3"]
    assert items[1].description == "(row not parsed)"
    assert items[1].unit == "pauschal"   # lump sum: priced, not skipped


def test_dash_quantity_is_a_lump_sum_row():
    """Game 1 position 3 was printed with en-dashes for qty and unit. It dropped,
    contiguity failed, and the round submitted nothing."""
    items = parse_line_items(
        " 1  Emergency call-out            \u2013   \u2013\n"
        " 2  Replace skirting boards      25   lm")
    assert [i.pos for i in items] == ["1", "2"]
    assert items[0].qty == 1.0
    assert items[0].unit == "pauschal"
    assert items[0].description == "Emergency call-out"


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


def test_duplicate_positions_do_not_lose_the_round():
    """The fallback must absorb duplicates too. It re-runs validate_items, whose
    duplicate check ignores require_contiguous -- so an unguarded fallback would
    raise the exception it exists to absorb, and submit nothing."""
    items = parse_line_items(
        " 1  A thing        5  m2\n"
        " 1  A thing again  2  lm\n"
        " 3  Third thing    1  pcs")
    assert [i.pos for i in items] == ["1", "2", "3"]
    assert items[0].description == "A thing"          # first wins
    assert items[1].description == "(row not parsed)"  # gap still filled


def test_empty_text_layer_uses_ocr(monkeypatch, tmp_path):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"synthetic")
    monkeypatch.setattr(
        "c2f.ingest.parse.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout="", stderr=""),
    )
    monkeypatch.setattr(
        "c2f.ingest.parse._ocr_pdf",
        lambda path: " 1  Synthetic repair   1  pcs\n",
    )
    assert "Synthetic repair" in pdf_to_text(pdf)


def test_image_only_synthetic_invoice_is_ocr_readable(tmp_path):
    """Rasterise the hand-written fixture, remove its text layer, then OCR it."""
    if not all(shutil.which(name) for name in ("pdftoppm", "pdfinfo", "tesseract")):
        pytest.skip("local OCR binaries unavailable")
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow unavailable for synthetic scan construction")

    source = Path(__file__).resolve().parents[1] / "fixtures/synth/invoices.pdf"
    prefix = tmp_path / "source"
    rendered = subprocess.run(
        [shutil.which("pdftoppm"), "-f", "1", "-l", "1", "-scale-to", "2500",
         "-png", str(source), str(prefix)],
        capture_output=True, text=True, timeout=12,
    )
    assert rendered.returncode == 0
    image_path = next(tmp_path.glob("source-*.png"))
    scanned = tmp_path / "scanned.pdf"
    with Image.open(image_path) as image:
        image.convert("RGB").save(scanned, "PDF", resolution=150)

    expected = parse_line_items(pdf_to_text(source))
    items = parse_line_items(pdf_to_text(scanned))
    assert [item.pos for item in items] == [item.pos for item in expected]
    assert [item.qty for item in items] == [item.qty for item in expected]
    assert all(item.description != "(row not parsed)" for item in items)
