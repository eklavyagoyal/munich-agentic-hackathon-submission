# Übergabe — Stand 22.08.2026, 23:25 UTC (nach Spiel 50)

**Diese Maschine submittet nicht mehr.** Runner gestoppt um 23:22:14 UTC, Spiel 51
unberührt, `C2F_READONLY=1` steht in der `.env` (der Submitter wirft dann eine
Exception statt zu PUTten). Weiter laufen (read-only): Daten-API auf :8000,
Dashboard auf :5173, `sync --loop` (aktualisiert DB + t-Bänder alle 5 min).

## Spielstand

- Gesamt: **−468.952 €** nach 50 Spielen · letzte Runde (50): **+9.159 €, Platz 2/17**
- v2-Pipeline (Spiele 44–50): −20.9k · +0.3k · +2.4k · −5.1k · −12.8k · −11.1k · **+9.2k**
- Break-even braucht ~5,2k pro Wertungsäquivalent (≈30 Spiele 1× + ≈20 Spiele 3× ab 06:00 UTC)

## Wie man den Runner (wieder) scharf macht

```
# .env: C2F_READONLY-Zeile entfernen, dann:
.venv/bin/python -m backend.app.play --game 0            # Pflicht-Smoke-Test (dry)
PYTHONUNBUFFERED=1 nohup .venv/bin/python -m backend.app.play --watch --submit >> data/logs/watch.log 2>&1 &
```

- **Nie zwei Runner** (PUT ist last-write-wins). Erst prüfen, ob der andere aus ist.
- Neustarts sind idempotent: erfolgreich submittete Spiele werden aus dem Event-Log
  (`data/events/v2.jsonl`) rekonstruiert und nie doppelt gespielt.
- Notfallpfad submittet Fallback-Raten, wenn der Hauptpfad wirft — aber nie, wenn
  schon ein erfolgreicher PUT stand.

## Was die Pipeline heute Nacht gelernt hat (alles im Backtest verifiziert)

| Mechanismus | Warum | Wirkung |
| --- | --- | --- |
| 3-Modell-Ensemble, Median, text-only | Foto & Rohpolicy machen Modelle „bolder, not better" (2× reproduziert) | Basis |
| **Retrieval-Anker** (`anchors.py`) | 600+ bewiesene t-Bänder aus gespielten Spielen pinnen die Preisskala; Round-Robin, damit große Cases kein Item verhungern lassen | Fehler vs. Band-Mitte 44 %→29 % |
| **Policy-Digest** (`digest.py`, gecacht) | Coverage ist PER CASE — Spiel 48 verbrannte 18/27 Items unter einer Pool-Ausschlussklausel | E[NET] ×3 auf voller Population |
| **Wertabhängiges b + b_max=450 + Anker-Clamps** (`policy.py`) | Fraud-Käufe clustern auf billigen Items, wrong-rejects auf teuren; t̂-Überschätzung skaliert b mit | Fraud-Käufe 32k→14.7k→**1.054 €** |
| Zero-Floor a=69/b=0 | Issuer-Überbieten kostet nichts; F(a)=0,186 gemessen | Gratis-Upside |

Alle Parameter live änderbar: Dashboard ⚡Live → Policy-Editor → `data/policy.json`
(wird vor jedem Spiel neu gelesen, kein Neustart).

## Der größte offene Hebel

**Issuer-Seite: immer noch zu billig.** Spiel 50 ließ trotz Platz 2 bewiesene 12.188 €
liegen. Werkzeuge dafür liegen bereit:
- `backend.app.calibrate --estimates --variant <name>` + `--sweep`: Ensemble-Varianten
  gegen bewiesene Bänder (leave-one-game-out, gecacht in `estimates_v`)
- `backend.app.opt`: Politik-Sweeps (A, b-Stufen, Anker-Clamps) ohne LLM-Kosten
- Ungetestete Ideen: Big-Ticket-Zweitmeinung (stärkeres Modell für die 3 wertvollsten
  Items, Budget ~45 s frei), A-Anhebung Richtung 0,9 (F-Term spricht dafür, Sweep war flach)

## Validierungs-Disziplin (bitte beibehalten)

- `bounds.py` reproduziert **alle offiziellen Matrix-Zellen auf 0,0000** — erst syncen,
  dann ableiten; niemals Hand-SQL gegen `transactions` ohne diese Validierung.
- Jede Prompt-/Politik-Änderung: erst Backtest auf identischer Item-Population
  (Metrik-Falle: die two-sided-Population enthält KEINE Coverage-Items), dann
  Game-0-Smoke, dann Neustart — nie ungetesteten Code unter dem Runner wechseln.
