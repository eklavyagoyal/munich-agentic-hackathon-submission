# Claim to Fame — v2 (Team Oasis)

Neuaufbau für die zweite Turnierhälfte: **Analyse**, kalibrierte **Submission-Pipeline**, **Live-Betrieb**.
Strategie & Lage: [docs/STRATEGY.md](docs/STRATEGY.md).

## Layout

```
backend/app/
  sync.py        alles frisch laden: Schedule, Matrix, alle Transaktionen, Keys, Cases
  bounds.py      t-Bänder + P&L-Attribution, validiert gegen die offizielle Matrix (0.0000)
  parse.py       Invoice-Parser (41/41 gespielte Cases exakt)
  estimate.py    3-Modell-LLM-Ensemble (Median, text-only) + Fallback-Raten
  policy.py      t̂ -> (a, b); hot-reloadbar über data/policy.json
  calibrate.py   Backtest: Ensemble über alte Cases + (A,B)-Sweep gegen bewiesene t-Bänder
  play.py        der Runner: Key -> Decrypt -> Parse -> Estimate -> Submit (+ Notfallpfad)
  submitter.py   einziges Modul mit Schreibzugriff auf die Turnier-API; Echo-Verifikation
  server.py      FastAPI :8000 — Daten für das Dashboard, GET/POST /api/policy
dashboard/       React (Vite) :5173 — Overview · ⚡Live · Games · Items · Teams
data/            ALLE Turnierdaten + Logs + Events — gitignored, niemals committen
```

## Live-Betrieb (läuft)

```bash
PYTHONUNBUFFERED=1 nohup .venv/bin/python -m backend.app.play --watch --submit >> data/logs/watch.log 2>&1 &
PYTHONUNBUFFERED=1 nohup .venv/bin/python -m backend.app.server >> data/logs/server.log 2>&1 &
cd dashboard && npm run dev        # http://localhost:5173 -> ⚡ Live
```

- **⚡ Live** zeigt: Runner-Status, Countdown, jede Runde mit Phasen-Timing, Modell-Votes
  pro Item, Prompt, entschlüsselte Dokumente, Submission-Echo. Policy (a/b-Multiplikatoren,
  Modelle) ist dort **live editierbar** — `data/policy.json` wird vor jedem Spiel neu gelesen.
- **Notfallpfad:** wirft der Hauptpfad, submittet der Runner Fallback-Raten statt nichts
  (ein 0/0-Spiel ist das teuerste Ergebnis überhaupt).
- Nach Code-Änderungen: `pkill -f backend.app.play`, Game-0-Dry-Run als Smoke-Test,
  dann neu starten — **nie ungetesteten Code unter dem Runner wechseln** (hat Spiel 44 gekostet).

## Analyse & Kalibrierung

```bash
.venv/bin/python -m backend.app.sync              # Daten aktualisieren (idempotent)
.venv/bin/python -m backend.app.bounds            # t-Bänder + Validierung
.venv/bin/python -m backend.app.calibrate --estimates   # Ensemble über alle alten Cases (Cache)
.venv/bin/python -m backend.app.calibrate --sweep       # (A,B)-Grid gegen bewiesene Bänder
```

**Dieses Repo ist der einzige Submitter.** `PUT` ist last-write-wins — nie einen zweiten
Runner armen. Auf jeder anderen Maschine `C2F_READONLY=1` in die `.env`.
