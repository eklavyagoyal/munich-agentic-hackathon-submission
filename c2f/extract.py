"""Case files -> structured line items.

`pdftotext -layout` first (deterministic, ~50ms), then one LLM call to turn that
text into line items. No layout regex: we have not seen a real invoice yet, and a
brittle column parser that silently mis-reads a quantity is a 10x pricing error
(GAMEPLAN §8 trap 4). The regex path exists only as a last-resort fallback.

Run `python -m c2f.extract <case_dir>` to inspect what a real case parses to.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import llm

LINE_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pos": {"type": "string", "description": "position number as printed"},
                    "description": {"type": "string"},
                    "qty": {"type": "number"},
                    "unit": {"type": "string", "description": "m2, lm, h, Stk, pauschal, ..."},
                    "vat_rate": {
                        "type": "number",
                        "description": "as a fraction, e.g. 0.19. Use 0.19 if the invoice does not say.",
                    },
                },
                "required": ["pos", "description", "qty", "unit", "vat_rate"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

_EXTRACT_PROMPT = """You are reading a tradesperson's invoice from an insurance claim.
The price columns are intentionally blank — ignore them entirely.

Return every line item in the order printed. Rules:
- `qty` is the numeric quantity as printed. Decimal comma means decimal point (18,5 -> 18.5).
- Keep `description` verbatim, in its original language. Do not translate or summarise.
- A lump-sum line (Pauschale, Anfahrt) has qty 1 and unit "pauschal".
- Do not invent, merge or split lines. Subtotals, Net, VAT and Total rows are NOT line items.

INVOICE TEXT:
```
{text}
```"""


@dataclass
class LineItem:
    pos: str
    description: str
    qty: float
    unit: str
    vat_rate: float = 0.19

    @property
    def label(self) -> str:
        return f"[{self.pos}] {self.qty:g} {self.unit} — {self.description}"


@dataclass
class Case:
    """Everything a round hands us."""

    dir: Path
    policy: str = ""
    damage: str = ""
    invoice_text: str = ""
    images: list[Path] = field(default_factory=list)

    @classmethod
    def load(cls, case_dir: str | Path) -> "Case":
        d = Path(case_dir)
        c = cls(dir=d)
        for path in sorted(d.rglob("*")):
            if path.is_dir():
                continue
            low = path.name.lower()
            if low.endswith(".pdf"):
                c.invoice_text += pdf_text(path) + "\n"
            elif low.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
                c.images.append(path)
            elif low.endswith((".txt", ".md")):
                body = path.read_text(errors="replace")
                # Filenames are documented as policy.txt / description.txt, but do not
                # bet the round on it — fall back to keyword sniffing.
                if "polic" in low or "versicher" in low:
                    c.policy += body + "\n"
                elif "descr" in low or "damage" in low or "schaden" in low:
                    c.damage += body + "\n"
                elif len(body) > len(c.policy):
                    c.policy += body + "\n"
                else:
                    c.damage += body + "\n"
        if not c.invoice_text.strip():
            raise RuntimeError(f"no invoice text extracted from {d} — check the PDF text layer")
        return c


def pdf_text(path: Path) -> str:
    """Text layer via poppler. -layout keeps columns aligned, which the LLM reads better."""
    try:
        out = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            capture_output=True,
            timeout=10,
            check=True,
        )
        return out.stdout.decode("utf-8", errors="replace")
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
        # Caller decides: an empty text layer means we need the vision fallback.
        llm.log.warning("pdftotext failed on %s: %s", path.name, e)
        return ""


async def line_items(case: Case, *, fast: bool) -> list[LineItem]:
    """Structure the invoice text. Falls back to a regex sweep if the model call dies."""
    try:
        data = await llm.ask_json(
            _EXTRACT_PROMPT.format(text=case.invoice_text[:60_000]),
            schema=LINE_ITEM_SCHEMA,
            fast=fast,
            timeout=12.0,
        )
        items = [LineItem(**it) for it in data["items"]]
        if items:
            return items
        llm.log.warning("extraction returned zero items — falling back to regex")
    except Exception as e:
        llm.log.warning("LLM extraction failed (%s) — falling back to regex", e)
    return regex_items(case.invoice_text)


_ROW = re.compile(
    r"^\s*(?P<pos>\d{1,3})[.)]?\s+(?P<desc>\S.*?)\s{2,}"
    # unit must start with a letter but may carry digits: m2, m3, m², lm, h, Stk, pauschal
    r"(?P<qty>\d+(?:[.,]\d+)?)\s+(?P<unit>[A-Za-zµ][A-Za-z0-9µ²³/.]{0,11})"
)


def regex_items(text: str) -> list[LineItem]:
    """Last resort. Assumes `pos  description   qty  unit`, which is the common layout.

    ponytail: deliberately dumb. If this fires we have already lost accuracy; the
    only job left is to produce *something* non-zero so we do not submit defaults.
    """
    out: list[LineItem] = []
    for line in text.splitlines():
        m = _ROW.match(line)
        if not m:
            continue
        desc = m.group("desc").strip()
        if re.search(r"(?i)\b(summe|total|netto|net|brutto|zwischensumme|mwst|vat|ust)\b", desc):
            continue
        out.append(
            LineItem(
                pos=m.group("pos"),
                description=desc,
                qty=float(m.group("qty").replace(",", ".")),
                unit=m.group("unit"),
            )
        )
    if not out:
        llm.log.error("regex fallback also found no line items")
    return out


def demo() -> None:
    sample = """
    POS  DESCRIPTION                                        QTY   UNIT  UNIT PRICE  VAT  TOTAL
    1    Remove water-damaged laminate in living room       18    m2
    2    New installation of laminate incl. impact sound    18,5  m2
    3    Replace skirting boards                            25    lm
    4    Anfahrtspauschale                                  1     pauschal
         Zwischensumme                                      1     EUR
    Net
    plus VAT
    Total amount
    """
    items = regex_items(sample)
    assert len(items) == 4, [i.label for i in items]
    assert items[1].qty == 18.5, items[1].qty  # decimal comma survived
    assert items[2].unit == "lm"
    assert all("summe" not in i.description.lower() for i in items)  # subtotal row dropped
    assert regex_items("nothing parseable here") == []  # no crash, no phantom items
    print("extract.py self-check ok —", " | ".join(i.label for i in items))


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        c = Case.load(sys.argv[1])
        print(f"policy {len(c.policy)}c | damage {len(c.damage)}c | images {len(c.images)}")
        print(c.invoice_text[:3000])
        print("--- regex pass:")
        for it in regex_items(c.invoice_text):
            print(" ", it.label)
    else:
        demo()
