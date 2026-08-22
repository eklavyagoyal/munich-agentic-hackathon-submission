"""The swappable seams: extraction, the API, and the parser hardening that
protects both. These are what let one pipeline serve every module.
"""
import asyncio
from pathlib import Path

import pytest

from c2f.core.models import Decision, LineItem, Submission
from c2f.ingest.parse import ParseError, read_files, validate_items
from c2f.submit.client import LiveApi, MockApi

ROOT = Path(__file__).resolve().parent.parent


def test_printed_position_survives_next_to_our_ordinal():
    """The payload may be keyed by the printed position; our ordinal exists only
    for ordering and drop detection."""
    raw = [LineItem(idx=0, description="a", qty=1, unit="m2", pos="10"),
           LineItem(idx=0, description="b", qty=1, unit="m2", pos="11a")]
    items = validate_items(raw, require_contiguous=False)
    assert [i.idx for i in items] == [1, 2]
    assert [i.pos for i in items] == ["10", "11a"]


def test_duplicate_positions_always_rejected():
    raw = [LineItem(idx=0, description="a", qty=1, unit="m2", pos="1"),
           LineItem(idx=0, description="b", qty=1, unit="m2", pos="1")]
    with pytest.raises(ParseError, match="duplicate"):
        validate_items(raw, require_contiguous=False)


def test_odd_numbering_allowed_on_the_model_path_only():
    raw = [LineItem(idx=0, description="a", qty=1, unit="m2", pos="2a")]
    assert validate_items(raw, require_contiguous=False)[0].pos == "2a"
    with pytest.raises(ParseError):
        validate_items(raw, require_contiguous=True)


def test_dropped_leading_row_caught_on_the_regex_path():
    raw = [LineItem(idx=0, description="a", qty=1, unit="m2", pos="3")]
    with pytest.raises(ParseError, match="expected 1"):
        validate_items(raw, require_contiguous=True)


def test_read_files_sniffs_when_filenames_are_unexpected(tmp_path):
    """Filenames are documented but not guaranteed; do not bet a round on them."""
    src = ROOT / "fixtures" / "synth" / "invoices.pdf"
    if not src.exists():
        pytest.skip("synth invoice fixture not present")
    (tmp_path / "versicherungsbedingungen.txt").write_text("policy body " * 40)
    (tmp_path / "schadenmeldung.txt").write_text("pipe broke")
    (tmp_path / "rechnung.pdf").write_bytes(src.read_bytes())

    cf = read_files(list(tmp_path.iterdir()))
    assert "policy body" in cf.policy      # matched on "versicher"
    assert "pipe broke" in cf.damage       # matched on "schaden"
    assert cf.invoice_text.strip()         # found by extension, not by name


def test_corrupt_pdf_fails_loudly(tmp_path):
    """A corrupt archive must never degrade into a blank invoice."""
    (tmp_path / "invoices.pdf").write_bytes(b"%PDF-1.4\nnot really a pdf")
    with pytest.raises(ParseError):
        read_files(list(tmp_path.iterdir()))


def test_extractor_falls_back_to_regex_without_a_backend():
    from c2f.ingest.extract_llm import extract_items

    text = " 1  Laminat verlegen        18   m2\n 2  Anfahrtspauschale     1   pauschal"
    items = asyncio.run(extract_items(text))
    assert [i.unit for i in items] == ["m2", "pauschal"]


def test_live_api_dry_run_never_posts():
    api = LiveApi(team_key="dummy", dry_run=True)
    sub = Submission("case-1", 1, (Decision(1, 10.0, 12.0, True, None),))
    r = api.submit(sub)
    assert r.ok and "dry run" in r.detail


def test_live_api_missing_key_fails_immediately_not_after_polling():
    """A missing key is a config error, not a transient one. Swallowing it into
    the retry loop burned 20s of a 60s round before telling anyone."""
    import time
    t0 = time.monotonic()
    with pytest.raises(RuntimeError, match="TEAM_API_KEY"):
        LiveApi(team_key="").fetch_key("case-1")
    assert time.monotonic() - t0 < 1.0


def test_mock_api_read_back_matches_what_was_sent():
    api = MockApi(keys={"c": "k"})
    sub = Submission("c", 1, (Decision(1, 10.0, 12.0, True, None),))
    api.submit(sub)
    assert api.get_submission("c")["items"] == sub.payload()["items"]
