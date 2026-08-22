# Two invoice-parser bugs, one of them silent

**Found:** 22 Aug 2026, 14:56 UTC · games 1–9 (nine finished games, all replayed
from the decrypted archives)

Two separate defects in `c2f/ingest/parse.py`. The first quietly replaces real
prices with a lump-sum guess. The second invents a line item out of a postal
address, and is what makes game 9 unusable for the valuation dataset.

---

## 1. A `flat rate` unit is never parsed

The unit column carries four values across the nine invoices we hold:

| unit | rows | parsed |
| --- | ---: | --- |
| `pcs` | 86 | yes |
| `–` (en-dash) | 16 | yes, as `pauschal` |
| `flat rate` | 12 | **no** |
| `hrs` | 5 | yes |

Every `flat rate` row falls through and is filled with a `(row not parsed)`
placeholder. `pcs`, `hrs` and the en-dash all parse. The en-dash case was fixed
after game 1 — the two-word unit was not.

Game 9's invoice, exactly as printed:

```
 1   Repair of the storm-damaged shed roof section       1   flat rate   -> placeholder
 2   Full repaint of the entire shed, including the      –   –           -> parsed
 5   Skilled carpentry labour for the roof repair        1   pcs         -> parsed
 6   Contractor hand tools and reusable equipment        1   flat rate   -> placeholder
```

Placeholders per game, replayed against the real archives:

| game | parsed | placeholders | score |
| ---: | ---: | ---: | ---: |
| 4 | 15 | 2 | +699.64 |
| 5 | 17 | 2 | −476 |
| 8 | 39 | 3 | −1,769.26 |
| 9 | 17 | **6** | **−6,586.39** |

Six of seventeen line items on game 9 — 35% of the invoice — were priced without
ever reading the row. Games 1, 2, 3, 6, 7 have no `flat rate` rows and no
placeholders.

I am **not** claiming the placeholders caused those scores; four games is far too
few and the pricing model is changing underneath us. What is certain is that on
12 rows we bid without reading the line, and that is free to fix.

---

## 2. A postal address becomes a line item

The row matcher accepts any line that starts with a number, so the sender's
street address is read as a position. Game 9 has three sub-invoices, each with a
`FROM` block:

```
 11 Sawdust Street        Main Street 1     -> looks like POS 11
  3 Landfill Loop         Main Street 1     -> looks like POS 3
 17 Stump Street          Main Street 1     -> looks like POS 17
```

Where a real position with that number exists, it wins and the address is
harmless — game 5 POS 11 is still `Room drying of the kitchen floor and wall
base`, game 8 POS 16 is still `Final site cleaning`. I checked both.

Game 9 has only 16 positions. `17 Stump Street` had nothing to collide with, so
**it became line item 17** and we submitted a bid for an item that does not exist:

```
parsed indices  [1..17]
tournament      [1..16]
```

That is what makes `tools/harvest.py` reject game 9 outright, so the game
contributes nothing to the valuation dataset.

**This one is luck-dependent, and that is the worrying part.** It is invisible
whenever the street number happens to be ≤ the number of positions. Games 5 and 8
carry the same defect and show no symptom. The count check only catches it when
the address number runs past the end of the invoice.

---

## What I would change

1. **Accept a multi-word unit.** `flat rate` should map to the same lump-sum
   handling `–` already gets. Twelve rows across nine games, no downside I can see.
2. **Anchor rows to the items table.** Only treat a numbered line as a position
   between the `ITEMS` / `POS.` header and the page footer. An address in a `FROM`
   block would then never be a candidate, rather than being caught by a count
   check that only fires when we get unlucky.
3. Worth considering: **refuse to bid on an index the invoice does not contain.**
   We bid on a phantom item 17. It cost nothing this time because the server
   ignores it, but a phantom row shifting real indices would be expensive and
   would look exactly like this one did — fine, until it wasn't.

## How to reproduce

```bash
PYTHONPATH=. .venv/bin/python tools/cases.py       # opens every case we hold a key for
PYTHONPATH=. .venv/bin/python -c "
from pathlib import Path
from c2f.ingest import parse
d = Path('data/open/game-009')
fs = [f for f in d.iterdir() if f.name in ('description.txt','policy.txt','invoices.pdf')]
for i in parse.build_case('9', fs, None).items:
    print(i.idx, i.unit, i.description[:60])
"
```

`data/open/game-NNN/invoices.pdf.txt` is the invoice as `pdftotext` renders it —
which is what the parser actually sees.

**Confidence:** high on both. Reproduced on nine games from the real archives, and
the unit counts and the address lines are quoted verbatim above. The *cost* of
bug 1 is unmeasured; only its frequency is.
