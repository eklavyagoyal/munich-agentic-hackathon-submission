# Prompt für die Claude-Code-Session auf dem Mac Mini

(Datei-Kopie des Prompts, der die Mini-Migration durchführt. Original-Übergabe:
docs/HANDOVER.md. Die .env und data/ kommen per rsync vom Laptop — Keys stehen
absichtlich NICHT in diesem Prompt.)

---

Wir migrieren eine laufende Hackathon-Pipeline (QuantCo "Claim to Fame", Team Oasis) von einem MacBook auf diesen Mac Mini. Auf dem MacBook läuft der Live-Runner WEITER, bis hier alles bewiesen ist — dein Job ist NUR: aufsetzen, verifizieren, READY melden. Du submittest NICHTS ohne explizites Go von mir.

**Repository:** https://github.com/Luraxx/agentic-hackathon (privat, Branch main).
Kontext im Repo: README.md (Betrieb), docs/HANDOVER.md (Spielstand & Regeln), docs/STRATEGY.md.

Aufgaben, in dieser Reihenfolge:

1. **Projekt beschaffen.** Prüfe, ob ~/agentic-hackathon-v2 schon existiert (ich rsynce den kompletten Ordner vom Laptop rüber, inkl. .git, .env und data/). Falls ja: nutze ihn und mach `git pull`. Falls nein: `git clone https://github.com/Luraxx/agentic-hackathon.git ~/agentic-hackathon-v2` (gh/git auth ggf. mit mir zusammen) und warte auf mein rsync für `data/` und `.env` — ohne die geht es nicht weiter.

2. **Entire aktivieren.** Prüfe `entire --version`. Falls nicht installiert: über Homebrew installieren (Doku: docs.entire.io), dann ggf. `entire login` (ich sitze daneben). Im Projektordner: `entire enable --agent claude-code` — die .entire/settings.json aus dem Repo (checkpoints: git-refs) soll erhalten bleiben. Danach `entire status` und `entire doctor` zeigen.

3. **Abhängigkeiten.**
   - `python3 --version` (≥3.10 nötig)
   - `python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt`
   - `pdftotext -v` — falls fehlt: `brew install poppler` (PFLICHT, der Invoice-Parser braucht es; ohne Homebrew: sag mir Bescheid)

4. **Daten verifizieren** (kommen per rsync; NIEMALS in git committen, data/ ist gitignored und muss es bleiben):
   - `data/cases/zips/` ≥ 100 zip-Dateien
   - `data/c2f.sqlite` vorhanden (~34 MB)
   - `data/events/v2.jsonl` vorhanden — daraus rekonstruiert der Runner, welche Spiele schon submittet sind (Doppel-Submit-Schutz)
   - `data/policy.json` vorhanden (Live-Policy)
   - `.env` vorhanden mit TEAM_API_KEY und OPENAI_API_KEY(_1/2/3)
   - Dann: `.venv/bin/python -m backend.app.sync` (holt Schedule/Transaktionen/Keys aktuell) und `.venv/bin/python -m backend.app.bounds` — die Validierung MUSS "max |reconstructed - official| = 0.0000 -> OK" ausgeben.

5. **Sicherung gegen versehentliches Submitten:** Stelle sicher, dass in `.env` die Zeile `C2F_READONLY=1` steht, SOLANGE der Laptop-Runner läuft. Der Submitter wirft damit eine Exception statt zu PUTten.

6. **Pflicht-Smoke-Test (dry, submittet nichts):**
   `.venv/bin/python -m backend.app.play --game 0`
   Erwartung: Timeline mit key/decrypt/parse/estimate, `dry_run: True`, 1 Item "New Bike", a=~357. Falls Modelle antworten (ensemble3): alles grün.

7. **Optional, nice-to-have:** Daten-API + Dashboard starten (read-only):
   `PYTHONUNBUFFERED=1 nohup .venv/bin/python -m backend.app.server >> data/logs/server.log 2>&1 &` und in `dashboard/`: `npm install && npm run dev` (UI auf :5173, Seite "Live").

8. **Melde READY** mit einer Checkliste: entire ✓, deps ✓, Daten ✓, Validierung 0.0000 ✓, Smoke ✓, READONLY gesetzt ✓. Und STOPP — der Scharfschalt-Befehl kommt erst nach meinem Go, und er lautet dann: C2F_READONLY-Zeile aus .env löschen, nochmal Game-0-Smoke, dann `PYTHONUNBUFFERED=1 nohup .venv/bin/python -m backend.app.play --watch --submit >> data/logs/watch.log 2>&1 &`. Eiserne Regel aus docs/HANDOVER.md: NIE zwei Runner gleichzeitig (PUT ist last-write-wins) — der Laptop wird VOR deinem Start gestoppt, das koordiniere ich.
