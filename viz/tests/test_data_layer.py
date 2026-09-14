from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from viz.data_layer import (
    ChargeGroup,
    PIPELINE_CORE,
    TournamentStore,
    _event_time,
    _percentile,
    _proven_charge,
    _readonly_connection,
)


class ReadOnlyDatabaseTests(unittest.TestCase):
    def test_readonly_connection_rejects_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "synthetic.sqlite"
            con = sqlite3.connect(path)
            con.execute("create table sample(value integer)")
            con.execute("insert into sample values (7)")
            con.commit()
            con.close()

            with _readonly_connection(path) as readonly:
                self.assertEqual(readonly.execute("select value from sample").fetchone(), (7,))
                with self.assertRaises(sqlite3.OperationalError):
                    readonly.execute("insert into sample values (8)")

    def test_concurrent_snapshots_use_unique_atomic_temporary_files(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "source.sqlite"
            target = root / "runtime" / "threshold-source.sqlite"
            target.parent.mkdir()
            con = sqlite3.connect(source)
            con.execute("create table sample(value integer)")
            con.execute("insert into sample values (17)")
            con.commit()
            con.close()

            def snapshot() -> None:
                store = object.__new__(TournamentStore)
                with _readonly_connection(source) as readonly:
                    store._snapshot_database(readonly, target)

            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda _index: snapshot(), range(8)))
            check = sqlite3.connect(target)
            try:
                self.assertEqual(check.execute("select value from sample").fetchone(), (17,))
            finally:
                check.close()
            self.assertEqual(list(target.parent.glob("*.tmp.sqlite")), [])


class ChargeEvidenceTests(unittest.TestCase):
    def test_paid_rejection_proves_fair_and_exact_charge(self) -> None:
        group = ChargeGroup(1, 1, "Synthetic A")
        group.add("Oasis", False, 120.0)
        group.add("Synthetic B", True, 120.0)
        self.assertEqual(group.observed()["classification"], "fair")
        self.assertEqual(group.observed()["chargeKind"], "exact")
        self.assertEqual(group.observed()["charge"], 120.0)

    def test_unpaid_rejection_hides_fraud_charge(self) -> None:
        group = ChargeGroup(1, 1, "Synthetic A")
        group.add("Oasis", False, 0.0)
        self.assertEqual(group.observed()["classification"], "fraud")
        self.assertEqual(group.observed()["chargeKind"], "hidden")
        self.assertIsNone(group.observed()["charge"])

    def test_accepted_fraud_payout_is_only_a_lower_bound(self) -> None:
        group = ChargeGroup(1, 1, "Synthetic A")
        group.add("Oasis", True, 340.0)
        group.add("Synthetic B", False, 0.0)
        observed = group.observed()
        self.assertEqual(observed["classification"], "fraud")
        self.assertEqual(observed["chargeKind"], "lower_bound")
        self.assertEqual(observed["charge"], 340.0)

    def test_rejected_fair_reviewer_cost_is_one_point_five_times_charge(self) -> None:
        group = ChargeGroup(1, 1, "Synthetic A")
        group.add("Oasis", False, 200.0)
        store = object.__new__(TournamentStore)
        cost, label = store._reviewer_cost(group, "Oasis")
        self.assertEqual(label, "fair")
        self.assertEqual(cost, 300.0)


class DependencySemanticsTests(unittest.TestCase):
    def test_noncritical_failure_is_degraded_but_ready(self) -> None:
        store = object.__new__(TournamentStore)
        store._dependencies = {
            "database": {"ok": True, "critical": True},
            "thresholds": {"ok": True, "critical": True},
            "leaderboard": {"ok": False, "critical": False},
        }
        summary = store._dependency_summary()
        self.assertTrue(summary["ready"])
        self.assertTrue(summary["degraded"])

    def test_critical_failure_fails_readiness(self) -> None:
        store = object.__new__(TournamentStore)
        store._dependencies = {
            "database": {"ok": False, "critical": True},
            "leaderboard": {"ok": True, "critical": False},
        }
        self.assertFalse(store._dependency_summary()["ready"])

    def test_leaderboard_5xx_keeps_stale_cache_and_enters_degraded_mode(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = TournamentStore(root=root, runtime=root / "viz" / "runtime",
                                    leaderboard_url="http://127.0.0.1:1/local-only")
            store._leaderboard = {"standings": [{"team_name": "Synthetic", "total": 1}]}
            error = urllib.error.HTTPError(store.leaderboard_url, 503, "synthetic", {}, None)
            with patch("urllib.request.urlopen", side_effect=error) as request:
                store._refresh_leaderboard(20.0)
                store._refresh_leaderboard(21.0)
            self.assertEqual(request.call_count, 1, "backoff must suppress an immediate retry")
            self.assertIsNotNone(store._leaderboard, "stale data remains available explicitly")
            self.assertFalse(store._dependencies["leaderboard"]["ok"])
            self.assertEqual(store._dependencies["leaderboard"]["mode"], "degraded-stale-cache")

    def test_leaderboard_timeout_is_explicit_failure(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = TournamentStore(root=root, runtime=root / "viz" / "runtime")
            with patch("urllib.request.urlopen", side_effect=TimeoutError("synthetic timeout")):
                store._refresh_leaderboard(20.0)
            self.assertFalse(store._dependencies["leaderboard"]["ok"])
            self.assertEqual(store._dependencies["leaderboard"]["error"], "TimeoutError")

    def test_partial_document_cache_is_explicitly_degraded(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "data").mkdir()
            archives = root / "public-cases-ehl" / "cases"
            archives.mkdir(parents=True)
            (root / "data" / "keys.json").write_text(json.dumps({"1": "synthetic-key"}))
            (archives / "case_1.zip").write_bytes(b"synthetic-archive-marker")
            store = object.__new__(TournamentStore)
            store.root = root
            store._rows_by_game = {1: [], 2: []}
            store._dependencies = {}
            self.assertEqual(store._document_games(), {1})
            self.assertFalse(store._dependencies["documents"]["ok"])
            self.assertEqual(store._dependencies["documents"]["mode"], "partial-local-cache")
            self.assertEqual(store._dependencies["documents"]["missingPlayedGames"], 1)


class IntelligenceMaterialisationTests(unittest.TestCase):
    def test_operations_context_exposes_stale_recorder_and_deadline_denominators(self) -> None:
        def milestone(kind: str, elapsed: float, *, tier: int | None = None,
                      ok: bool | None = None) -> dict[str, object]:
            row: dict[str, object] = {
                "type": kind, "seq": int(elapsed) + 1,
                "ts": "2026-01-01T00:10:00+00:00",
                "elapsedFromStartMs": elapsed,
            }
            if tier is not None:
                row["tier"] = tier
            if ok is not None:
                row["ok"] = ok
            return row

        game_one_milestones = [
            milestone("round.scheduled", 0), milestone("key.received", 100),
            milestone("case.decrypted", 500), milestone("case.parsed", 900),
            milestone("submission.built", 1_500),
            milestone("submission.sent", 1_800, tier=1, ok=True),
            milestone("submission.sent", 50_000, tier=2, ok=True),
            milestone("submission.verified", 51_000),
            milestone("round.played", 60_000),
        ]
        store = object.__new__(TournamentStore)
        store._overview = {"race": {"gameIds": [1, 2, 3]}}
        store._dependencies = {}
        store._events = {
            "pipelines": {
                1: {
                    "available": True, "milestones": game_one_milestones,
                    "activities": [
                        {"type": "item.belief", "elapsedFromStartMs": 1_000,
                         "firstTs": "2026-01-01T00:10:01+00:00"},
                        {"type": "item.decided", "elapsedFromStartMs": 1_400,
                         "firstTs": "2026-01-01T00:10:01.4+00:00"},
                    ],
                    "eventCounts": {stage: 1 for stage in PIPELINE_CORE},
                    "eventCount": 11, "alerts": {}, "completeness": 1.0,
                    "observedSpanMs": 60_000,
                },
                2: {
                    "available": True,
                    "milestones": [milestone("round.scheduled", 0),
                                   milestone("submission.sent", 2_500, tier=1, ok=False)],
                    "activities": [],
                    "eventCounts": {"round.scheduled": 1, "submission.sent": 1},
                    "eventCount": 2, "alerts": {"warning": 1},
                    "completeness": 0.2, "observedSpanMs": 2_500,
                },
            },
            "live": [
                {"type": "submission.sent", "game": 2, "seq": 5,
                 "ts": "2026-01-01T00:10:00+00:00", "tier": 1,
                 "ok": False, "latencyMs": 50, "status": 503},
            ],
        }
        result = store._operations_context(datetime(2026, 1, 1, 0, 20,
                                                    tzinfo=timezone.utc))
        summary = result["summary"]
        self.assertEqual((result["schemaVersion"], result["telemetryStatus"],
                          result["latestPlayedGame"], result["latestRecordedGame"],
                          result["lagPlayedGames"]),
                         (1, "stale-played-rounds", 3, 2, 1))
        self.assertEqual((summary["playedGames"], summary["pipelineGames"],
                          summary["recordedPlayedGames"], summary["missingPlayedGames"],
                          summary["completeCoreGames"]), (3, 2, 2, 1, 1))
        self.assertEqual((summary["tier1Observed"], summary["tier1AtOrUnderTarget"],
                          summary["tier2Observed"], summary["tier2AtOrUnderDeadline"],
                          summary["failedSubmissionCalls"], summary["alerts"]),
                         (2, 1, 1, 1, 1, 1))
        self.assertEqual(len(result["games"]), 3)
        self.assertFalse(result["games"][-1]["recorded"])
        self.assertEqual(set(result["games"][0]["stageTimesMs"]), set(PIPELINE_CORE))
        self.assertEqual(store._dependencies["operationsTelemetry"]["mode"],
                         "stale-played-rounds")
        self.assertFalse(store._dependencies["operationsTelemetry"]["ok"])

    def test_market_microstructure_reconciles_every_directed_settlement_edge(self) -> None:
        groups: dict[tuple[int, int, str], ChargeGroup] = {}

        def group(game: int, item: int, issuer: str,
                  rows: list[tuple[str, bool, float]]) -> None:
            value = ChargeGroup(game, item, issuer)
            for reviewer, accepted, amount in rows:
                value.add(reviewer, accepted, amount)
            groups[(game, item, issuer)] = value

        group(1, 1, "Synthetic A", [("Oasis", True, 100), ("Synthetic B", False, 100)])
        group(1, 2, "Oasis", [("Synthetic A", True, 300), ("Synthetic B", False, 0)])
        group(2, 1, "Synthetic B", [("Oasis", False, 0), ("Synthetic A", False, 0)])
        store = object.__new__(TournamentStore)
        store._groups = groups
        store._thresholds = {
            (1, 1): {"tLo": 120, "tHi": 150},
            (1, 2): {"tLo": 80, "tHi": 120},
            (2, 1): {"tLo": 50, "tHi": 75},
        }
        race = {
            "gameIds": [1, 2],
            "series": [
                {"team": "Oasis", "rounds": [200, 0], "total": 200},
                {"team": "Synthetic A", "rounds": [-100, 0], "total": -100},
                {"team": "Synthetic B", "rounds": [-150, 0], "total": -150},
            ],
        }
        market = store._build_market("2026-01-01T00:00:00+00:00", race)
        summaries = {row["team"]: row for row in market["summaries"]}
        edges = {(row["issuer"], row["reviewer"]): row for row in market["edges"]}

        self.assertEqual((len(market["teams"]), len(edges), len(market["timeline"])),
                         (3, 6, 6))
        self.assertEqual(market["schemaVersion"], 2)
        cube = market["edgeTimeline"]
        self.assertEqual(cube["encoding"], "dense-array-v1")
        self.assertEqual(len(cube["rows"]), 3 * 2 * 2)
        frames = [dict(zip(cube["columns"], row, strict=True)) for row in cube["rows"]]
        self.assertEqual(len({(row["game"], row["issuerIndex"], row["reviewerIndex"])
                              for row in frames}), len(frames))
        self.assertEqual(sum(row["decisions"] for row in frames), 6)
        for edge in market["edges"]:
            issuer_index = market["teams"].index(edge["issuer"])
            reviewer_index = market["teams"].index(edge["reviewer"])
            selected = [row for row in frames
                        if row["issuerIndex"] == issuer_index and
                        row["reviewerIndex"] == reviewer_index]
            self.assertEqual(sum(row["decisions"] for row in selected), edge["decisions"])
            self.assertAlmostEqual(sum(row["issuerIncome"] for row in selected),
                                   edge["issuerIncome"], places=2)
            self.assertAlmostEqual(sum(row["reviewerCost"] for row in selected),
                                   edge["reviewerCost"], places=2)
        self.assertEqual(sum(row["decisions"] for row in edges.values()), 6)
        self.assertEqual((summaries["Oasis"]["issuedIncome"],
                          summaries["Oasis"]["reviewerCost"],
                          summaries["Oasis"]["net"]), (300, 100, 200))
        self.assertEqual((summaries["Synthetic A"]["wrongReviewCost"],
                          summaries["Synthetic B"]["wrongReviewCost"]), (300, 150))
        self.assertEqual(edges[("Synthetic A", "Synthetic B")]["penaltyWedge"], 50)
        self.assertEqual(edges[("Oasis", "Synthetic A")]["acceptFraudCount"], 1)
        self.assertEqual(edges[("Synthetic B", "Oasis")]["hiddenFraud"], 1)
        self.assertTrue(all(row["scoreReconciliationDelta"] == 0
                            for row in market["summaries"]))
        for team, summary in summaries.items():
            last = [row for row in market["timeline"] if row["team"] == team][-1]
            self.assertEqual(last["officialCumulativeScore"], summary["officialTotal"])
        serialized = json.dumps(market)
        for forbidden in ("description", "policy", "damage", "photo", "fair_charges"):
            self.assertNotIn(forbidden, serialized)

    def test_reviewer_lab_preserves_observability_and_reconciles_priced_cells(self) -> None:
        groups: dict[tuple[int, int, str], ChargeGroup] = {}

        def group(item: int, issuer: str, rows: list[tuple[str, bool, float]]) -> None:
            value = ChargeGroup(1, item, issuer)
            for reviewer, accepted, amount in rows:
                value.add(reviewer, accepted, amount)
            groups[(1, item, issuer)] = value

        group(1, "Synthetic A", [("Oasis", False, 100), ("Peer", True, 100)])
        group(2, "Synthetic B", [("Oasis", True, 300), ("Peer", False, 0)])
        group(3, "Synthetic C", [("Oasis", False, 0), ("Peer", False, 0)])
        group(4, "Synthetic D", [("Oasis", True, 40), ("Peer", True, 40)])
        group(5, "Synthetic E", [("Oasis", True, 75), ("Peer", True, 75)])
        store = object.__new__(TournamentStore)
        store._groups = groups
        store._thresholds = {
            (1, 1): {"tLo": 120, "tHi": 150},
            (1, 2): {"tLo": 80, "tHi": 120},
            (1, 3): {"tLo": 80, "tHi": 120},
            (1, 4): {"tLo": 50, "tHi": 100},
            (1, 5): {"tLo": 50, "tHi": 100},
        }
        store._events = {
            "decisions": {(1, item): {"a": 1, "b": limit}
                          for item, limit in ((1, 80), (2, 350), (3, 100), (4, 50), (5, 90))},
            "beliefs": {(1, item): {"source": "synthetic"} for item in range(1, 6)},
        }
        lab = store._build_reviewer_lab("2026-01-01T00:00:00+00:00")
        summary = lab["summary"]
        self.assertEqual((summary["cells"], summary["provenCells"],
                          summary["unprovenCells"]), (5, 4, 1))
        self.assertEqual(summary["observedReviewerCost"], 565)
        self.assertEqual((summary["fairExactEligible"],
                          summary["fraudDownshiftEligible"],
                          summary["hiddenFraudEligible"]), (2, 1, 1))
        self.assertEqual((summary["limitConsistent"], summary["limitIndeterminate"],
                          summary["limitInconsistent"], summary["limitMissing"]),
                         (2, 3, 0, 0))
        inferred = next(row for row in lab["cells"] if row["item"] == 4)
        self.assertEqual((inferred["provenClass"], inferred["chargeKind"],
                          inferred["evidenceKind"]),
                         ("fair", "exact", "sanctioned-floor-exact"))
        hidden = next(row for row in lab["cells"] if row["item"] == 3)
        self.assertIsNone(hidden["charge"])
        self.assertTrue(hidden["hiddenFraudEligible"])
        serialized = json.dumps(lab)
        for forbidden in ("description", "policy", "damage", "photo", "fair_charges"):
            self.assertNotIn(forbidden, serialized)

    def test_event_time_normalises_epoch_and_iso_without_accepting_bad_ranges(self) -> None:
        iso, epoch = _event_time(1_700_000_000.25)
        self.assertEqual(iso, "2023-11-14T22:13:20.250000+00:00")
        self.assertEqual(epoch, 1_700_000_000.25)
        self.assertEqual(_event_time("2023-11-14T22:13:20Z"),
                         ("2023-11-14T22:13:20+00:00", 1_700_000_000.0))
        self.assertEqual(_event_time("not-a-time"), ("", None))
        self.assertEqual(_event_time(12), ("", None))

    def test_event_flight_recorder_is_complete_timed_and_sanitized(self) -> None:
        events = [
            (1, "round.scheduled", {}, 0.0),
            (2, "key.received", {"ms": 80, "case": "do-not-copy"}, 1.0),
            (3, "case.decrypted", {"ms": 120, "files": ["a", "b"]}, 3.0),
            (4, "case.parsed", {"n_items": 2, "items": ["do-not-copy"]}, 5.0),
            (5, "item.belief", {"idx": 1, "median": 100, "sigma": .2,
                                 "source": "synthetic"}, 6.0),
            (6, "rule.fired", {"idx": 1, "rule": "synthetic", "shadow": True,
                                "from": [90, 90], "to": [100, 100],
                                "note": "do-not-copy"}, 6.2),
            (7, "item.decided", {"idx": 1, "a": 100, "b": 100}, 7.0),
            (8, "submission.built", {"tier": 1, "n_items": 2,
                                      "total_a": 200, "total_b": 200}, 8.0),
            (9, "submission.sent", {"tier": 1, "ok": True, "status": 200,
                                     "ms": 95, "detail": "do-not-copy"}, 9.0),
            (10, "submission.verified", {"tier": 1, "ok": True,
                                          "detail": "do-not-copy"}, 10.0),
            (11, "round.played", {"played": 7}, 11.0),
            (12, "alert", {"level": "error", "msg": "do-not-copy"}, 30.0),
            (13, "alert", {"level": "do-not-copy", "msg": "do-not-copy"}, 31.0),
        ]
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "events.jsonl"
            path.write_text("\n".join(json.dumps({
                "seq": seq, "round": 7, "type": event_type,
                "ts": 1_700_000_000 + offset, "payload": payload,
            }) for seq, event_type, payload, offset in events))
            store = object.__new__(TournamentStore)
            store.events_path = path
            store._dependencies = {}
            parsed = store._read_events()

        flight = parsed["pipelines"][7]
        self.assertEqual((flight["observedCoreStages"], flight["coreStageDenominator"]),
                         (10, 10))
        self.assertEqual(flight["completeness"], 1.0)
        self.assertEqual(flight["observedSpanMs"], 11_000.0)
        self.assertEqual(flight["alerts"], {"error": 1, "other": 1})
        activities = {row["type"]: row for row in flight["activities"]}
        self.assertEqual(activities["item.belief"]["count"], 1)
        self.assertEqual(activities["rule.fired"]["durationMs"], 0.0)
        sent = next(row for row in flight["milestones"]
                    if row["type"] == "submission.sent")
        self.assertEqual((sent["status"], sent["latencyMs"], sent["ok"]),
                         (200, 95.0, True))
        played = next(row for row in flight["milestones"]
                      if row["type"] == "round.played")
        self.assertEqual(played["playedCount"], 7)
        serialized = json.dumps(flight)
        self.assertNotIn("do-not-copy", serialized)
        self.assertNotIn("detail", serialized)
        self.assertNotIn("note", serialized)
        replay = parsed["replays"][7]
        self.assertEqual((replay["eventCount"], replay["itemCount"],
                          replay["beliefEvents"], replay["ruleEvents"],
                          replay["decisionEvents"]), (3, 1, 1, 1, 1))
        self.assertEqual([row["elapsedFromStartMs"] for row in replay["events"]],
                         [6000.0, 6200.0, 7000.0])
        self.assertEqual(replay["events"][0]["source"], "synthetic")
        self.assertEqual(replay["events"][1]["to"], [100.0, 100.0])
        replay_serialized = json.dumps(replay)
        self.assertNotIn("do-not-copy", replay_serialized)
        self.assertNotIn("note", replay_serialized)

    def test_proven_charge_respects_strict_bracket_boundaries(self) -> None:
        threshold = {"tLo": 100.0, "tHi": 120.0}
        self.assertEqual(_proven_charge(100.0, threshold),
                         ("at-or-under-floor", 1600.0))
        self.assertEqual(_proven_charge(120.0, threshold), ("unprovable", None))
        self.assertEqual(_proven_charge(120.01, threshold), ("above-ceiling", 0.0))
        self.assertEqual(_proven_charge(50.0, None), ("unlabelled", None))
        self.assertEqual(_proven_charge(-1.0, threshold), ("invalid", None))

    def test_percentile_interpolates_and_handles_empty_input(self) -> None:
        self.assertEqual(_percentile([10, 20, 30, 40], 0.5), 25)
        self.assertEqual(_percentile([10, 20, 30, 40], 0.95), 38.5)
        self.assertIsNone(_percentile([], 0.5))

    def test_rank_dynamics_preserves_rank_history_and_five_game_momentum(self) -> None:
        race = {
            "gameIds": [1, 2, 3],
            "series": [
                {"team": "Oasis", "scores": [0, 10, 5], "rounds": [0, 10, -5]},
                {"team": "Synthetic", "scores": [1, 2, 3], "rounds": [1, 1, 1]},
            ],
        }
        result = TournamentStore._rank_dynamics(race)
        oasis = next(row for row in result["teams"] if row["team"] == "Oasis")
        self.assertEqual(oasis["ranks"], [2, 1, 1])
        self.assertEqual(oasis["bestRank"], 1)
        self.assertEqual(oasis["momentum5"], 5)

    def test_race_robustness_lenses_use_each_teams_own_rounds(self) -> None:
        store = object.__new__(TournamentStore)
        rows = [
            (1, "Oasis", 100.0), (2, "Oasis", -50.0),
            (3, "Oasis", 20.0), (4, "Oasis", 10.0), (5, "Oasis", -5.0),
        ]
        race = store._build_race(rows)
        oasis = race["series"][0]
        self.assertEqual(oasis["total"], 75.0)
        self.assertEqual(oasis["medianPaceTotal"], 50.0)
        self.assertEqual(oasis["winsorizedTotal"], 61.0)
        self.assertEqual(oasis["withoutTop3Positive"], -55.0)
        self.assertEqual(oasis["withoutWorst3Negative"], 130.0)
        self.assertEqual(oasis["positiveTop3Share"], 1.0)
        self.assertEqual(oasis["bestRound"], {"game": 1, "score": 100.0})
        self.assertEqual(oasis["worstRound"], {"game": 2, "score": -50.0})

    def test_rule_intelligence_reconciles_fixed_denominator_and_hidden_exposure(self) -> None:
        store = object.__new__(TournamentStore)
        store._thresholds = {
            (1, 1): {"tLo": 100.0, "tHi": 110.0},
            (1, 2): {"tLo": 100.0, "tHi": 110.0},
        }
        store._events = {"rules": {
            (1, 1): [{
                "rule": "synthetic_rule", "shadow": True, "seq": 1,
                "from": [50.0, 80.0], "to": [120.0, 130.0],
            }],
            (1, 2): [{
                "rule": "synthetic_rule", "shadow": True, "seq": 2,
                "from": [150.0, 50.0], "to": [100.0, 40.0],
            }],
            (1, 3): [{
                "rule": "active_count_only", "shadow": False, "seq": 3,
                "from": None, "to": None,
            }],
        }}
        index = [
            {"game": 1, "item": 1, "field": {"hidden": 3}},
            {"game": 1, "item": 2, "field": {"hidden": 7}},
        ]
        result = store._rule_intelligence(index)
        shadow = next(row for row in result["rules"] if row["shadow"])
        active = next(row for row in result["rules"] if not row["shadow"])

        self.assertEqual((result["firings"], result["pairedFirings"],
                          result["ruleVariants"]), (3, 2, 2))
        self.assertEqual((shadow["before"]["bestPossible"],
                          shadow["after"]["bestPossible"]), (3200.0, 3200.0))
        self.assertEqual((shadow["before"]["score"], shadow["after"]["score"]),
                         (0.25, 0.5))
        self.assertEqual(shadow["provenIncomeDelta"], 800.0)
        self.assertEqual((shadow["limitRaises"], shadow["limitLowers"]), (1, 1))
        self.assertEqual(shadow["hiddenChargesOnLimitRaises"], 3)
        self.assertEqual(shadow["bucketLimitMoves"], [{
            "bucket": "50–400", "items": 2, "raise": 1, "lower": 1,
            "same": 0, "medianDelta": 20.0, "hiddenChargesOnRaises": 3,
        }])
        transitions = {(row["from"], row["to"]): row["items"]
                       for row in shadow["transitions"]}
        self.assertEqual(transitions, {
            ("at-or-under-floor", "above-ceiling"): 1,
            ("above-ceiling", "at-or-under-floor"): 1,
        })
        self.assertEqual((active["firings"], active["paired"]), (1, 0))
        self.assertEqual(active["before"]["score"], None)

    def test_shadow_portfolios_dedupe_latest_firing_and_measure_rule_opposition(self) -> None:
        store = object.__new__(TournamentStore)
        store._thresholds = {
            (1, 1): {"tLo": 100.0, "tHi": 110.0},
            (1, 2): {"tLo": 100.0, "tHi": 110.0},
        }
        store._events = {"rules": {
            (1, 1): [
                {"rule": "rule_a", "shadow": True, "seq": 1,
                 "from": [50.0, 80.0], "to": [120.0, 130.0]},
                {"rule": "rule_a", "shadow": True, "seq": 2,
                 "from": [50.0, 80.0], "to": [90.0, 95.0]},
                {"rule": "rule_b", "shadow": True, "seq": 4,
                 "from": [50.0, 80.0], "to": [30.0, 70.0]},
            ],
            (1, 2): [
                {"rule": "rule_a", "shadow": True, "seq": 3,
                 "from": [150.0, 50.0], "to": [100.0, 40.0]},
            ],
        }}
        index = [
            {"game": 1, "item": 1, "source": "synthetic", "field": {"hidden": 3}},
            {"game": 1, "item": 2, "source": "synthetic", "field": {"hidden": 7}},
        ]

        portfolios = store._rule_intelligence(index)["portfolios"]
        rule_a = next(row for row in portfolios["rules"] if row["rule"] == "rule_a")
        self.assertEqual((rule_a["pairedFirings"], rule_a["uniqueItems"],
                          rule_a["duplicateFirings"], rule_a["unstableItems"]),
                         (3, 2, 1, 1))
        self.assertEqual((rule_a["before"]["score"], rule_a["after"]["score"]),
                         (0.25, 0.95))
        self.assertEqual(rule_a["provenIncomeDelta"], 2240.0)
        latest_a_item_1 = next(
            row for row in portfolios["records"]
            if row["rule"] == "rule_a" and row["item"] == 1
        )
        self.assertEqual((latest_a_item_1["seq"], latest_a_item_1["after"]),
                         (2, [90.0, 95.0]))
        self.assertEqual((latest_a_item_1["repeatFirings"],
                          latest_a_item_1["candidateStable"]), (2, False))
        self.assertEqual((portfolios["uniqueItems"], portfolios["multiRuleItems"]), (2, 1))
        self.assertEqual(len(portfolios["records"]), 3)
        overlap = portfolios["overlaps"][0]
        self.assertEqual((overlap["items"], overlap["directionComparable"],
                          overlap["directionAgreement"], overlap["directionOpposition"]),
                         (1, 1, 0, 1))
        self.assertEqual(overlap["directionAgreementRate"], 0.0)

    def test_transaction_only_item_is_present_in_global_index(self) -> None:
        store = object.__new__(TournamentStore)
        store._events = {"decisions": {}, "beliefs": {}, "rules": {}, "replays": {
            3: {"events": [
                {"type": "item.belief", "item": 7},
                {"type": "item.decided", "item": 7},
            ]},
        }}
        store._thresholds = {}
        group = ChargeGroup(3, 7, "Synthetic")
        group.add("Oasis", False, 0)
        store._groups = {(3, 7, "Synthetic"): group}
        rows = store._build_item_index({3})
        self.assertEqual([(row["game"], row["item"]) for row in rows], [(3, 7)])
        self.assertEqual(rows[0]["status"], "unlabelled")
        self.assertEqual(rows[0]["field"]["hidden"], 1)
        self.assertEqual(rows[0]["replayCount"], 2)
        self.assertTrue(rows[0]["documentsAvailable"])

    def test_phase_windows_keep_fixed_denominators(self) -> None:
        rows = [{"game": game, "net": float(game), "income": float(game * 2),
                 "cost": float(game)} for game in range(1, 13)]
        phases = TournamentStore._phase_rows(rows, size=10)
        self.assertEqual([(row["startGame"], row["endGame"], row["games"])
                          for row in phases], [(1, 10, 10), (11, 12, 2)])

    def test_risk_lattice_keeps_direction_and_limit_denominators_explicit(self) -> None:
        rows = [
            {"source": "synthetic", "tLo": 100, "a": 50, "b": 80,
             "status": "under", "logError": -0.6931, "foregoneLowerBound": 800},
            {"source": "synthetic", "tLo": 100, "a": 300, "b": 250,
             "status": "over", "logError": 1.0986, "foregoneLowerBound": 0},
            {"source": "synthetic", "tLo": 100, "a": 150, "b": 120,
             "status": "above-floor-open-ceiling", "logError": 0.4055,
             "foregoneLowerBound": 0},
            {"source": "synthetic", "tLo": None, "a": 50, "b": 50,
             "status": "unlabelled", "logError": None, "foregoneLowerBound": 0},
        ]
        result = TournamentStore._risk_rows(rows)
        cell = result["cells"][0]
        self.assertEqual(result["labelledItems"], 3)
        self.assertEqual(cell["bucket"], "50–400")
        self.assertEqual((cell["under"], cell["over"], cell["notProvenWrong"]), (1, 1, 1))
        self.assertEqual(cell["wrongRate"], 0.6667)
        self.assertEqual(cell["medianLimitMinusFloor"], 20)
        self.assertEqual(cell["limitBelowFloorRate"], 0.3333)

    def test_opponent_dossier_reconciles_payoff_cells_and_issued_evidence(self) -> None:
        store = object.__new__(TournamentStore)
        oasis_fair = ChargeGroup(1, 1, "Oasis")
        oasis_fair.add("Synthetic", False, 100)
        oasis_fair.add("Third", True, 100)
        oasis_fraud = ChargeGroup(1, 2, "Oasis")
        oasis_fraud.add("Synthetic", True, 40)
        oasis_fraud.add("Third", False, 0)
        issued_under = ChargeGroup(1, 1, "Synthetic")
        issued_under.add("Oasis", False, 50)
        issued_over = ChargeGroup(1, 2, "Synthetic")
        issued_over.add("Oasis", True, 200)
        issued_over.add("Third", False, 0)
        store._groups = {
            (1, 1, "Oasis"): oasis_fair,
            (1, 2, "Oasis"): oasis_fraud,
            (1, 1, "Synthetic"): issued_under,
            (1, 2, "Synthetic"): issued_over,
        }
        store._thresholds = {
            (1, 1): {"tLo": 100, "tHi": 120},
            (1, 2): {"tLo": 100, "tHi": 150},
        }
        row = next(item for item in store._opponents() if item["team"] == "Synthetic")
        self.assertEqual(row["reviewDecisions"], 2)
        self.assertEqual(row["reviewCells"]["rejectFair"], {"count": 1, "euros": 150.0})
        self.assertEqual(row["reviewCells"]["acceptFraud"], {"count": 1, "euros": 40.0})
        self.assertEqual(row["fairRejectRateAgainstUs"], 1.0)
        self.assertEqual(row["fraudAcceptRateAgainstUs"], 1.0)
        self.assertEqual(row["issuedEvidence"]["under"], 1)
        self.assertEqual(row["issuedEvidence"]["over"], 1)
        self.assertEqual(row["netExchange"], -135.0)

    def test_item_capital_flows_reconcile_observed_income_and_reviewer_cost(self) -> None:
        store = object.__new__(TournamentStore)
        store._rows_by_game = {
            1: [
                (1, "Oasis", "Synthetic", 1, True, 100.0),
                (1, "Oasis", "Third", 1, True, 100.0),
            ],
        }
        fair = ChargeGroup(1, 1, "Synthetic")
        fair.add("Oasis", False, 50.0)
        fair.add("Third", True, 50.0)
        fraud = ChargeGroup(1, 2, "Third")
        fraud.add("Oasis", True, 40.0)
        fraud.add("Synthetic", False, 0.0)
        store._groups = {(1, 1, "Synthetic"): fair, (1, 2, "Third"): fraud}

        rows = store._game_item_economics(1)
        self.assertEqual(rows[1]["issuerIncome"], 200.0)
        self.assertEqual(rows[1]["reviewerCost"], 75.0)
        self.assertEqual(rows[1]["netContribution"], 125.0)
        self.assertEqual(rows[1]["matrix"]["rejectFair"], {"cost": 75.0, "count": 1})
        self.assertEqual(rows[2]["reviewerCost"], 40.0)
        self.assertEqual(rows[2]["matrix"]["acceptFraud"], {"cost": 40.0, "count": 1})
        self.assertEqual(sum(row["issuerIncome"] for row in rows.values()), 200.0)
        self.assertEqual(sum(row["reviewerCost"] for row in rows.values()), 115.0)


if __name__ == "__main__":
    unittest.main()
