# Comeback-Plan: −328k → positiv bis zur 3×-Phase

**Stand: 22.08.2026, 23:20 lokal (21:20 UTC). Team `Oasis`, Platz 14/17, net −328.323,54 € nach 40/100 Spielen.**

## 1. Die Lage in Zahlen

Quelle: `leaderboard/api/performance?team=Oasis` + Spielplan (`api/games`).

| Fakt | Wert | Bedeutung |
| --- | --- | --- |
| Net | **−328.324 €** (income 663.857, costs 992.181) | Wir zahlen 1,5× so viel wie wir einnehmen |
| Spiele offen | **60 von 100** | Mehr als die Hälfte des Turniers ist noch spielbar |
| Bis 08:00 lokal (06:00 UTC) | 41 Spiele à **1×** | Kalibrier- und Aufholphase |
| Ab 08:00 lokal | **19 Spiele à 3×** = 57 Spieläquivalente | Der eigentliche Hebel: fast so viel Wertung wie die gesamten bisherigen 40 Spiele |
| Takt | alle 757,6 s (12 min 37,6 s) | Schedule ist öffentlich und exakt (`api/games`) |

**Konsequenz:** 41 + 57 = 98 Spieläquivalente sind offen, 40 sind gespielt. Ein Comeback ist
rechnerisch kein Wunder — das beste Team (`eyay`) macht ~3.650 €/Spiel. Auf diesem Niveau wären
ab jetzt ~358 k zu holen. Alles, was wir **vor** 08:00 an Qualität gewinnen, zahlt sich danach dreifach aus.

### Wo das Geld verloren geht (Performance-Zerlegung, 40 Spiele)

| Rolle | Zähler | Interpretation |
| --- | --- | ---: |
| Reviewer: falsch akzeptiert | **905** | Fraud bezahlt — voller Schaden `min(a,c)` |
| Reviewer: falsch abgelehnt (Penalty) | **1.098** | Faire Rechnung abgelehnt → wir zahlen **1,5a** statt a |
| Reviewer: korrekt | 3.789 accepts + 1.600 rejects | |
| Issuer: akzeptiert | 2.778 / 7.392 (37,6 %) | Niedrige Acceptrate ist per se ok (fair-rejected zahlt trotzdem) — aber nur wenn `a ≤ t` war |

Die exakte €-Attribution pro Fehlerklasse rechnet das Dashboard (Abschnitt 3) aus den
Transaktionsdaten — das ist Aufgabe 1, denn sie entscheidet, welcher Hebel zuerst kommt.

## 2. Was dieses Spiel wirklich ist

Kein Poker, kein Opponent-Modelling im Kern: **ein Schätzproblem für `t` pro Line-Item.**

- **Issuer:** Ein fairer Charge `a ≤ t` wird von *jedem* Gegner bezahlt (Accept: a; Reject: a + Strafe für ihn).
  `a > t` verdient (fast) nichts. ⇒ optimal: `a` knapp unter t̂ (untere Konfidenzschranke).
- **Reviewer:** Accept kostet `a`, falscher Reject kostet `1,5a`. ⇒ `b` an der *oberen* Konfidenzschranke:
  im Zweifel akzeptieren, denn der Fehler „fair abgelehnt“ ist 50 % teurer als der Fehler „Fraud bezahlt“
  erst ab dem Punkt, wo Fraud-Anteil × Schaden das Penalty-Risiko übersteigt. Die richtige Schwelle
  liefert die Kalibrierung, nicht das Bauchgefühl.
- Beide Seiten hängen am **selben t̂** — eine bessere Schätzung repariert Einnahmen UND Kosten gleichzeitig.

### Der ungenutzte Datenschatz

`api/transactions?game_id&team` ist öffentlich — für **alle** Teams. Jede Zeile
`{issuer, reviewer, line_item_index, accepted, amount}` verrät etwas über t:

| Beobachtung | Schluss |
| --- | --- |
| rejected, amount > 0 (Penalty floss) | Charge war fair: **t ≥ a = amount/1,5** |
| rejected, amount = 0 (nichts floss) | Charge war Fraud: **t < a** des Issuers |
| accepted, amount < a des Issuers | Cap griff: amount = c ≥ 4t ⇒ **t ≤ amount/4** |

17 Teams reichen unterschiedliche `a` ein ⇒ pro Item ein **interval-zensiertes t-Band**, oft eng.
Damit: echtes Preisniveau pro Gewerk lernen, unsere 40 Spiele nachrechnen („was hätte Politik P verdient?“),
und die b-Politik datenbasiert setzen. Das ist die Analyse-Ebene dieses Repos.

## 3. Die drei Ebenen dieses Repos

```
┌────────────────────────────────────────────────────────────┐
│  A · DATEN-FUNDAMENT      backend/app/sync.py              │
│  Alles frisch & vollständig: Spielplan, Matrix, alle       │
│  Transaktionen (17 Teams × fertige Spiele), Keys, Cases    │
│  (101 Zips → entschlüsselt), SQLite. Idempotent, resumbar. │
├────────────────────────────────────────────────────────────┤
│  B · ANALYSE              backend/app/bounds.py + React    │
│  t-Bänder pro Item · €-Attribution pro Fehlerklasse ·      │
│  Gegner-Profile (wer akzeptiert was) · Counterfactuals     │
│  Dashboard: Overview / Games / Items / Teams               │
├────────────────────────────────────────────────────────────┤
│  C · ENTSCHEIDUNG & SUBMISSION (v2)                        │
│  Kalibrierte a/b-Politik aus B + LLM-Ensemble für neue     │
│  Cases. Läuft erst, wenn sie den alten Runner nachweislich │
│  schlägt — bis dahin submittet ausschließlich der alte.    │
└────────────────────────────────────────────────────────────┘
```

**Eiserne Regeln** (aus den Fehlern von Repo v1):

1. **Nie zwei Runner.** `PUT` ist last-write-wins — ein zweiter Submitter ersetzt bessere Antworten.
   Dieses Repo submittet NICHTS, solange der alte Runner armed ist. Übergabe ist eine explizite Team-Entscheidung.
2. **Keine Case-Daten in git.** `data/` ist komplett gitignored (Organizer: checked-in claim data = ranking penalty).
3. **Analyse getrennt vom Hot Path.** Dashboard/API sind read-only auf `data/`, können nichts kaputt machen.
4. **Jede abgeleitete Zahl wird validiert** — z. B. P&L-Rekonstruktion aus Transaktionen muss die offizielle
   Matrix reproduzieren, sonst ist die Interpretation falsch.

## 4. Zeitplan bis 08:00

| bis (lokal) | Meilenstein |
| --- | --- |
| 00:15 | Ebene A steht: alle Daten lokal, SQLite gefüllt, Validierung grün |
| 01:00 | Dashboard v1: Standings, P&L-Attribution, Game-Drilldown |
| 01:30 | **Befund:** die 3 teuersten Fehlerklassen in €, je mit Gegenmaßnahme |
| 02:30 | t-Bänder + gelerntes Preisniveau pro Gewerk; Counterfactual-Backtest der letzten 40 Spiele |
| 04:00 | Entscheidung mit Team: Politik-Update in alten Runner vs. Pipeline v2 scharf |
| 06:00 | Neue Politik läuft nachweislich sauber über mehrere Live-Spiele |
| 08:00 | **3×-Phase mit bester validierter Politik — 19 Spiele, 57 Spieläquivalente** |

## 5. Offene Entscheidungen (mit dem Team zu diskutieren)

- **KI-Einsatz:** Es stehen „KI-Programme in jeglicher Stärke“ zur Verfügung. Vorbefund aus v1
  (`analysis/luis-1725`): 3-Modell-Ensemble, **Median**, text-only (Beschreibung + Invoice-Zeilen,
  ohne Policy/Foto) schlug alles andere; mehr Kontext machte Modelle „mutiger, nicht besser“.
  Neu zu bewerten: stärkere Modelle sind erlaubt und Latenz ist nur in den 60 s des Live-Spiels kritisch —
  für die **Offline-Kalibrierung** (t-Bänder erklären, Preisbuch bauen) können beliebig starke Modelle rechnen.
- **b-Politik:** Wie großzügig akzeptieren? Antwort kommt aus der €-Attribution (Penalty-Kosten vs. Fraud-Kosten).
- **Issuer-Aggressivität:** `a` am unteren t-Band (sicher, von allen bezahlt) vs. gezielt höher gegen
  Teams mit nachweislich hohem `b`. Erst nach Gegner-Profilen entscheiden.
- **Übergabezeitpunkt** alte → neue Pipeline (und wer den Schlüssel „armed“ hält).

## 6. Judging nicht vergessen

Score ist „the main signal, not the only one“. Generality, Consistency und der Pitch
(„how the strategy changed as you played“) zählen. Dieses Repo IST das Beweismaterial:
die Analyse-Ebene dokumentiert den Strategiewechsel mit Zahlen. Write-up am Ende aus
`docs/` + Dashboard-Screenshots.
