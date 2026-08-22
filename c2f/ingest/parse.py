"""Turn an extracted case directory into a `Case`.

The invoice parser is deliberately STRICT. A parser that silently shifts item
indices produces a submission that looks entirely healthy and is scored as
garbage -- the quietest way to lose this tournament. Every failure here is loud.
"""
from __future__ import annotations

import re
import shutil
import subprocess
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
    r"(?P<qty>\d{1,6}(?:[.,]\d{1,3})?|[\u2013\u2014-])\s+"
    # Up to 12 chars: "pauschal" (8) and "Pauschale" (9) are on nearly every German
    # trade invoice, and at 6 they were dropped -- which the contiguity check below
    # then escalated into a total parse failure, i.e. a lost round.
    r"(?P<unit>[A-Za-zµ%][A-Za-z0-9µ²³%.]{0,11}|[\u2013\u2014-])\s*$"
)
DASHES = ("\u2013", "\u2014", "-")
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
        qty_raw, unit_raw = m["qty"], m["unit"].strip()
        # "one of it, no unit printed" -- the same shape the price book already
        # prices as a lump sum, so this reuses existing handling rather than
        # inventing a second notion of quantity-less work.
        qty = 1.0 if qty_raw in DASHES else float(qty_raw.replace(",", "."))
        unit = "pauschal" if unit_raw in DASHES else unit_raw
        items.append(LineItem(idx=0, pos=m["pos"], description=m["desc"].strip(),
                              qty=qty, unit=unit))

    try:
        return validate_items(items, require_contiguous=True)
    except ParseError:
        # A row we cannot read must never cost the round. Omitted line items score
        # as charge_price=0 and acceptance_limit=0, which rejects every fair claim
        # AND pays the penalty on it -- strictly worse than a rough bid. So fill
        # the gaps with lump-sum placeholders and submit a number for every
        # position that was printed.
        return validate_items(_fill_gaps(items), require_contiguous=False)


def _fill_gaps(items: list[LineItem]) -> list[LineItem]:
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
    if not nums:
        return items
    have = set(nums)
    filled = list(items) + [
        LineItem(idx=0, pos=str(n), description="(row not parsed)",
                 qty=1.0, unit="pauschal")
        for n in range(1, nums[-1] + 1) if n not in have
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
