"""LLM invoice extraction -- the primary path, regex as the fallback.

A brittle column regex that silently mis-reads a quantity is a 10x pricing
error, and we have not seen a real invoice yet. So the model reads the layout
and the regex only catches it when no backend is configured.

Kept out of `parse` so the deterministic path imports no provider: the fallback
must work when the backend is down, and the tests must run without credentials.
"""
from __future__ import annotations

from c2f.core.models import LineItem
from c2f.ingest.parse import ParseError, parse_line_items, validate_items

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
                    "vat_rate": {"type": "number",
                                 "description": "fraction, e.g. 0.19. Use 0.19 if unstated."},
                },
                "required": ["pos", "description", "qty", "unit", "vat_rate"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

_PROMPT = """You are reading a tradesperson's invoice from an insurance claim.
The price columns are intentionally blank - ignore them entirely.

Return every line item in the order printed. Rules:
- `qty` is the numeric quantity as printed. Decimal comma means decimal point (18,5 -> 18.5).
- Keep `description` verbatim, in its original language. Do not translate or summarise.
- A lump-sum line (Pauschale, Anfahrt) has qty 1 and unit "pauschal".
- Do not invent, merge or split lines. Subtotals, Net, VAT and Total rows are NOT line items.

INVOICE TEXT:
```
{text}
```"""


async def extract_items(invoice_text: str, *, fast: bool = True,
                        timeout: float = 12.0) -> tuple[LineItem, ...]:
    """Model first, regex second. Both results go through the same validation."""
    from c2f.estimate import llm

    try:
        data = await llm.ask_json(_PROMPT.format(text=invoice_text[:60_000]),
                                  schema=LINE_ITEM_SCHEMA, fast=fast, timeout=timeout)
        raw = [
            LineItem(idx=0, description=d["description"], qty=float(d["qty"]),
                     unit=d["unit"], pos=str(d["pos"]),
                     vat_rate=d["vat_rate"] if 0 <= d["vat_rate"] < 1 else 0.19)
            for d in data["items"]
        ]
        if raw:
            return validate_items(raw, require_contiguous=False)
        llm.log.warning("extraction returned zero items -- falling back to regex")
    except ParseError:
        raise
    except Exception as e:  # noqa: BLE001 -- NoBackend, timeout, malformed JSON
        llm.log.warning("LLM extraction unavailable (%s) -- falling back to regex", e)
    return parse_line_items(invoice_text)
