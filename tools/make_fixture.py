"""Generate a synthetic encrypted case so the whole pipeline is provable today,
without credentials. Mirrors the invoice layout from the QuantCo slides.

    python tools/make_fixture.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pyzipper
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "cases"
PASSWORD = "fixture-key-case-0"

POLICY = """HOUSEHOLD CONTENTS POLICY -- Section 4: Water damage

Covered: damage caused by water escaping from pipes, including removal and
replacement of damaged floor coverings, skirting boards and drying measures.

Excluded: gradual wear and tear, cosmetic renovation not caused by the loss
event, and any item not related to the reported damage.
"""

DESCRIPTION = """The water pipe in the living room broke on 07 Aug 2026,
resulting in soaked laminate flooring across the room and damage to the
skirting boards along all four walls.
"""

ITEMS = [
    (1, "Remove water-damaged laminate in living room", "18", "m2"),
    (2, "New installation of laminate incl. impact sound insulation", "18", "m2"),
    (3, "Replace skirting boards", "25", "lm"),
    (4, "Repaint ceiling for visual uniformity", "22", "m2"),   # unrelated -> t should be 0
]


def build_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    y = h - 60
    c.setFont("Helvetica-Bold", 16); c.drawString(50, y, "Invoice"); y -= 30
    c.setFont("Helvetica", 9)
    for label, val in (("INVOICE NO.", "2026-0028"), ("DATE", "07 Aug 2026"),
                       ("DUE DATE", "14 Aug 2026"), ("TRADE", "Flooring")):
        c.drawString(50, y, f"{label}: {val}"); y -= 14
    y -= 10
    c.setFont("Helvetica-Bold", 10); c.drawString(50, y, "LINE ITEMS"); y -= 18
    c.setFont("Helvetica-Bold", 8)
    c.drawString(50, y, "POS."); c.drawString(85, y, "DESCRIPTION")
    c.drawString(420, y, "QTY"); c.drawString(465, y, "UNIT")
    c.drawString(500, y, "UNIT PRICE"); y -= 14
    c.setFont("Helvetica", 8)
    for pos, desc, qty, unit in ITEMS:
        c.drawString(50, y, str(pos)); c.drawString(85, y, desc)
        c.drawString(420, y, qty); c.drawString(465, y, unit)
        y -= 14                      # UNIT PRICE deliberately left blank
    y -= 10
    for label in ("Net", "plus VAT", "Total amount"):
        c.setFont("Helvetica-Bold", 8); c.drawString(50, y, label); y -= 14
    c.save()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "_build"; tmp.mkdir(exist_ok=True)
    (tmp / "policy.txt").write_text(POLICY, encoding="utf-8")
    (tmp / "description.txt").write_text(DESCRIPTION, encoding="utf-8")
    build_pdf(tmp / "invoices.pdf")

    archive = OUT / "case-0.zip"
    with pyzipper.AESZipFile(archive, "w", compression=pyzipper.ZIP_DEFLATED,
                             encryption=pyzipper.WZ_AES) as zf:
        zf.setpassword(PASSWORD.encode())
        for f in sorted(tmp.iterdir()):
            zf.write(f, f.name)
    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()
    print(f"wrote {archive}  ({archive.stat().st_size} bytes, password {PASSWORD!r})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
