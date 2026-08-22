"""Turn an extracted case directory into a `Case`.

The invoice parser is deliberately STRICT. A parser that silently shifts item
indices produces a submission that looks entirely healthy and is scored as
garbage -- the quietest way to lose this tournament. Every failure here is loud.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from c2f.core.models import Case, LineItem


class ParseError(RuntimeError):
    pass


# "  1   Remove water-damaged laminate in living room      18   m2"
ROW = re.compile(
    r"^\s*(?P<pos>\d{1,3})\s+"
    r"(?P<desc>\S.*?\S)\s{2,}"
    r"(?P<qty>\d{1,6}(?:[.,]\d{1,3})?)\s+"
    r"(?P<unit>[A-Za-zµ%][A-Za-z0-9µ²³%.]{0,5})\s*$"
)
STOP_WORDS = ("net", "plus vat", "total amount", "zwischensumme", "gesamtbetrag")


def pdf_to_text(pdf: Path) -> str:
    exe = shutil.which("pdftotext")
    if exe is None:
        raise ParseError("pdftotext not on PATH (brew install poppler)")
    proc = subprocess.run([exe, "-layout", str(pdf), "-"],
                          capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        raise ParseError(f"pdftotext exit {proc.returncode}: {proc.stderr.strip()[:200]}")
    return proc.stdout


def parse_line_items(text: str) -> tuple[LineItem, ...]:
    items: list[LineItem] = []
    for raw in text.splitlines():
        low = raw.strip().lower()
        if not low or any(low.startswith(w) for w in STOP_WORDS):
            continue
        m = ROW.match(raw)
        if not m:
            continue
        qty = float(m["qty"].replace(",", "."))
        items.append(LineItem(idx=int(m["pos"]), description=m["desc"].strip(),
                              qty=qty, unit=m["unit"].strip()))

    if not items:
        raise ParseError("no line items parsed -- refusing to submit a blank invoice")

    positions = [i.idx for i in items]
    if positions[0] != 1:
        raise ParseError(
            f"line items start at position {positions[0]}, expected 1 -- rows were dropped")
    if positions != list(range(1, len(positions) + 1)):
        # Non-contiguous positions mean we dropped or duplicated a row. Every
        # subsequent price would land on the wrong item.
        raise ParseError(f"line item positions are not contiguous: {positions}")
    return tuple(items)


def _read(path: Path | None) -> str:
    return path.read_text(encoding="utf-8", errors="replace").strip() if path else ""


def build_case(case_id: str, files: list[Path]) -> Case:
    by_name = {p.name.lower(): p for p in files}

    def find(*names: str) -> Path | None:
        for n in names:
            if n in by_name:
                return by_name[n]
        return None

    pdf = find("invoices.pdf", "invoice.pdf")
    if pdf is None:
        pdf = next((p for p in files if p.suffix.lower() == ".pdf"), None)
    if pdf is None:
        raise ParseError(f"no invoice PDF among {[p.name for p in files]}")

    items = parse_line_items(pdf_to_text(pdf))
    images = tuple(str(p) for p in files if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
    return Case(
        case_id=case_id,
        policy_text=_read(find("policy.txt")),
        damage_description=_read(find("description.txt", "damage.txt")),
        items=items,
        image_paths=images,
    )
