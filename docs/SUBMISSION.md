# Team Oasis — Claim to Fame: Systembericht

*QuantCo Agentic Hackathon München, 22.–23. August 2026 · Repo: `agentic-hackathon` (v2) · **Endstand: Platz 9/17 (−356.834 €), Sieg im Finalspiel 100 (+134.957 €, größtes Einzelergebnis des eigenen Turniers).***

---

## 1. Das Spiel in drei Sätzen

Pro Runde bekommen alle 17 Teams denselben Versicherungsfall (Policy, Schadenbeschreibung, Foto, Rechnung mit geschwärzten Preisen). Pro Line-Item existiert ein geheimer fairer Wert `t`; wir submitten blind `a` (was wir als Rechnungssteller von jedem Gegner verlangen) und `b` (bis wohin wir als Versicherer eingehende Rechnungen akzeptieren). Die Payoff-Asymmetrien entscheiden alles: **eine faire Rechnung (a ≤ t) wird von jedem bezahlt — auch von Ablehnern (die zahlen 1,5a)**; falsches Ablehnen kostet also 0,5a extra, falsches Akzeptieren den vollen Betrag, und **Überbieten kostet den Rechnungssteller nichts**.

## 2. Architektur: drei Ebenen + ein Runner

```
A · DATENFUNDAMENT   sync.py     alle 5 min: Spielplan, offizielle Matrix, Keys,
                                 Cases, 254.000+ Transaktionen ALLER 17 Teams → SQLite
B · ANALYSE          bounds.py   interval-zensierte t-Bänder aus den Flows des
                                 gesamten Feldes · P&L-Attribution pro Fehlerklasse
                     calibrate/  Backtests & Politik-Sweeps ohne LLM-Kosten
                     opt.py
C · ENTSCHEIDUNG     estimate.py 3-Modell-LLM-Ensemble (Median, text-only)
                     anchors.py  Retrieval bewiesener Preisbänder in den Prompt
                     digest.py   Policy-Digest pro Case (Ausschlüsse, Caps)
                     wording.py  Szenario-/Wording-Präzedenzen früherer Spiele
                     policy.py   t̂ → (a, b) — hot-reloadbar über data/policy.json
RUNNER               play.py     Key → Decrypt → Parse → Estimate → Decide → Submit
                     submitter.py einziges Modul mit API-Schreibzugriff: Event-Log,
                                 Doppel-Submit-Schutz, Echo-Verifikation, Notfallpfad
UI                   dashboard/  React „⚡ Live": jede Phase, jedes Modell-Votum,
                                 Policy-Editor (greift ohne Neustart ab dem nächsten Spiel)
```

**Die zwei eisernen Disziplinen:**

1. **Validierung vor Vertrauen.** Unsere P&L-Rekonstruktion aus den Roh-Transaktionen muss die offizielle Score-Matrix **auf 0,0000 reproduzieren** (zuletzt 1.530 Zellen), sonst wird keine abgeleitete Zahl benutzt. Diese Disziplin hat sich doppelt bezahlt: Als die Organisatoren ab Spiel 81 unangekündigt den 3×-Multiplikator aktivierten, schlug die Validierung sofort Alarm — ohne sie hätten falsch skalierte Bänder unbemerkt alle Anker vergiftet.
2. **Nichts Ungetestetes unter dem laufenden Runner.** Jede Änderung: Backtest → Game-0-Smoke (dry) → Neustart zwischen zwei Runden. Parameter dagegen sind hot: `policy.json` wird vor jedem Spiel neu gelesen.

## 3. Der Strategie-Bogen — wie sich die Strategie im Spiel verändert hat

**Phase 1 (Spiele 1–43, „v1"): −328k.** LLM-Schätzungen ohne Validierungsebene, boolesche Coverage-Entscheidungen, keine Nutzung der öffentlichen Daten. Lehrgeld.

**Phase 2 (Spiele 44–50, „v2"-Neuaufbau):** Erst das Datenfundament, dann Entscheidungen. Retrieval-Anker aus bewiesenen t-Bändern (Schätzfehler 44 % → 29 %), Policy-Digest pro Case (Spiel 48 verbrannte 18/27 Items unter einer Ausschlussklausel), wertabhängiges b mit globalem Deckel: Fraud-Käufe von 32k auf ~1k pro Spiel. Spiel 50: Platz 2.

**Phase 3 (Migration + der teuerste Fehler des Turniers):** Wechsel auf eine zweite Maschine mit READY-Gate (Setup beweisen, read-only bleiben, erst nach explizitem Go scharfschalten — `C2F_READONLY` lässt den Submitter werfen statt PUTten). Trotzdem: ein vergessener v1-Runner auf einer dritten Maschine lief weiter. Da `PUT` last-write-wins ist, überschrieb er unsere korrekte Submission mit Nullen — **Spiel 82: −242.000 € in einer einzigen 3×-Runde.** Der Nachweis gelang forensisch: unser Score war centgenau identisch mit den No-Submit-Teams, obwohl der Server unsere Werte per Echo bestätigt hatte. Maschine identifiziert, abgeschaltet, ab Spiel 84 sauber.

**Phase 4 (3×-Phase, Spiele 84+): datengetriebenes Live-Tuning.** Vier Mechanismen, jeder vor dem Scharfschalten backtested, jeder in Minuten rückrollbar:

- **P(covered)-Gate:** Das Ensemble liefert pro Item eine kalibrierte Coverage-Wahrscheinlichkeit. Die Kollegen-Idee („Preis mit p multiplizieren") haben wir spieltheoretisch korrigiert: **p skaliert niemals a** (Überbieten ist gratis, Unterbieten verschenkt garantierte 16×a), sondern steuert nur die Reviewer-Seite — unter p<⅔ akzeptieren wir nichts (Schwellwertregel aus der 2:1-Asymmetrie). Backtest: +17,6k über 76 Spiele.
- **Präzedenz-Gedächtnis:** Die Organisatoren recyceln Szenarien (teils wortidentisch). Adjudizierte Ergebnisse früherer Zwillinge („Item X bewies t<38") wandern als harte Fakten in den Prompt.
- **Gegnerfeld-Kurven statt Bauchgefühl:** Die öffentlichen Transaktionen aller Teams ergeben eine gemessene Fraud-Akzeptanzkurve F(a) und — wichtiger — exakte Counterfactuals auf unseren eigenen abgelehnten Charges (Ablehnungs-Flows verraten die Ground truth perfekt: Penalty = war fair, null = war Fraud). Ergebnis: unser Penalty-Leck saß im Akzeptanz-Deckel, nicht im Multiplikator → Deckel 450→800 (+12,8k/7 Spiele), Multiplikatoren gestrafft.
- **Anker-Hygiene:** Der Anker-Floor kollidierte über Gewerke hinweg (generische Zeilen wie „Skilled worker hours": bewiesen ≥754 im Wasserschaden, <49 im Fahrrad-Case) — kostete ein Spiel und flog raus (rückwirkend über 70 Spiele netto negativ).

**Ergebnis der Phase 4 (final):** Vierzehn Runden seit dem korrigierten Paket (Spiele 87–100): **dreizehn positiv, +575,5k**, darunter **zwei Rundensiege** — Spiel 96 (+64,8k, +23k Vorsprung) und das **Finale Spiel 100 (+134.957 €, +32k Vorsprung, größtes Einzelergebnis des eigenen Turniers)** — dazu viermal Platz 2/3. Gesamtcomeback von −956,8k (Tiefpunkt nach dem Rogue-Vorfall) auf **−356,8k = +600k Comeback, Endplatz 9/17** (Platz 13 → 9). Issuer-Einkommen seit Spiel 84: **Platz 1 aller 17 Teams**, bei gleichzeitig niedrigsten Accept-Kosten und Bestwert bei gekauftem Fraud.

## 4. Die Evidenz in Zahlen

| Behauptung | Beleg |
| --- | --- |
| Rekonstruktion exakt | 1.530 Matrix-Zellen, max. Abweichung 0,0000 |
| 3×-Phase beginnt bei Spiel 81 (nicht 82) | alle 5 Nicht-Null-Zellen von g81 exakt 3× der Transaktionssumme |
| Anker wirken | Leave-one-game-out: +17 % Issuer-Einkommen, −14 % Reviewer-Kosten |
| P(covered)-Gate wirkt | +17,6k/76 Spiele; Präzision 0,78/Recall 0,60 auf 444 bewiesen wertlosen Items |
| Deckel-Anhebung wirkt | Counterfactual auf 561 echten Rejects: m=1,0/b_max=800 = +12,8k; **Live-A/B auf Zwillings-Cases 89/92: Penalty-Aufschlag −72 %, NET +64 %** |
| Modellstärke ersetzt keine Kalibrierung | gpt-5.6-Zweitmeinung für Top-Items im Backtest verworfen: Band-Fehler 0,178 → 0,235 (bolder, not better — dokumentiert, Flag bleibt aus) |
| Acceptance-Rate ist die falsche Metrik | PaidRate zählt: 63,8 % (Feldbestwert) — faire Rechnungen zahlen auch Ablehner |
| Rogue-Runner-Forensik | g82: Score centgenau = No-Submit-Cluster trotz echo-bestätigter eigener Submission |

## 5. Was wir gelernt haben

1. **Organisatorische Fehler schlagen jede Modellqualität.** Ein vergessener Prozess kostete mehr (−261k) als alle Modellfehler der zweiten Turnierhälfte zusammen. „Nie zwei Runner" gehört in die Architektur (Read-only-Flags, Event-Log, Echo-Verifikation), nicht in die Disziplin.
2. **Jede abgeleitete Zahl gegen die offizielle Wahrheit validieren** — die 0,0000-Schranke hat zwei stille Katastrophen verhindert (Regel-Fehlinterpretation, unangekündigter Multiplikator).
3. **Public Data ≠ Public Alpha.** Die Transaktions-API stand allen offen; das Alpha lag in der Verarbeitungspipeline (Bänder, Anker, Kurven, Counterfactuals).
4. **Spieltheorie vor Machine Learning.** Die Payoff-Asymmetrien diktieren die Politik: Acceptance-Rate ist Vanity (fair zahlt immer), a senkt man nie (Überbieten gratis), b ist ein Schwellwertproblem (akzeptiere nur bei P(fair) > ⅔). Erst danach lohnt besseres Schätzen.
5. **Mehr Kontext — und mehr Modellstärke — machen Modelle „bolder, not better".** Text-only-Median-Ensemble schlug jede Variante mit Foto/Rohpolicy, und auch die Zweitmeinung eines stärkeren Modells verschlechterte die Band-Treffer messbar. Kalibrierung schlägt Kapazität.
6. **Coverage ist per Case, nicht per Wording** (der Schedule entscheidet) — Präzedenzen deshalb nur als weiche Evidenz in den Prompt, nie als harte Regel.
7. **Iterationsgeschwindigkeit ist ein Feature der Architektur:** hot-reloadbare Politik + LLM-freie Sweeps + Event-Log-Replay erlaubten fünf validierte Politikwechsel in einer Stunde Live-Betrieb — bei einem 12-Minuten-Rundentakt.
8. **Das Turnier hat ein Gedächtnis** — wer Szenario-Recycling erkennt, spielt mit offenen Karten.

## 6. Betrieb (Kurzreferenz)

```bash
.venv/bin/python -m backend.app.sync --loop        # Datenfundament, alle 5 min
.venv/bin/python -m backend.app.play --game 0      # Pflicht-Smoke (dry) vor jedem Scharfschalten
PYTHONUNBUFFERED=1 nohup .venv/bin/python -m backend.app.play --watch --submit >> data/logs/watch.log 2>&1 &
.venv/bin/python -m backend.app.server &           # Daten-API :8000 (read-only)
cd dashboard && npm run dev                        # ⚡ Live-UI :5173
```

*Sicherungen: `C2F_READONLY=1` auf jeder Nicht-Runner-Maschine · ein Submitter-Modul · Event-Log rekonstruiert `already_submitted` über Neustarts · Notfallpfad submittet Fallback-Raten statt nichts (ein 0/0-Spiel ist das teuerste Ergebnis).*
