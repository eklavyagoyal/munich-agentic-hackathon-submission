"""Turn an extracted case directory into a `Case`.

The invoice parser is deliberately STRICT. A parser that silently shifts item
indices produces a submission that looks entirely healthy and is scored as
garbage -- the quietest way to lose this tournament. Every failure here is loud.
"""
from __future__ import annotations

import csv
import io
import re
import shutil
import statistics
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from c2f.core.models import Case, LineItem


class ParseError(RuntimeError):
    pass


# "  1   Remove water-damaged laminate in living room      18   m2"
ROW = re.compile(
    r"^\s*(?P<pos>\d{1,3})\s+"
    r"(?P<desc>\S.*?\S)\s{2,}"
    # A dash in the qty or unit column is a lump-sum row -- game 1 position 3 was
    # printed "–   –" and dropping it failed contiguity, which cost the whole round.
    # Group separators happen: a 2,412.1 kWh row was dropped in game 17 because
    # this matched "2,412" and then choked on ".1". The last separator in the
    # token is the decimal one; _qty() below resolves which is which.
    r"(?P<qty>\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?|\d{1,6}(?:[.,]\d{1,3})?|[\u2013\u2014-])\s+"
    # Up to 12 chars: "pauschal" (8) and "Pauschale" (9) are on nearly every German
    # trade invoice, and at 6 they were dropped -- which the contiguity check below
    # then escalated into a total parse failure, i.e. a lost round.
    # One internal space, because "flat rate" is two words and this group forbade
    # spaces -- so every such row was dropped, became a placeholder, and could then
    # be priced by neither a keyword nor a model, a placeholder having no
    # description at all. 12 real rows across games 4, 5, 8 and 9. _UNITS already
    # maps "flat rate" to pauschal, so no unit-table change is needed.
    r"(?P<unit>[A-Za-zµ%][A-Za-z0-9µ²³%.]{0,11}(?:[ ][A-Za-z]{1,8})?|[\u2013\u2014-])\s*$"
)
DASHES = ("\u2013", "\u2014", "-")


def _qty(raw: str) -> float:
    """Parse a printed quantity. Handles 18, 3,5 (German decimal), 2,412.1 and 2.412,1.

    Rule: when both separators appear, the LAST one is the decimal point and the other
    groups thousands. With only one separator, three trailing digits mean thousands
    (2,412) and one or two mean a decimal (3,5).
    """
    t = raw.strip()
    if t in DASHES:
        return 1.0
    last_dot, last_comma = t.rfind("."), t.rfind(",")
    if last_dot >= 0 and last_comma >= 0:
        dec = "." if last_dot > last_comma else ","
        grp = "," if dec == "." else "."
        t = t.replace(grp, "").replace(dec, ".")
    elif last_dot >= 0 or last_comma >= 0:
        sep = "." if last_dot >= 0 else ","
        tail = t.split(sep)[-1]
        t = t.replace(sep, "") if len(tail) == 3 else t.replace(sep, ".")
    try:
        return float(t)
    except ValueError:
        return 1.0
STOP_WORDS = ("net", "plus vat", "total amount", "zwischensumme", "gesamtbetrag")
OCR_MAX_PAGES = 6


def _tsv_to_layout(raw: str) -> str:
    """Reconstruct line spacing from Tesseract TSV bounding boxes."""

    groups: dict[tuple[int, int, int, int], list[tuple[int, int, str]]] = {}
    try:
        reader = csv.DictReader(io.StringIO(raw), delimiter="\t")
        for row in reader:
            word = re.sub(r"\s+", " ", (row.get("text") or "").strip())
            if not word:
                continue
            key = tuple(int(row[name]) for name in (
                "page_num", "block_num", "par_num", "line_num"
            ))
            groups.setdefault(key, []).append(
                (int(row["left"]), int(row["height"]), word)
            )
    except (KeyError, TypeError, ValueError, csv.Error) as exc:
        raise ParseError(f"invalid Tesseract TSV: {type(exc).__name__}") from exc
    if not groups:
        raise ParseError("Tesseract TSV contained no words")

    lines: list[str] = []
    for key in sorted(groups):
        words = sorted(groups[key])
        # Approximate a monospace column from the median glyph height. Physical
        # gaps between the description, quantity, and unit then become the 2+
        # spaces the strict invoice regex expects.
        char_width = max(statistics.median(height for _, height, _ in words) * 0.45, 1.0)
        line = ""
        for left, _height, word in words:
            column = round(left / char_width)
            line += " " * max(1, column - len(line)) + word
        lines.append(line)
    return "\n".join(lines)


def _ocr_pdf(pdf: Path) -> str:
    """Bounded local OCR fallback for a valid PDF with no text layer.

    Rendering is capped at six 2500-pixel pages.  With a five-second deadline per
    Tesseract invocation the worst case stays inside the one-minute round budget,
    while ordinary one-page invoices complete much faster.  No network or model
    credential is involved.
    """

    pdfinfo = shutil.which("pdfinfo")
    renderer = shutil.which("pdftoppm")
    tesseract = shutil.which("tesseract")
    missing = [name for name, path in (
        ("pdfinfo", pdfinfo), ("pdftoppm", renderer), ("tesseract", tesseract)
    ) if path is None]
    if missing:
        raise ParseError(f"OCR unavailable; missing binaries: {', '.join(missing)}")

    info = subprocess.run(
        [pdfinfo, str(pdf)], capture_output=True, text=True, timeout=5
    )
    if info.returncode != 0:
        raise ParseError(f"pdfinfo exit {info.returncode}")
    match = re.search(r"^Pages:\s*(\d+)\s*$", info.stdout, re.MULTILINE)
    if match is None:
        raise ParseError("pdfinfo did not report a page count")
    pages = int(match.group(1))
    if not 1 <= pages <= OCR_MAX_PAGES:
        raise ParseError(f"OCR page count {pages} outside supported range 1..{OCR_MAX_PAGES}")

    with tempfile.TemporaryDirectory(prefix="c2f-ocr-") as raw_temp:
        temp = Path(raw_temp)
        prefix = temp / "page"
        rendered = subprocess.run(
            [renderer, "-f", "1", "-l", str(pages), "-scale-to", "2500",
             "-png", str(pdf), str(prefix)],
            capture_output=True, text=True, timeout=12,
        )
        if rendered.returncode != 0:
            raise ParseError(f"pdftoppm exit {rendered.returncode}")
        images = sorted(temp.glob("page-*.png"))
        if len(images) != pages:
            raise ParseError(f"OCR renderer produced {len(images)}/{pages} pages")

        text: list[str] = []
        for image in images:
            result = subprocess.run(
                [tesseract, str(image), "stdout", "-l", "eng", "--psm", "4", "tsv"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                raise ParseError(f"tesseract exit {result.returncode}")
            text.append(_tsv_to_layout(result.stdout))
    output = "\n".join(text)
    if not output.strip():
        raise ParseError("OCR produced no text")
    return output


def pdf_to_text(pdf: Path) -> str:
    exe = shutil.which("pdftotext")
    if exe is None:
        raise ParseError("pdftotext not on PATH (brew install poppler)")
    proc = subprocess.run([exe, "-layout", str(pdf), "-"],
                          capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        raise ParseError(f"pdftotext exit {proc.returncode}: {proc.stderr.strip()[:200]}")
    if proc.stdout.strip():
        return proc.stdout
    try:
        return _ocr_pdf(pdf)
    except (OSError, subprocess.SubprocessError, ParseError) as exc:
        raise ParseError(f"PDF has no text layer and OCR failed: {exc}") from exc


def parse_line_items(text: str) -> tuple[LineItem, ...]:
    items: list[LineItem] = []
    for raw in text.splitlines():
        low = raw.strip().lower()
        if not low or any(low.startswith(w) for w in STOP_WORDS):
            continue
        m = ROW.match(raw)
        if not m:
            continue
        qty_raw, unit_raw = m["qty"], m["unit"].strip()
        # "one of it, no unit printed" -- the same shape the price book already
        # prices as a lump sum, so this reuses existing handling rather than
        # inventing a second notion of quantity-less work.
        qty = _qty(qty_raw)
        unit = "pauschal" if unit_raw in DASHES else unit_raw
        items.append(LineItem(idx=0, pos=m["pos"], description=m["desc"].strip(),
                              qty=qty, unit=unit))

    ceiling = _position_ceiling(text)
    try:
        out = validate_items(items, require_contiguous=True)
        # Contiguity cannot see a missing LAST row: 1..19 is perfectly contiguous even
        # when the invoice printed 20. Game 17 lost position 20 that way and submitted
        # nothing for it -- silently, on our largest-income round. So compare against
        # the printed positions even on the success path.
        if ceiling > len(out):
            return validate_items(_fill_gaps(items, ceiling), require_contiguous=False)
        return out
    except ParseError:
        # A row we cannot read must never cost the round. Omitted line items score
        # as charge_price=0 and acceptance_limit=0, which rejects every fair claim
        # AND pays the penalty on it -- strictly worse than a rough bid. So fill
        # the gaps with lump-sum placeholders and submit a number for every
        # position that was printed.
        return validate_items(_fill_gaps(items, ceiling), require_contiguous=False)


def _position_ceiling(text: str) -> int:
    """Highest N such that every position 1..N is printed at the start of a line.

    Filling only up to the highest row we *parsed* silently shrinks the invoice
    when the tail rows fail: mangling every unit on the real case 1 left 3 items
    out of 18, and the missing 15 would score 0/0. The printed numbers are still
    there even when the rest of the row is unreadable, so they give us N.

    A contiguous run from 1 is what makes this safe: a stray number (an address
    line, a date, a phone number) does not extend the run, so we never invent
    positions past the end of the invoice.
    """
    seen = {int(m.group(1)) for m in re.finditer(r"^\s*(\d{1,3})\s", text, re.M)}
    n = 0
    while n + 1 in seen:
        n += 1
    return n


def _fill_gaps(items: list[LineItem], ceiling: int = 0) -> list[LineItem]:
    """Insert a placeholder for every printed position we failed to parse.

    Also drops duplicate positions, keeping the first. The duplicate check in
    validate_items runs on both paths, so without this the fallback would raise
    the very exception it exists to absorb -- and a raise here is a round that
    submits nothing, which is the worst outcome in the game.
    """
    seen: set[str] = set()
    deduped = []
    for i in items:
        if i.pos in seen:
            continue
        seen.add(i.pos)
        deduped.append(i)
    items = deduped
    nums = sorted({int(i.pos) for i in items if i.pos.isdigit()})
    top = max([ceiling] + nums) if (nums or ceiling) else 0
    if not top:
        return items
    have = set(nums)
    filled = list(items) + [
        LineItem(idx=0, pos=str(n), description="(row not parsed)",
                 qty=1.0, unit="pauschal")
        for n in range(1, top + 1) if n not in have
    ]
    return sorted(filled, key=lambda i: int(i.pos) if i.pos.isdigit() else 10**6)


def validate_items(items: list[LineItem], *, require_contiguous: bool) -> tuple[LineItem, ...]:
    """Re-index to our own contiguous ordinal and check for dropped rows.

    `require_contiguous` is for the regex path, where a non-matching row is
    silently skipped and the printed positions are the only evidence. The model
    path sees the whole document at once, so odd real-world numbering ("2a",
    starting at 10) is accepted there -- but duplicates never are.
    """
    if not items:
        raise ParseError("no line items parsed -- refusing to submit a blank invoice")
    printed = [i.pos for i in items]
    if len(set(printed)) != len(printed):
        raise ParseError(f"duplicate line item positions: {printed}")
    if require_contiguous:
        try:
            nums = [int(p) for p in printed]
        except ValueError as e:
            raise ParseError(f"non-numeric positions on the regex path: {printed}") from e
        if nums[0] != 1:
            raise ParseError(f"line items start at {nums[0]}, expected 1 -- rows were dropped")
        if nums != list(range(1, len(nums) + 1)):
            raise ParseError(f"line item positions are not contiguous: {nums}")
    return tuple(
        LineItem(idx=n, description=i.description, qty=i.qty, unit=i.unit,
                 pos=i.pos, trade=i.trade, vat_rate=i.vat_rate)
        for n, i in enumerate(items, start=1))


def _read(path: Path | None) -> str:
    return path.read_text(encoding="utf-8", errors="replace").strip() if path else ""


@dataclass
class CaseFiles:
    policy: str = ""
    damage: str = ""
    invoice_text: str = ""
    images: list[Path] = field(default_factory=list)


def read_files(files: list[Path]) -> CaseFiles:
    """Filenames are documented as policy.txt / description.txt, but do not bet
    the round on it -- fall back to keyword sniffing, then to length."""
    cf = CaseFiles()
    for path in sorted(files):
        low = path.name.lower()
        if low.endswith(".pdf"):
            cf.invoice_text += pdf_to_text(path) + "\n"
        elif low.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
            cf.images.append(path)
        elif low.endswith((".txt", ".md")):
            body = path.read_text(encoding="utf-8", errors="replace")
            if "polic" in low or "versicher" in low:
                cf.policy += body + "\n"
            elif "descr" in low or "damage" in low or "schaden" in low:
                cf.damage += body + "\n"
            elif len(body) > len(cf.policy):
                cf.policy += body + "\n"
            else:
                cf.damage += body + "\n"
    if not cf.invoice_text.strip():
        raise ParseError("no invoice text extracted -- check the PDF text layer")
    return cf


def build_case(case_id: str, files: list[Path],
               items: tuple[LineItem, ...] | None = None) -> Case:
    """Assemble a Case. Pass `items` from the LLM extractor; omit for the regex."""
    cf = read_files(files)
    if items is None:
        items = parse_line_items(cf.invoice_text)
    return Case(case_id=case_id, policy_text=cf.policy.strip(),
                damage_description=cf.damage.strip(), items=items,
                image_paths=tuple(str(p) for p in cf.images))
