"""Invoice parsing — adapted from v1's battle-tested parser (every quirk in the
regex was paid for with a lost round: en-dash lump-sum rows, "flat rate" units,
group separators in quantities, missing tail rows).

Never raise on a readable invoice: a missing row scores 0/0 which both rejects
fair claims (penalty) and earns nothing. Fill gaps with placeholders instead.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class ParseError(RuntimeError):
    pass


@dataclass(frozen=True)
class LineItem:
    idx: int          # contiguous ordinal 1..N == the API's line item index
    description: str
    qty: float
    unit: str
    pos: str = ""


@dataclass(frozen=True)
class Case:
    game_id: int
    policy: str
    damage: str
    invoice_text: str
    items: tuple[LineItem, ...]
    images: tuple[str, ...] = ()


ROW = re.compile(
    r"^\s*(?P<pos>\d{1,3})\s+"
    r"(?P<desc>\S.*?\S)\s{2,}"
    r"(?P<qty>\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?|\d{1,6}(?:[.,]\d{1,3})?|[–—-])\s+"
    r"(?P<unit>[A-Za-zµ%][A-Za-z0-9µ²³%.]{0,11}(?:[ ][A-Za-z]{1,8})?|[–—-])\s*$"
)
DASHES = ("–", "—", "-")
STOP_WORDS = ("net", "plus vat", "total amount", "zwischensumme", "gesamtbetrag")


def _qty(raw: str) -> float:
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


def pdf_to_text(pdf: Path) -> str:
    exe = shutil.which("pdftotext")
    if exe is None:
        raise ParseError("pdftotext not on PATH (brew install poppler)")
    proc = subprocess.run([exe, "-layout", str(pdf), "-"],
                          capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        raise ParseError(f"pdftotext exit {proc.returncode}")
    if not proc.stdout.strip():
        raise ParseError("PDF has no text layer")
    return proc.stdout


def _position_ceiling(text: str) -> int:
    """Highest N with positions 1..N all printed at line starts — catches tail
    rows the regex could not read (they still must be submitted).

    Requires >=2 spaces after the number: real rows sit in a column layout,
    while street addresses ("11 Sawdust Street") have exactly one space and
    would otherwise inflate the ceiling (games 9 and 39)."""
    seen = {int(m.group(1)) for m in re.finditer(r"^\s*(\d{1,3})\s{2,}", text, re.M)}
    n = 0
    while n + 1 in seen:
        n += 1
    return n


def parse_line_items(text: str) -> tuple[LineItem, ...]:
    rows: list[tuple[str, str, float, str]] = []
    for raw in text.splitlines():
        low = raw.strip().lower()
        if not low or any(low.startswith(w) for w in STOP_WORDS):
            continue
        m = ROW.match(raw)
        if not m:
            continue
        unit_raw = m["unit"].strip()
        rows.append((m["pos"], m["desc"].strip(), _qty(m["qty"]),
                     "pauschal" if unit_raw in DASHES else unit_raw))

    # dedupe printed positions, keep first
    seen: set[str] = set()
    rows = [r for r in rows if not (r[0] in seen or seen.add(r[0]))]

    ceiling = _position_ceiling(text)
    have = {int(p) for p, *_ in rows if p.isdigit()}
    top = max([ceiling] + sorted(have)) if (have or ceiling) else 0
    if not top:
        raise ParseError("no line items found in invoice text")
    for n in range(1, top + 1):
        if n not in have:
            rows.append((str(n), "(row not parsed)", 1.0, "pauschal"))
    rows.sort(key=lambda r: int(r[0]) if r[0].isdigit() else 10**6)
    return tuple(LineItem(idx=i, pos=p, description=d, qty=q, unit=u)
                 for i, (p, d, q, u) in enumerate(rows, start=1))


def load_case(game_id: int, case_dir: Path) -> Case:
    policy = damage = invoice_text = ""
    images: list[str] = []
    for path in sorted(case_dir.rglob("*")):
        if not path.is_file():
            continue
        low = path.name.lower()
        if low.endswith(".pdf"):
            invoice_text += pdf_to_text(path) + "\n"
        elif low.endswith((".png", ".jpg", ".jpeg", ".webp")):
            images.append(str(path))
        elif low.endswith((".txt", ".md")) and not low.endswith(".pdf.txt"):
            body = path.read_text(encoding="utf-8", errors="replace")
            if "polic" in low or "versicher" in low:
                policy += body + "\n"
            elif "descr" in low or "damage" in low or "schaden" in low:
                damage += body + "\n"
            elif len(body) > len(policy):
                policy += body + "\n"
            else:
                damage += body + "\n"
    if not invoice_text.strip():
        raise ParseError(f"no invoice text in {case_dir}")
    return Case(game_id=game_id, policy=policy.strip(), damage=damage.strip(),
                invoice_text=invoice_text, items=parse_line_items(invoice_text),
                images=tuple(images))
