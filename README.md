# Claim to Fame — v2 (Team Oasis)

Neuaufbau für die zweite Turnierhälfte: erst **Analyse**, dann kalibrierte **Submission-Pipeline**.
Der Plan: [docs/STRATEGY.md](docs/STRATEGY.md).

## Layout

```
backend/app/     Python: Daten-Sync, t-Band-Analyse, FastAPI für das Dashboard
dashboard/       React (Vite) — Analyse-UI
data/            ALLE Turnierdaten — gitignored, niemals committen
docs/            Strategie & Befunde
```

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
cp .env.example .env        # TEAM_API_KEY eintragen (im Team-Chat)
```

## Benutzen

```bash
.venv/bin/python -m backend.app.sync            # alles frisch laden (idempotent, resumbar)
.venv/bin/python -m backend.app.bounds          # t-Bänder + P&L ableiten & validieren
.venv/bin/python -m backend.app.server          # Daten-API auf :8000
cd dashboard && npm install && npm run dev      # UI auf :5173
```

**Dieses Repo submittet nichts.** Der Live-Runner (altes Repo) bleibt der einzige Submitter,
bis das Team explizit umschaltet — `PUT` ist last-write-wins.
