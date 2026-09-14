"""Read-only data materialisation for the local tournament dashboard.

The production database is never opened without SQLite URI ``mode=ro``. Derived
material is written only below ``viz/runtime`` (which is gitignored because case
manifests can contain claim text).
"""
from __future__ import annotations

import copy
import json
import math
import os
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


US = "Oasis"
CADENCE_SECONDS = 757.6
LEADERBOARD_URL = "http://127.0.0.1:8080/api/leaderboard"
MAX_REMOTE_BYTES = 5_000_000
ROOT = Path(__file__).resolve().parent.parent
VIZ_ROOT = Path(__file__).resolve().parent
RUNTIME = VIZ_ROOT / "runtime"
DB_PATH = ROOT / "data" / "c2f.sqlite"
EVENTS_PATH = ROOT / "data" / "events" / "tournament.jsonl"
PIPELINE_MILESTONES = {
    "round.scheduled", "key.received", "case.decrypted", "case.parsed",
    "prior.prefetched", "submission.built", "submission.sent",
    "submission.verified", "round.closed", "round.played",
}
PIPELINE_ACTIVITIES = {"item.belief", "rule.fired", "item.decided"}
PIPELINE_CORE = (
    "round.scheduled", "key.received", "case.decrypted", "case.parsed",
    "item.belief", "item.decided", "submission.built", "submission.sent",
    "submission.verified", "round.played",
)


class DataUnavailable(RuntimeError):
    """A required read-only input could not be materialised."""


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _money(value: float) -> float:
    return round(_finite(value), 2)


def _median(values: Iterable[float]) -> float | None:
    clean = [_finite(v) for v in values if math.isfinite(_finite(v))]
    return round(statistics.median(clean), 4) if clean else None


def _rolling_median(values: list[float], window: int = 5) -> list[float]:
    return [round(statistics.median(values[max(0, i - window + 1): i + 1]), 2)
            for i in range(len(values))]


def _percentile(values: Iterable[float], quantile: float) -> float | None:
    clean = sorted(_finite(value) for value in values if math.isfinite(_finite(value)))
    if not clean:
        return None
    position = (len(clean) - 1) * min(1.0, max(0.0, quantile))
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return round(clean[lower], 2)
    weight = position - lower
    return round(clean[lower] * (1 - weight) + clean[upper] * weight, 2)


def _proven_charge(charge: float, threshold: dict[str, Any] | None) -> tuple[str, float | None]:
    """Classify a candidate only where the sanctioned bracket proves its side."""
    if threshold is None:
        return "unlabelled", None
    value = _finite(charge, float("nan"))
    if not math.isfinite(value) or value < 0:
        return "invalid", None
    if value <= float(threshold["tLo"]):
        return "at-or-under-floor", 16 * value
    if threshold.get("tHi") is not None and value > float(threshold["tHi"]):
        return "above-ceiling", 0.0
    return "unprovable", None


def _floor_bucket(value: Any) -> str:
    floor = _finite(value, float("nan"))
    if not math.isfinite(floor):
        return "unlabelled"
    if floor < 50:
        return "0–50"
    if floor < 400:
        return "50–400"
    if floor < 1200:
        return "400–1200"
    return "1200+"


def _event_time(value: Any) -> tuple[str, float | None]:
    """Normalise numeric or ISO event timestamps without inventing a time."""
    if isinstance(value, bool) or value is None:
        return "", None
    try:
        epoch = float(value)
    except (TypeError, ValueError):
        epoch = float("nan")
    if math.isfinite(epoch):
        if not 946_684_800 <= epoch <= 4_102_444_800:
            return "", None
        moment = datetime.fromtimestamp(epoch, tz=timezone.utc)
        return moment.isoformat(), epoch
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        return "", None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    epoch = moment.timestamp()
    if not 946_684_800 <= epoch <= 4_102_444_800:
        return "", None
    return moment.isoformat(), epoch


def _bounded_event_number(value: Any, maximum: float, *, integer: bool = False) -> int | float | None:
    number = _finite(value, float("nan"))
    if not math.isfinite(number) or not 0 <= number <= maximum:
        return None
    if integer:
        return int(number) if number.is_integer() else None
    return round(number, 2)


def _pipeline_milestone(event_type: str, payload: dict[str, Any], seq: int,
                        timestamp: str, epoch: float | None) -> dict[str, Any]:
    """Keep only bounded numeric/status metadata from a pipeline event."""
    row: dict[str, Any] = {
        "type": event_type, "seq": seq, "ts": timestamp, "_epoch": epoch,
    }

    def keep(name: str, source: str, maximum: float, *, integer: bool = False) -> None:
        value = _bounded_event_number(payload.get(source), maximum, integer=integer)
        if value is not None:
            row[name] = value

    if event_type == "key.received":
        keep("reportedMs", "ms", 1_000_000)
    elif event_type == "case.decrypted":
        keep("reportedMs", "ms", 1_000_000)
        files = payload.get("files")
        if isinstance(files, (list, tuple)):
            row["files"] = min(len(files), 500)
        else:
            keep("files", "files", 500, integer=True)
    elif event_type == "case.parsed":
        keep("items", "n_items", 500, integer=True)
    elif event_type == "prior.prefetched":
        keep("reportedMs", "ms", 1_000_000)
        keep("items", "n", 500, integer=True)
    elif event_type == "submission.built":
        keep("tier", "tier", 2, integer=True)
        if row.get("tier") not in {1, 2}:
            row.pop("tier", None)
        keep("items", "n_items", 500, integer=True)
        keep("totalA", "total_a", 1_000_000_000)
        keep("totalB", "total_b", 1_000_000_000)
    elif event_type == "submission.sent":
        keep("tier", "tier", 2, integer=True)
        keep("latencyMs", "ms", 1_000_000)
        keep("status", "status", 599, integer=True)
        if row.get("status", 100) < 100:
            row.pop("status", None)
        if row.get("tier") not in {1, 2}:
            row.pop("tier", None)
        row["ok"] = payload.get("ok") is True
    elif event_type == "submission.verified":
        keep("tier", "tier", 2, integer=True)
        if row.get("tier") not in {1, 2}:
            row.pop("tier", None)
        row["ok"] = payload.get("ok") is True
    elif event_type == "round.closed":
        keep("elapsedSeconds", "elapsed_s", 10_000)
    elif event_type == "round.played":
        keep("playedCount", "played", 100, integer=True)
    return row


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(raw, 0o600)
        os.replace(raw, path)
    finally:
        try:
            os.unlink(raw)
        except FileNotFoundError:
            pass


def _readonly_connection(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise DataUnavailable(f"database not found: {path}")
    con = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=1.0)
    con.execute("PRAGMA query_only=ON")
    con.execute("PRAGMA busy_timeout=1000")
    return con


@dataclass
class ChargeGroup:
    game: int
    item: int
    issuer: str
    decisions: dict[str, tuple[bool, float]] = field(default_factory=dict)
    accepted_amounts: list[float] = field(default_factory=list)
    rejected_paid: list[float] = field(default_factory=list)
    rejected_unpaid: int = 0

    def add(self, reviewer: str, accepted: bool, amount: float) -> None:
        self.decisions[reviewer] = (accepted, amount)
        if accepted:
            if amount > 0:
                self.accepted_amounts.append(amount)
        elif amount > 0:
            self.rejected_paid.append(amount)
        else:
            self.rejected_unpaid += 1

    def observed(self) -> dict[str, Any]:
        """Return only what the settlement records prove about the submitted charge."""
        if self.rejected_paid and self.rejected_unpaid:
            return {
                "classification": "conflict",
                "charge": max(self.rejected_paid),
                "chargeKind": "inconsistent",
                "accepted": len(self.accepted_amounts),
                "reviewers": len(self.decisions),
            }
        if self.rejected_paid:
            # Rejected but paid is fair; issuer payout is the original charge a.
            return {
                "classification": "fair",
                "charge": max(self.rejected_paid),
                "chargeKind": "exact",
                "accepted": len(self.accepted_amounts),
                "reviewers": len(self.decisions),
            }
        if self.rejected_unpaid:
            visible = max(self.accepted_amounts) if self.accepted_amounts else None
            return {
                "classification": "fraud",
                "charge": visible,
                "chargeKind": "lower_bound" if visible is not None else "hidden",
                "accepted": len(self.accepted_amounts),
                "reviewers": len(self.decisions),
            }
        visible = max(self.accepted_amounts) if self.accepted_amounts else None
        return {
            "classification": "unresolved",
            "charge": visible,
            "chargeKind": "observed_payout" if visible is not None else "hidden",
            "accepted": len(self.accepted_amounts),
            "reviewers": len(self.decisions),
        }


class TournamentStore:
    """Thread-safe, bounded-refresh materialised view of all non-document data."""

    def __init__(self, *, root: Path = ROOT, runtime: Path = RUNTIME,
                 leaderboard_url: str = LEADERBOARD_URL) -> None:
        self.root = root.resolve()
        self.runtime = runtime.resolve()
        self.db_path = self.root / "data" / "c2f.sqlite"
        self.events_path = self.root / "data" / "events" / "tournament.jsonl"
        self.threshold_tool = self.root / "tools" / "thresholds.py"
        self.leaderboard_url = leaderboard_url
        self.runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.runtime, 0o700)
        self.cache_dir = self.runtime / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._lock = threading.RLock()
        self._last_refresh = 0.0
        self._fingerprint: tuple[Any, ...] | None = None
        self._threshold_fingerprint: tuple[Any, ...] | None = None
        self._overview: dict[str, Any] | None = None
        self._reviewer_lab: dict[str, Any] | None = None
        self._market: dict[str, Any] | None = None
        self._game_cache: dict[int, dict[str, Any]] = {}
        self._thresholds: dict[tuple[int, int], dict[str, Any]] = {}
        self._groups: dict[tuple[int, int, str], ChargeGroup] = {}
        self._rows_by_game: dict[int, list[tuple[Any, ...]]] = {}
        self._events: dict[str, Any] = {}
        self._leaderboard: dict[str, Any] | None = None
        self._leaderboard_last_attempt = 0.0
        self._leaderboard_failures = 0
        self._dependencies: dict[str, dict[str, Any]] = {}

    def _fingerprint_inputs(self, con: sqlite3.Connection) -> tuple[Any, ...]:
        tx = con.execute(
            "SELECT count(*),coalesce(max(game_id),0),coalesce(max(rowid),0) "
            "FROM transactions"
        ).fetchone()
        scores = con.execute(
            "SELECT count(*),coalesce(max(game_id),0),coalesce(max(rowid),0) FROM scores"
        ).fetchone()
        event_stat = self.events_path.stat() if self.events_path.exists() else None
        return (*tx, *scores,
                event_stat.st_size if event_stat else -1,
                event_stat.st_mtime_ns if event_stat else -1)

    def refresh(self, *, force: bool = False) -> None:
        with self._lock:
            now = time.monotonic()
            if not force and self._overview is not None and now - self._last_refresh < 4.0:
                return
            materialised = False
            try:
                with _readonly_connection(self.db_path) as con:
                    fingerprint = self._fingerprint_inputs(con)
                    changed = fingerprint != self._fingerprint
                    if changed or self._overview is None:
                        self._materialise(con, fingerprint)
                        self._fingerprint = fingerprint
                        self._game_cache.clear()
                        materialised = True
                    self._dependencies["database"] = {
                        "ok": True, "critical": True, "mode": "read-only",
                        "rows": int(fingerprint[0]),
                    }
            except (sqlite3.Error, OSError, DataUnavailable) as exc:
                self._dependencies["database"] = {
                    "ok": False, "critical": True, "error": type(exc).__name__,
                }
                if self._overview is None:
                    raise DataUnavailable(f"read-only database refresh failed: {exc}") from exc
            self._refresh_leaderboard(now)
            if self._overview is not None:
                self._overview["live"] = self._live_context()
                self._overview["dependencies"] = self._dependency_summary()
                if materialised:
                    _atomic_json(self.cache_dir / "overview.json", self._overview)
            self._last_refresh = now

    def _materialise(self, con: sqlite3.Connection,
                     fingerprint: tuple[Any, ...]) -> None:
        transaction_fingerprint = tuple(fingerprint[:3])
        if transaction_fingerprint != self._threshold_fingerprint or not self._thresholds:
            self._thresholds = self._run_thresholds(con, fingerprint)
            self._threshold_fingerprint = transaction_fingerprint
        self._events = self._read_events()
        rows = con.execute(
            "SELECT game_id,issuer,reviewer,line_item,accepted,amount "
            "FROM transactions ORDER BY game_id,line_item,issuer,reviewer"
        ).fetchall()
        score_rows = con.execute(
            "SELECT game_id,team,score FROM scores ORDER BY game_id,team"
        ).fetchall()
        game_rows = con.execute(
            "SELECT id,start_time,status FROM games ORDER BY id"
        ).fetchall()
        self._groups, self._rows_by_game = self._group_transactions(rows)
        document_games = self._document_games()
        race = self._build_race(score_rows)
        game_summaries, trends = self._build_trends(score_rows)
        item_index = self._build_item_index(document_games)
        intelligence = self._build_intelligence(
            race, trends, game_summaries, item_index, document_games
        )
        generated_at = datetime.now(timezone.utc).isoformat()
        self._reviewer_lab = self._build_reviewer_lab(generated_at)
        self._market = self._build_market(generated_at, race)
        self._overview = {
            "schemaVersion": 7,
            "generatedAt": generated_at,
            "team": US,
            "cadenceSeconds": CADENCE_SECONDS,
            "race": race,
            "games": [{"id": int(g), "startTime": start, "status": status,
                       "documentsAvailable": int(g) in document_games,
                       **game_summaries.get(int(g), {})}
                      for g, start, status in game_rows],
            "trends": trends,
            "itemIndex": item_index,
            "intelligence": intelligence,
            "thresholdCount": len(self._thresholds),
            "denominators": {
                "race": "cumulative team score in EUR per played game",
                "anatomy": "Oasis issuer/reviewer settlements in one game",
                "matrix": "proven issuer-side classifications; euros are reviewer cost",
                "thresholds": "one sanctioned bracket per (game, line item)",
                "strategy": "one Oasis decision per item with a sanctioned proven floor",
                "opponents": "one bilateral issuer/reviewer relationship per non-Oasis team",
            },
        }
        _atomic_json(self.cache_dir / "reviewer.json", self._reviewer_lab)
        _atomic_json(self.cache_dir / "market.json", self._market)

    def _document_games(self) -> set[int]:
        """Return games with both a cached key and archive, without exposing key material."""
        keys_path = self.root / "data" / "keys.json"
        archive_root = self.root / "public-cases-ehl" / "cases"
        try:
            raw = json.loads(keys_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("key cache schema mismatch")
            keyed = {int(game) for game, key in raw.items()
                     if str(game).isdigit() and isinstance(key, str) and bool(key)}
            archived = {
                game for game in range(101)
                if (archive_root / f"case_{game}.zip").is_file() or
                (archive_root / f"case_{game:02d}.zip").is_file()
            }
            available = keyed & archived
            played = set(self._rows_by_game)
            missing = played - available
            self._dependencies["documents"] = {
                "ok": not missing,
                "critical": False,
                "mode": "local-key-and-archive" if not missing else "partial-local-cache",
                "availableGames": len(available),
                "missingPlayedGames": len(missing),
                "latestAvailableGame": max(available, default=None),
            }
            return available
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._dependencies["documents"] = {
                "ok": False, "critical": False, "mode": "unavailable",
                "error": type(exc).__name__, "availableGames": 0,
            }
            return set()

    def _snapshot_database(self, con: sqlite3.Connection, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, raw_tmp = tempfile.mkstemp(
            prefix=f".{target.stem}.", suffix=".tmp.sqlite", dir=target.parent
        )
        os.close(descriptor)
        tmp = Path(raw_tmp)
        try:
            dst = sqlite3.connect(tmp)
            try:
                con.backup(dst)
                dst.execute("PRAGMA journal_mode=DELETE")
                dst.commit()
            finally:
                dst.close()
            os.chmod(tmp, 0o600)
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)

    def _run_thresholds(self, con: sqlite3.Connection,
                        fingerprint: tuple[Any, ...]) -> dict[tuple[int, int], dict[str, Any]]:
        snapshot = self.cache_dir / "threshold-source.sqlite"
        self._snapshot_database(con, snapshot)
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONPATH": str(self.root),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }
        try:
            proc = subprocess.run(
                [sys.executable, str(self.threshold_tool), "--db", str(snapshot), "--jsonl"],
                cwd=self.runtime, env=env, capture_output=True, text=True,
                timeout=45, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            self._dependencies["thresholds"] = {
                "ok": False, "critical": True, "error": type(exc).__name__,
            }
            raise DataUnavailable(f"threshold tool failed: {type(exc).__name__}") from exc
        if proc.returncode != 0:
            self._dependencies["thresholds"] = {
                "ok": False, "critical": True, "error": f"exit {proc.returncode}",
            }
            raise DataUnavailable(f"threshold tool exited {proc.returncode}")
        if len(proc.stdout.encode("utf-8")) > 10_000_000:
            raise DataUnavailable("threshold output exceeded 10 MB safety limit")
        thresholds: dict[tuple[int, int], dict[str, Any]] = {}
        for line_no, raw in enumerate(proc.stdout.splitlines(), start=1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
                game, item = int(row["game"]), int(row["item"])
                lo = float(row["t_lo"])
                hi = None if row.get("t_hi") is None else float(row["t_hi"])
                if game < 0 or item < 1 or lo < 0 or not math.isfinite(lo):
                    raise ValueError("invalid threshold domain")
                if hi is not None and (not math.isfinite(hi) or hi < 0):
                    raise ValueError("invalid upper bound")
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise DataUnavailable(f"invalid threshold JSONL at line {line_no}") from exc
            thresholds[(game, item)] = {
                "tLo": round(lo, 2), "tHi": None if hi is None else round(hi, 2),
                "nFair": int(row.get("n_fair", 0)),
                "nFraud": int(row.get("n_fraud", 0)),
                "fairCharges": [round(float(v), 2) for v in row.get("fair_charges", [])
                                if math.isfinite(float(v))],
            }
        self._dependencies["thresholds"] = {
            "ok": True, "critical": True, "mode": "sanctioned-tool",
            "rows": len(thresholds), "transactionFingerprint": list(fingerprint[:3]),
        }
        _atomic_json(self.cache_dir / "thresholds.json", {
            f"{g}:{i}": row for (g, i), row in thresholds.items()
        })
        return thresholds

    def _read_events(self) -> dict[str, Any]:
        decisions: dict[tuple[int, int], dict[str, Any]] = {}
        beliefs: dict[tuple[int, int], dict[str, Any]] = {}
        rules: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
        item_replay_events: dict[int, list[dict[str, Any]]] = defaultdict(list)
        live: list[dict[str, Any]] = []
        schedules: list[dict[str, Any]] = []
        pipeline_counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        pipeline_milestones: dict[int, list[dict[str, Any]]] = defaultdict(list)
        pipeline_activities: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
        pipeline_alerts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        max_seq = 0
        if not self.events_path.is_file():
            self._dependencies["events"] = {
                "ok": False, "critical": True, "error": "missing",
            }
            raise DataUnavailable("event log not found")
        try:
            with self.events_path.open("r", encoding="utf-8", errors="replace") as handle:
                for line_no, raw in enumerate(handle, start=1):
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        # A final partial line is expected while the daemon appends.
                        continue
                    try:
                        game = int(event.get("round"))
                    except (TypeError, ValueError):
                        continue
                    seq = int(event.get("seq") or line_no)
                    max_seq = max(max_seq, seq)
                    typ = str(event.get("type") or "")
                    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
                    ts, epoch = _event_time(event.get("ts"))
                    if typ:
                        pipeline_counts[game][typ] += 1
                    if typ in PIPELINE_MILESTONES:
                        pipeline_milestones[game].append(
                            _pipeline_milestone(typ, payload, seq, ts, epoch)
                        )
                    elif typ in PIPELINE_ACTIVITIES:
                        activity = pipeline_activities[game].setdefault(typ, {
                            "type": typ, "count": 0, "firstSeq": seq, "lastSeq": seq,
                            "firstTs": ts, "lastTs": ts,
                            "_firstEpoch": epoch, "_lastEpoch": epoch,
                        })
                        activity["count"] += 1
                        activity["lastSeq"] = seq
                        activity["lastTs"] = ts
                        if epoch is not None:
                            if activity["_firstEpoch"] is None or epoch < activity["_firstEpoch"]:
                                activity["_firstEpoch"] = epoch
                                activity["firstTs"] = ts
                            if activity["_lastEpoch"] is None or epoch > activity["_lastEpoch"]:
                                activity["_lastEpoch"] = epoch
                                activity["lastTs"] = ts
                    if typ == "item.decided":
                        try:
                            idx = int(payload["idx"])
                            a, b = float(payload["a"]), float(payload["b"])
                        except (KeyError, TypeError, ValueError):
                            continue
                        if all(math.isfinite(v) and v >= 0 for v in (a, b)):
                            decision_record = {
                                "a": round(a, 2), "b": round(b, 2),
                                "covered": bool(payload.get("covered", True)),
                                "seq": seq, "ts": ts,
                            }
                            decisions[(game, idx)] = decision_record
                            item_replay_events[game].append({
                                "type": typ, "seq": seq, "ts": ts, "_epoch": epoch,
                                "item": idx, "a": decision_record["a"],
                                "b": decision_record["b"],
                                "covered": decision_record["covered"],
                            })
                    elif typ == "item.belief":
                        try:
                            idx = int(payload["idx"])
                            median = float(payload["median"])
                            sigma = float(payload["sigma"])
                        except (KeyError, TypeError, ValueError):
                            continue
                        if math.isfinite(median) and math.isfinite(sigma):
                            belief_record = {
                                "median": round(median, 2), "sigma": round(sigma, 4),
                                "source": str(payload.get("source") or "unknown")[:120],
                                "seq": seq, "ts": ts,
                            }
                            beliefs[(game, idx)] = belief_record
                            item_replay_events[game].append({
                                "type": typ, "seq": seq, "ts": ts, "_epoch": epoch,
                                "item": idx, "median": belief_record["median"],
                                "sigma": belief_record["sigma"],
                                "source": belief_record["source"],
                            })
                    elif typ == "rule.fired":
                        try:
                            idx = int(payload["idx"])
                        except (KeyError, TypeError, ValueError):
                            continue
                        before = payload.get("from")
                        after = payload.get("to")
                        rule_record = {
                            "rule": str(payload.get("rule") or "unnamed")[:120],
                            "shadow": bool(payload.get("shadow")),
                            "from": self._pair(before), "to": self._pair(after),
                            "seq": seq, "ts": ts,
                        }
                        rules[(game, idx)].append(rule_record)
                        item_replay_events[game].append({
                            "type": typ, "item": idx, "_epoch": epoch, **rule_record,
                        })
                    elif typ == "round.scheduled":
                        schedules.append({"game": game, "ts": ts, "seq": seq})
                    elif typ.startswith("submission.") or typ in {"round.played", "alert"}:
                        item: dict[str, Any] = {
                            "seq": seq, "game": game, "ts": ts, "type": typ,
                        }
                        if typ == "submission.sent":
                            item.update({
                                "ok": bool(payload.get("ok")),
                                "status": int(payload["status"]) if isinstance(payload.get("status"), int) else None,
                                "latencyMs": round(_finite(payload.get("ms")), 1),
                                "tier": int(payload["tier"]) if isinstance(payload.get("tier"), int) else None,
                            })
                        elif typ == "submission.verified":
                            item.update({"ok": bool(payload.get("ok")), "tier": payload.get("tier")})
                        elif typ == "alert":
                            # Alert text can contain claim material. Preserve severity only.
                            raw_level = str(payload.get("level") or "warning").casefold()
                            level = {
                                "warn": "warning", "warning": "warning",
                                "error": "error", "critical": "critical",
                                "info": "info", "debug": "debug",
                            }.get(raw_level, "other")
                            item["level"] = level
                            pipeline_alerts[game][level] += 1
                        live.append(item)
        except OSError as exc:
            self._dependencies["events"] = {
                "ok": False, "critical": True, "error": type(exc).__name__,
            }
            raise DataUnavailable(f"event log read failed: {type(exc).__name__}") from exc
        for entries in rules.values():
            entries.sort(key=lambda row: row["seq"])
        pipelines: dict[int, dict[str, Any]] = {}
        pipeline_origins: dict[int, float | None] = {}
        pipeline_games = sorted(set(pipeline_counts) | set(pipeline_milestones) |
                                set(pipeline_activities))
        for game in pipeline_games:
            milestones = sorted(pipeline_milestones.get(game, []), key=lambda row: row["seq"])
            activities = sorted(pipeline_activities.get(game, {}).values(),
                                key=lambda row: row["firstSeq"])
            epochs = [row["_epoch"] for row in milestones if row["_epoch"] is not None]
            epochs.extend(row["_firstEpoch"] for row in activities
                          if row["_firstEpoch"] is not None)
            epochs.extend(row["_lastEpoch"] for row in activities
                          if row["_lastEpoch"] is not None)
            origin = min(epochs) if epochs else None
            pipeline_origins[game] = origin
            previous = None
            for row in milestones:
                epoch = row.pop("_epoch")
                row["elapsedFromStartMs"] = (
                    None if epoch is None or origin is None else round((epoch - origin) * 1000, 1)
                )
                row["elapsedFromPreviousMs"] = (
                    None if epoch is None or previous is None else round((epoch - previous) * 1000, 1)
                )
                if epoch is not None:
                    previous = epoch
            for row in activities:
                first_epoch = row.pop("_firstEpoch")
                last_epoch = row.pop("_lastEpoch")
                row["elapsedFromStartMs"] = (
                    None if first_epoch is None or origin is None
                    else round((first_epoch - origin) * 1000, 1)
                )
                row["durationMs"] = (
                    None if first_epoch is None or last_epoch is None
                    else round(max(0.0, last_epoch - first_epoch) * 1000, 1)
                )
            counts = dict(sorted(pipeline_counts.get(game, {}).items()))
            observed_core = sum(counts.get(event_type, 0) > 0
                                for event_type in PIPELINE_CORE)
            pipelines[game] = {
                "game": game, "available": bool(milestones or activities),
                "milestones": milestones, "activities": activities,
                "eventCounts": counts,
                "eventCount": sum(counts.values()),
                "alerts": dict(sorted(pipeline_alerts.get(game, {}).items())),
                "completeness": round(observed_core / len(PIPELINE_CORE), 4),
                "observedCoreStages": observed_core,
                "coreStageDenominator": len(PIPELINE_CORE),
                "observedSpanMs": (
                    round((max(epochs) - min(epochs)) * 1000, 1) if epochs else None
                ),
                "startTs": (
                    datetime.fromtimestamp(origin, tz=timezone.utc).isoformat()
                    if origin is not None else ""
                ),
            }
        replays: dict[int, dict[str, Any]] = {}
        for game, raw_rows in item_replay_events.items():
            origin = pipeline_origins.get(game)
            rows = []
            for raw_row in sorted(raw_rows, key=lambda row: row["seq"]):
                row = raw_row.copy()
                epoch = row.pop("_epoch")
                row["elapsedFromStartMs"] = (
                    None if epoch is None or origin is None
                    else round(max(0.0, epoch - origin) * 1000, 1)
                )
                rows.append(row)
            item_ids = sorted({int(row["item"]) for row in rows})
            replays[game] = {
                "game": game, "available": bool(rows), "events": rows,
                "eventCount": len(rows), "itemCount": len(item_ids),
                "itemsWithBelief": len({row["item"] for row in rows
                                        if row["type"] == "item.belief"}),
                "itemsWithDecision": len({row["item"] for row in rows
                                          if row["type"] == "item.decided"}),
                "beliefEvents": sum(row["type"] == "item.belief" for row in rows),
                "ruleEvents": sum(row["type"] == "rule.fired" for row in rows),
                "decisionEvents": sum(row["type"] == "item.decided" for row in rows),
                "startTs": pipelines.get(game, {}).get("startTs", ""),
            }
        self._dependencies["events"] = {
            "ok": True, "critical": True, "mode": "append-only-tail", "maxSeq": max_seq,
        }
        return {
            "decisions": decisions, "beliefs": beliefs, "rules": dict(rules),
            "live": live[-160:], "schedules": schedules[-100:], "maxSeq": max_seq,
            "pipelines": pipelines,
            "replays": replays,
            "latestPipelineGame": max(
                (game for game, row in pipelines.items() if row["available"]), default=None
            ),
        }

    @staticmethod
    def _pair(value: Any) -> list[float] | None:
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return None
        pair = [_finite(value[0], float("nan")), _finite(value[1], float("nan"))]
        return [round(v, 2) for v in pair] if all(math.isfinite(v) for v in pair) else None

    def _group_transactions(self, rows: list[tuple[Any, ...]]) -> tuple[
            dict[tuple[int, int, str], ChargeGroup], dict[int, list[tuple[Any, ...]]]]:
        groups: dict[tuple[int, int, str], ChargeGroup] = {}
        per_game: dict[int, list[tuple[Any, ...]]] = defaultdict(list)
        for game, issuer, reviewer, item, accepted, amount in rows:
            game_i, item_i = int(game), int(item)
            amount_f = _finite(amount)
            row = (game_i, str(issuer), str(reviewer), item_i, bool(accepted), amount_f)
            per_game[game_i].append(row)
            key = (game_i, item_i, str(issuer))
            group = groups.setdefault(key, ChargeGroup(game_i, item_i, str(issuer)))
            group.add(str(reviewer), bool(accepted), amount_f)
        return groups, dict(per_game)

    def _build_race(self, rows: list[tuple[Any, ...]]) -> dict[str, Any]:
        games = sorted({int(row[0]) for row in rows})
        teams = sorted({str(row[1]) for row in rows}, key=lambda t: (t != US, t.casefold()))
        by_team: dict[str, dict[int, float]] = defaultdict(dict)
        for game, team, score in rows:
            by_team[str(team)][int(game)] = _finite(score)
        series = []
        for team in teams:
            running = 0.0
            cumulative: list[float] = []
            deltas: list[float] = []
            for game in games:
                delta = by_team[team].get(game, 0.0)
                deltas.append(round(delta, 2))
                running += delta
                cumulative.append(round(running, 2))
            ordered = sorted((abs(v), v) for v in deltas)
            top = sum(abs(v) for _, v in ordered[-3:])
            absolute = sum(abs(v) for v in deltas)
            positive = sorted((v for v in deltas if v > 0), reverse=True)
            negative = sorted(v for v in deltas if v < 0)
            p10 = _percentile(deltas, 0.1)
            p90 = _percentile(deltas, 0.9)
            winsorized = sum(min(max(v, p10), p90) for v in deltas) if p10 is not None and p90 is not None else running
            best_index = max(range(len(deltas)), key=deltas.__getitem__) if deltas else None
            worst_index = min(range(len(deltas)), key=deltas.__getitem__) if deltas else None
            series.append({
                "team": team, "scores": cumulative, "rounds": deltas,
                "total": round(running, 2), "meanRound": round(statistics.mean(deltas), 2) if deltas else 0,
                "medianRound": round(statistics.median(deltas), 2) if deltas else 0,
                "top3AbsoluteShare": round(top / absolute, 4) if absolute else 0,
                "positiveTop3Share": round(sum(positive[:3]) / sum(positive), 4) if positive else 0,
                "medianPaceTotal": round(statistics.median(deltas) * len(deltas), 2) if deltas else 0,
                "winsorizedTotal": round(winsorized, 2),
                "withoutTop3Positive": round(running - sum(positive[:3]), 2),
                "withoutWorst3Negative": round(running - sum(negative[:3]), 2),
                "roundVolatility": round(statistics.pstdev(deltas), 2) if len(deltas) > 1 else 0,
                "positiveRoundRate": round(sum(v > 0 for v in deltas) / len(deltas), 4) if deltas else 0,
                "bestRound": None if best_index is None else {"game": games[best_index], "score": deltas[best_index]},
                "worstRound": None if worst_index is None else {"game": games[worst_index], "score": deltas[worst_index]},
            })
        return {"gameIds": games, "series": series, "teamCount": len(teams)}

    def _build_item_index(self, document_games: set[int] | None = None) -> list[dict[str, Any]]:
        """Compact, description-free evidence index for instant global navigation."""
        document_games = document_games or set()
        decisions = self._events.get("decisions", {})
        beliefs = self._events.get("beliefs", {})
        rules = self._events.get("rules", {})
        replay_counts: dict[tuple[int, int], int] = defaultdict(int)
        for game, replay in self._events.get("replays", {}).items():
            for event in replay.get("events", []):
                if isinstance(event.get("item"), int):
                    replay_counts[(int(game), int(event["item"]))] += 1
        transaction_items = {(game, item) for game, item, _issuer in self._groups}
        keys = sorted(set(decisions) | set(beliefs) | set(rules) |
                      set(self._thresholds) | transaction_items)
        out: list[dict[str, Any]] = []
        for game, item in keys:
            decision = decisions.get((game, item))
            threshold = self._thresholds.get((game, item))
            belief = beliefs.get((game, item))
            status = "unlabelled"
            log_error = None
            foregone = 0.0
            over_ratio = None
            if decision and threshold:
                charge = decision["a"]
                if charge < threshold["tLo"]:
                    status = "under"
                    foregone = 16 * (threshold["tLo"] - charge)
                elif threshold["tHi"] is not None and charge > threshold["tHi"]:
                    status = "over"
                    over_ratio = charge / threshold["tHi"] if threshold["tHi"] > 0 else None
                elif threshold["tHi"] is None:
                    status = "above-floor-open-ceiling"
                else:
                    status = "inside-bracket"
                if charge > 0 and threshold["tLo"] > 0:
                    log_error = math.log(charge / threshold["tLo"])
            field = {"exact": 0, "lowerBound": 0, "hidden": 0, "unresolved": 0}
            for (g, it, issuer), group in self._groups.items():
                if g != game or it != item or issuer == US:
                    continue
                observed = group.observed()
                kind = observed["chargeKind"]
                if kind == "exact":
                    field["exact"] += 1
                elif kind == "lower_bound":
                    field["lowerBound"] += 1
                elif kind == "hidden":
                    field["hidden"] += 1
                else:
                    field["unresolved"] += 1
            item_rules = rules.get((game, item), [])
            out.append({
                "game": game, "item": item, "status": status,
                "a": decision.get("a") if decision else None,
                "b": decision.get("b") if decision else None,
                "covered": decision.get("covered") if decision else None,
                "tLo": threshold.get("tLo") if threshold else None,
                "tHi": threshold.get("tHi") if threshold else None,
                "nFair": threshold.get("nFair") if threshold else None,
                "nFraud": threshold.get("nFraud") if threshold else None,
                "bracketKind": ("two-sided" if threshold and threshold["tHi"] is not None
                                else "floor-only" if threshold else "unlabelled"),
                "median": belief.get("median") if belief else None,
                "source": belief.get("source") if belief else None,
                "sigma": belief.get("sigma") if belief else None,
                "logError": None if log_error is None else round(log_error, 4),
                "foregoneLowerBound": round(foregone, 2),
                "overRatio": None if over_ratio is None else round(over_ratio, 4),
                "ruleCount": len(item_rules),
                "shadowCount": sum(bool(row.get("shadow")) for row in item_rules),
                "replayCount": replay_counts.get((game, item), 0),
                "documentsAvailable": game in document_games,
                "field": field,
            })
        return out

    @staticmethod
    def _rank_dynamics(race: dict[str, Any]) -> dict[str, Any]:
        games = race["gameIds"]
        series = race["series"]
        ranks: dict[str, list[int]] = {row["team"]: [] for row in series}
        for index in range(len(games)):
            ordered = sorted(series, key=lambda row: (-row["scores"][index], row["team"].casefold()))
            for rank, row in enumerate(ordered, start=1):
                ranks[row["team"]].append(rank)
        rows = []
        for team in sorted(ranks, key=lambda name: ranks[name][-1] if ranks[name] else 10**6):
            team_series = next(row for row in series if row["team"] == team)
            history = ranks[team]
            lookback = max(0, len(history) - 6)
            momentum = sum(team_series["rounds"][-5:])
            rows.append({
                "team": team, "ranks": history,
                "currentRank": history[-1] if history else None,
                "bestRank": min(history) if history else None,
                "worstRank": max(history) if history else None,
                "rankChange5": (history[lookback] - history[-1]) if history else 0,
                "momentum5": round(momentum, 2),
                "currentScore": team_series["scores"][-1] if team_series["scores"] else 0,
            })
        return {"gameIds": games, "teams": rows}

    def _quality_rows(self, summaries: dict[int, dict[str, Any]],
                      item_index: list[dict[str, Any]],
                      document_games: set[int]) -> list[dict[str, Any]]:
        items_by_game: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in item_index:
            items_by_game[row["game"]].append(row)
        out = []
        for game in sorted(self._rows_by_game):
            items = items_by_game.get(game, [])
            groups = [group for (g, _, issuer), group in self._groups.items()
                      if g == game and issuer != US]
            expected_groups = len({row["item"] for row in items}) * 16
            hidden = sum(group.observed()["chargeKind"] == "hidden" for group in groups)
            summary = summaries.get(game, {})
            reconciliation = summary.get("scoreReconciliationDelta")
            decision_count = sum(row["a"] is not None for row in items)
            belief_count = sum(row["median"] is not None for row in items)
            rule_trace_count = sum(row["ruleCount"] > 0 for row in items)
            replay_count = sum(row["replayCount"] > 0 for row in items)
            threshold_count = sum(row["tLo"] is not None for row in items)
            out.append({
                "game": game, "transactionRows": len(self._rows_by_game.get(game, [])),
                "items": len(items), "decisions": decision_count,
                "beliefs": belief_count, "ruleTraces": rule_trace_count,
                "replayedItems": replay_count,
                "thresholds": threshold_count,
                "twoSided": sum(row["bracketKind"] == "two-sided" for row in items),
                "openCeilings": sum(row["bracketKind"] == "floor-only" for row in items),
                "hiddenCharges": hidden,
                "fieldCoverage": round(len(groups) / expected_groups, 4) if expected_groups else 0,
                "decisionCoverage": round(decision_count / len(items), 4) if items else 0,
                "beliefCoverage": round(belief_count / len(items), 4) if items else 0,
                "ruleTraceCoverage": round(rule_trace_count / len(items), 4) if items else 0,
                "replayCoverage": round(replay_count / len(items), 4) if items else 0,
                "thresholdCoverage": round(threshold_count / len(items), 4) if items else 0,
                "documentsAvailable": game in document_games,
                "scoreReconciliationDelta": reconciliation,
                "reconciled": (reconciliation is not None and abs(reconciliation) <= 0.011),
            })
        return out

    @staticmethod
    def _phase_rows(economics: list[dict[str, Any]], size: int = 10) -> list[dict[str, Any]]:
        phases = []
        for offset in range(0, len(economics), size):
            rows = economics[offset: offset + size]
            if not rows:
                continue
            nets = [row["net"] for row in rows]
            phases.append({
                "label": f"G{rows[0]['game']}–{rows[-1]['game']}",
                "startGame": rows[0]["game"], "endGame": rows[-1]["game"],
                "games": len(rows), "net": round(sum(nets), 2),
                "income": round(sum(row["income"] for row in rows), 2),
                "cost": round(sum(row["cost"] for row in rows), 2),
                "meanNet": round(statistics.mean(nets), 2),
                "medianNet": round(statistics.median(nets), 2),
                "positiveRate": round(sum(value > 0 for value in nets) / len(nets), 4),
                "volatility": round(statistics.pstdev(nets), 2) if len(nets) > 1 else 0,
            })
        return phases

    @staticmethod
    def _source_rows(item_index: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in item_index:
            groups[row.get("source") or "no logged belief"].append(row)
        out = []
        for source, rows in groups.items():
            errors = [abs(row["logError"]) for row in rows if row["logError"] is not None]
            labelled = [row for row in rows if row["tLo"] is not None]
            out.append({
                "source": source, "items": len(rows), "labelled": len(labelled),
                "under": sum(row["status"] == "under" for row in rows),
                "over": sum(row["status"] == "over" for row in rows),
                "inside": sum(row["status"] in {"inside-bracket", "above-floor-open-ceiling"}
                              for row in rows),
                "medianAbsoluteLogError": _median(errors),
                "foregoneLowerBound": round(sum(row["foregoneLowerBound"] for row in rows), 2),
            })
        return sorted(out, key=lambda row: (-row["items"], row["source"]))

    @staticmethod
    def _risk_rows(item_index: list[dict[str, Any]]) -> dict[str, Any]:
        """Aggregate evidence by belief source and value regime without point labels."""
        bucket_specs = [
            ("0–50", 0.0, 50.0),
            ("50–400", 50.0, 400.0),
            ("400–1200", 400.0, 1200.0),
            ("1200+", 1200.0, None),
        ]
        groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        labelled = [row for row in item_index
                    if row.get("tLo") is not None and float(row["tLo"]) >= 0]
        for row in labelled:
            floor = float(row["tLo"])
            bucket = next((name for name, lo, hi in bucket_specs
                           if floor >= lo and (hi is None or floor < hi)), None)
            if bucket is not None:
                groups[(row.get("source") or "no logged belief", bucket)].append(row)

        cells = []
        for (source, bucket), rows in groups.items():
            with_decision = [row for row in rows if row.get("a") is not None]
            wrong = [row for row in with_decision if row["status"] in {"under", "over"}]
            errors = [abs(float(row["logError"])) for row in with_decision
                      if row.get("logError") is not None]
            limit_deltas = [float(row["b"]) - float(row["tLo"])
                            for row in rows if row.get("b") is not None]
            cells.append({
                "source": source,
                "bucket": bucket,
                "items": len(rows),
                "decisions": len(with_decision),
                "under": sum(row["status"] == "under" for row in with_decision),
                "over": sum(row["status"] == "over" for row in with_decision),
                "notProvenWrong": sum(
                    row["status"] in {"inside-bracket", "above-floor-open-ceiling"}
                    for row in with_decision
                ),
                "wrongRate": round(len(wrong) / len(with_decision), 4) if with_decision else None,
                "medianAbsoluteLogError": _median(errors),
                "foregoneLowerBound": round(
                    sum(float(row.get("foregoneLowerBound") or 0) for row in rows), 2
                ),
                "limits": len(limit_deltas),
                "medianLimitMinusFloor": _median(limit_deltas),
                "limitBelowFloorRate": round(
                    sum(delta < 0 for delta in limit_deltas) / len(limit_deltas), 4
                ) if limit_deltas else None,
            })
        bucket_order = {name: index for index, (name, _, _) in enumerate(bucket_specs)}
        cells.sort(key=lambda row: (row["source"].casefold(), bucket_order[row["bucket"]]))
        return {
            "buckets": [name for name, _, _ in bucket_specs],
            "sources": sorted({row["source"] for row in cells}, key=str.casefold),
            "cells": cells,
            "labelledItems": len(labelled),
            "decidedItems": sum(row.get("a") is not None for row in labelled),
            "denominator": "items with a sanctioned proven floor, grouped by logged belief source",
        }

    def _rule_intelligence(self, item_index: list[dict[str, Any]]) -> dict[str, Any]:
        """Materialise logged rule firings without pricing unprovable counterfactuals."""
        item_lookup = {(row["game"], row["item"]): row for row in item_index}
        bucket_specs = [("0–50", 0.0, 50.0), ("50–400", 50.0, 400.0),
                        ("400–1200", 400.0, 1200.0), ("1200+", 1200.0, None)]
        grouped: dict[tuple[str, bool], list[dict[str, Any]]] = defaultdict(list)
        records: list[dict[str, Any]] = []
        for (game, item), firings in self._events.get("rules", {}).items():
            threshold = self._thresholds.get((game, item))
            indexed = item_lookup.get((game, item), {})
            for firing in firings:
                rule = str(firing["rule"])
                shadow = bool(firing["shadow"])
                before = firing.get("from")
                after = firing.get("to")
                record: dict[str, Any] = {
                    "id": f"{rule}|{'shadow' if shadow else 'active'}",
                    "rule": rule, "shadow": shadow, "game": game, "item": item,
                    "seq": firing.get("seq"), "paired": before is not None and after is not None,
                    "before": before, "after": after,
                }
                if record["paired"]:
                    before_state, before_income = _proven_charge(float(before[0]), threshold)
                    after_state, after_income = _proven_charge(float(after[0]), threshold)
                    floor = threshold.get("tLo") if threshold else None
                    bucket = next((name for name, lo, hi in bucket_specs
                                   if floor is not None and float(floor) >= lo and
                                   (hi is None or float(floor) < hi)), None)
                    record.update({
                        "aDelta": round(float(after[0]) - float(before[0]), 2),
                        "bDelta": round(float(after[1]) - float(before[1]), 2),
                        "beforeState": before_state, "afterState": after_state,
                        "beforeProvenIncome": None if before_income is None else round(before_income, 2),
                        "afterProvenIncome": None if after_income is None else round(after_income, 2),
                        "tLo": floor,
                        "tHi": threshold.get("tHi") if threshold else None,
                        "bestPossible": None if floor is None else round(16 * float(floor), 2),
                        "bucket": bucket,
                        "source": indexed.get("source"),
                        "hiddenCharges": int(indexed.get("field", {}).get("hidden", 0)),
                    })
                    records.append(record)
                grouped[(rule, shadow)].append(record)

        def metric(rows: list[dict[str, Any]], side: str) -> dict[str, Any]:
            labelled = [row for row in rows if row.get("bestPossible") is not None]
            state_key = f"{side}State"
            income_key = f"{side}ProvenIncome"
            best = sum(float(row["bestPossible"]) for row in labelled)
            income = sum(float(row[income_key]) for row in labelled
                         if row.get(income_key) is not None)
            foregone = 0.0
            for row in labelled:
                charge = float(row[side][0])
                if charge < float(row["tLo"]):
                    foregone += 16 * (float(row["tLo"]) - charge)
            return {
                "items": len(labelled), "bestPossible": round(best, 2),
                "provenIncome": round(income, 2),
                "score": round(income / best, 6) if best else None,
                "excluded": sum(row.get(income_key) is None for row in labelled),
                "atOrUnderFloor": sum(row.get(state_key) == "at-or-under-floor" for row in labelled),
                "aboveCeiling": sum(row.get(state_key) == "above-ceiling" for row in labelled),
                "unprovable": sum(row.get(state_key) == "unprovable" for row in labelled),
                "foregoneLowerBound": round(foregone, 2),
            }

        summaries = []
        for (rule, shadow), rows in grouped.items():
            paired = [row for row in rows if row["paired"]]
            before_metric = metric(paired, "before")
            after_metric = metric(paired, "after")
            transitions: dict[tuple[str, str], int] = defaultdict(int)
            for row in paired:
                if row.get("tLo") is not None:
                    transitions[(row["beforeState"], row["afterState"])] += 1
            bucket_moves = []
            for bucket, _, _ in bucket_specs:
                bucket_rows = [row for row in paired if row.get("bucket") == bucket]
                if not bucket_rows:
                    continue
                deltas = [float(row["bDelta"]) for row in bucket_rows]
                bucket_moves.append({
                    "bucket": bucket, "items": len(bucket_rows),
                    "raise": sum(delta > 0 for delta in deltas),
                    "lower": sum(delta < 0 for delta in deltas),
                    "same": sum(delta == 0 for delta in deltas),
                    "medianDelta": _median(deltas),
                    "hiddenChargesOnRaises": sum(
                        row["hiddenCharges"] for row in bucket_rows if row["bDelta"] > 0
                    ),
                })
            timeline = []
            for game in sorted({row["game"] for row in rows}):
                game_rows = [row for row in rows if row["game"] == game]
                game_paired = [row for row in game_rows if row["paired"]]
                before_game = metric(game_paired, "before")
                after_game = metric(game_paired, "after")
                timeline.append({
                    "game": game, "firings": len(game_rows), "paired": len(game_paired),
                    "labelled": after_game["items"],
                    "beforeScore": before_game["score"], "afterScore": after_game["score"],
                    "provenIncomeDelta": round(
                        after_game["provenIncome"] - before_game["provenIncome"], 2
                    ),
                    "afterExcluded": after_game["excluded"],
                    "bRaises": sum(row.get("bDelta", 0) > 0 for row in game_paired),
                    "bLowers": sum(row.get("bDelta", 0) < 0 for row in game_paired),
                })
            summaries.append({
                "id": f"{rule}|{'shadow' if shadow else 'active'}",
                "rule": rule, "shadow": shadow, "firings": len(rows),
                "games": len({row["game"] for row in rows}), "paired": len(paired),
                "chargeRaises": sum(row.get("aDelta", 0) > 0 for row in paired),
                "chargeLowers": sum(row.get("aDelta", 0) < 0 for row in paired),
                "limitRaises": sum(row.get("bDelta", 0) > 0 for row in paired),
                "limitLowers": sum(row.get("bDelta", 0) < 0 for row in paired),
                "hiddenChargesOnLimitRaises": sum(
                    row.get("hiddenCharges", 0) for row in paired if row.get("bDelta", 0) > 0
                ),
                "medianChargeDelta": _median([row["aDelta"] for row in paired]),
                "medianLimitDelta": _median([row["bDelta"] for row in paired]),
                "before": before_metric, "after": after_metric,
                "provenIncomeDelta": round(
                    after_metric["provenIncome"] - before_metric["provenIncome"], 2
                ),
                "transitions": [{"from": before, "to": after, "items": count}
                                for (before, after), count in sorted(transitions.items())],
                "bucketLimitMoves": bucket_moves, "timeline": timeline,
            })
        summaries.sort(key=lambda row: (not row["shadow"], -row["paired"], -row["firings"], row["rule"]))
        records.sort(key=lambda row: (row["id"], row["game"], row["item"], row.get("seq") or 0))
        portfolio_rules = []
        latest_records = []
        for rule_id in sorted({row["id"] for row in records}):
            rule_rows = [row for row in records if row["id"] == rule_id]
            by_item: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
            for row in rule_rows:
                by_item[(row["game"], row["item"])].append(row)
            selected = []
            unstable = 0
            for item_rows in by_item.values():
                ordered_rows = sorted(item_rows, key=lambda row: row.get("seq") or 0)
                stable = len({tuple(row["after"]) for row in ordered_rows}) == 1
                ordered_rows[-1]["repeatFirings"] = len(ordered_rows)
                ordered_rows[-1]["candidateStable"] = stable
                selected.append(ordered_rows[-1])
                unstable += int(not stable)
            selected.sort(key=lambda row: (row["game"], row["item"]))
            latest_records.extend(selected)
            before_metric = metric(selected, "before")
            after_metric = metric(selected, "after")
            portfolio_rules.append({
                "id": rule_id, "rule": selected[0]["rule"],
                "shadow": selected[0]["shadow"],
                "pairedFirings": len(rule_rows), "uniqueItems": len(selected),
                "duplicateFirings": len(rule_rows) - len(selected),
                "unstableItems": unstable,
                "before": before_metric, "after": after_metric,
                "provenIncomeDelta": round(
                    after_metric["provenIncome"] - before_metric["provenIncome"], 2
                ),
            })

        item_candidates: dict[tuple[int, int], dict[str, dict[str, Any]]] = defaultdict(dict)
        for row in latest_records:
            item_candidates[(row["game"], row["item"])][row["id"]] = row
        overlaps = []
        rule_ids = sorted(row["id"] for row in portfolio_rules)
        for left_index, left_id in enumerate(rule_ids):
            for right_id in rule_ids[left_index + 1:]:
                pairs = [(candidates[left_id], candidates[right_id])
                         for candidates in item_candidates.values()
                         if left_id in candidates and right_id in candidates]
                if not pairs:
                    continue
                comparable = [(left, right) for left, right in pairs
                              if left["aDelta"] != 0 and right["aDelta"] != 0]
                agreement = sum(
                    math.copysign(1, left["aDelta"]) == math.copysign(1, right["aDelta"])
                    for left, right in comparable
                )
                log_spreads = [
                    abs(math.log(float(left["after"][0]) / float(right["after"][0])))
                    for left, right in pairs
                    if float(left["after"][0]) > 0 and float(right["after"][0]) > 0
                ]
                overlaps.append({
                    "left": left_id, "right": right_id, "items": len(pairs),
                    "directionComparable": len(comparable),
                    "directionAgreement": agreement,
                    "directionOpposition": len(comparable) - agreement,
                    "directionAgreementRate": (
                        round(agreement / len(comparable), 4) if comparable else None
                    ),
                    "bothRaiseB": sum(left["bDelta"] > 0 and right["bDelta"] > 0
                                      for left, right in pairs),
                    "medianAbsoluteLogCandidateRatio": _median(log_spreads),
                })
        portfolio_rules.sort(key=lambda row: (-row["provenIncomeDelta"], -row["uniqueItems"], row["id"]))
        latest_records.sort(key=lambda row: (row["id"], row["game"], row["item"]))
        return {
            "rules": summaries, "records": records,
            "firings": sum(len(rows) for rows in grouped.values()),
            "pairedFirings": len(records),
            "ruleVariants": len(summaries),
            "denominator": ("one logged rule firing; proven-income scores use 16 × t_lo "
                            "as a fixed denominator for labelled paired firings"),
            "portfolios": {
                "rules": portfolio_rules, "records": latest_records, "overlaps": overlaps,
                "uniqueItems": len(item_candidates),
                "multiRuleItems": sum(len(candidates) > 1
                                      for candidates in item_candidates.values()),
                "dedupePolicy": ("latest logged paired firing by sequence for each "
                                 "rule × game × item"),
                "denominator": ("one deduplicated game/item candidate for the selected "
                                "primary rule; t_lo buckets are diagnostic hindsight only"),
            },
        }

    @staticmethod
    def _anomaly_rows(race: dict[str, Any], trends: dict[str, Any],
                      item_index: list[dict[str, Any]]) -> list[dict[str, Any]]:
        anomalies: list[dict[str, Any]] = []
        under = sorted((row for row in item_index if row["status"] == "under"),
                       key=lambda row: row["foregoneLowerBound"], reverse=True)
        for row in under[:8]:
            anomalies.append({
                "type": "undercharge", "game": row["game"], "item": row["item"],
                "magnitude": row["foregoneLowerBound"], "unit": "EUR lower bound",
                "severity": "critical" if row["foregoneLowerBound"] >= 25_000 else "high",
            })
        over = sorted((row for row in item_index if row["status"] == "over"),
                      key=lambda row: row["overRatio"] or 0, reverse=True)
        for row in over[:5]:
            anomalies.append({
                "type": "overcharge", "game": row["game"], "item": row["item"],
                "magnitude": row["overRatio"], "unit": "× proven ceiling",
                "severity": "high" if (row["overRatio"] or 0) >= 5 else "medium",
            })
        for row in sorted(trends["decisionStream"],
                          key=lambda item: item["rejectFair"]["euros"], reverse=True)[:4]:
            anomalies.append({
                "type": "fair-rejection-cost", "game": row["game"], "item": None,
                "magnitude": row["rejectFair"]["euros"], "unit": "EUR reviewer cost",
                "severity": "critical" if row["rejectFair"]["euros"] >= 10_000 else "high",
            })
        oasis = next((row for row in race["series"] if row["team"] == US), None)
        if oasis:
            shocks = sorted(zip(race["gameIds"], oasis["rounds"]),
                            key=lambda pair: abs(pair[1]), reverse=True)
            for game, value in shocks[:4]:
                anomalies.append({
                    "type": "round-shock", "game": game, "item": None,
                    "magnitude": value, "unit": "EUR net",
                    "severity": "high" if abs(value) >= 10_000 else "medium",
                })
        order = {"critical": 0, "high": 1, "medium": 2}
        return sorted(anomalies, key=lambda row: (order.get(row["severity"], 9),
                                                  -abs(row["magnitude"])))

    def _build_intelligence(self, race: dict[str, Any], trends: dict[str, Any],
                            summaries: dict[int, dict[str, Any]],
                            item_index: list[dict[str, Any]],
                            document_games: set[int]) -> dict[str, Any]:
        dynamics = self._rank_dynamics(race)
        oasis = next((row for row in dynamics["teams"] if row["team"] == US), {})
        leader = dynamics["teams"][0] if dynamics["teams"] else {}
        economics = trends["economics"]
        recent = economics[-5:]
        previous = economics[-10:-5]
        recent_net = sum(row["net"] for row in recent)
        previous_net = sum(row["net"] for row in previous)
        reject_fair = sum(row["rejectFair"]["euros"] for row in trends["decisionStream"])
        accept_fraud = sum(row["acceptFraud"]["euros"] for row in trends["decisionStream"])
        quality = self._quality_rows(summaries, item_index, document_games)
        return {
            "briefing": {
                "currentRank": oasis.get("currentRank"),
                "rankChange5": oasis.get("rankChange5", 0),
                "score": oasis.get("currentScore", 0),
                "leader": leader.get("team"), "leaderScore": leader.get("currentScore", 0),
                "gapToLeader": round(leader.get("currentScore", 0) - oasis.get("currentScore", 0), 2),
                "momentum5": round(recent_net, 2),
                "momentumDelta": round(recent_net - previous_net, 2),
                "provenForegone": trends["concentration"]["totalLowerBound"],
                "provenForegoneItems": trends["concentration"]["itemCount"],
                "fairRejectionCost": round(reject_fair, 2),
                "fraudAcceptanceCost": round(accept_fraud, 2),
                "errorCostRatio": round(reject_fair / accept_fraud, 3) if accept_fraud else None,
                "hiddenCharges": sum(row["hiddenCharges"] for row in quality),
                "playedGames": len(economics),
            },
            "rankDynamics": dynamics,
            "phases": self._phase_rows(economics),
            "quality": quality,
            "sources": self._source_rows(item_index),
            "valueRisk": self._risk_rows(item_index),
            "rules": self._rule_intelligence(item_index),
            "anomalies": self._anomaly_rows(race, trends, item_index),
        }

    def _reviewer_cost(self, group: ChargeGroup, reviewer: str) -> tuple[float, str]:
        decision = group.decisions.get(reviewer)
        if decision is None:
            return 0.0, "missing"
        accepted, amount = decision
        observed = group.observed()
        label = observed["classification"]
        if accepted:
            return amount, label
        if label == "fair" and observed["charge"] is not None:
            return 1.5 * float(observed["charge"]), label
        return 0.0, label

    def _build_reviewer_lab(self, generated_at: str) -> dict[str, Any]:
        """Materialise claim-free reviewer evidence without reconstructing hidden charges."""
        decisions = self._events.get("decisions", {})
        beliefs = self._events.get("beliefs", {})
        cells: list[dict[str, Any]] = []
        matrix = {
            "acceptFair": {"count": 0, "cost": 0.0},
            "rejectFair": {"count": 0, "cost": 0.0},
            "acceptFraud": {"count": 0, "cost": 0.0},
            "rejectFraud": {"count": 0, "cost": 0.0},
        }
        unproven = {"count": 0, "cost": 0.0}
        for (game, item, issuer), group in sorted(self._groups.items()):
            if issuer == US or US not in group.decisions:
                continue
            accepted, _paid = group.decisions[US]
            actual_cost, settlement_class = self._reviewer_cost(group, US)
            observed = group.observed()
            threshold = self._thresholds.get((game, item))
            logged = decisions.get((game, item))
            belief = beliefs.get((game, item))
            charge = observed.get("charge")
            charge_kind = str(observed.get("chargeKind") or "unknown")
            proven_class = settlement_class if settlement_class in {"fair", "fraud"} else "unproven"
            evidence_kind = {
                ("fair", "exact"): "paid-rejection-exact",
                ("fraud", "lower_bound"): "accepted-fraud-lower-bound",
                ("fraud", "hidden"): "unpaid-rejection-hidden",
            }.get((proven_class, charge_kind), "unproven")
            if settlement_class == "conflict":
                proven_class = "conflict"
                evidence_kind = "conflicting-settlement"
            elif proven_class == "unproven" and accepted and charge is not None and threshold:
                # An accepted fair charge pays its exact a. Accepted fraud pays at least
                # more than t, so an observed payout at/below a sanctioned floor proves fair.
                if float(charge) <= float(threshold["tLo"]):
                    proven_class = "fair"
                    charge_kind = "exact"
                    evidence_kind = "sanctioned-floor-exact"
                elif (threshold.get("tHi") is not None and
                      float(charge) > float(threshold["tHi"])):
                    # Accepted-fraud payout is a lower bound on the submitted charge.
                    proven_class = "fraud"
                    charge_kind = "lower_bound"
                    evidence_kind = "sanctioned-ceiling-lower-bound"
            reviewer_limit = logged.get("b") if logged else None
            limit_audit = "missing" if reviewer_limit is None else "indeterminate"
            if reviewer_limit is not None and charge is not None:
                if proven_class == "fair" and charge_kind == "exact":
                    limit_audit = ("consistent" if (float(charge) <= float(reviewer_limit)) == accepted
                                   else "inconsistent")
                elif proven_class == "fraud" and charge_kind == "lower_bound":
                    if float(reviewer_limit) < float(charge):
                        limit_audit = "consistent" if not accepted else "inconsistent"
            outcome = None
            if proven_class in {"fair", "fraud"}:
                outcome = ("accept" if accepted else "reject") + proven_class.title()
                matrix[outcome]["count"] += 1
                matrix[outcome]["cost"] += actual_cost
            else:
                unproven["count"] += 1
                unproven["cost"] += actual_cost
            cells.append({
                "game": game, "item": item, "opponent": issuer,
                "actualAccepted": accepted, "actualCost": _money(actual_cost),
                "outcome": outcome, "provenClass": proven_class,
                "evidenceKind": evidence_kind,
                "charge": None if charge is None else _money(charge),
                "chargeKind": charge_kind,
                "tLo": threshold.get("tLo") if threshold else None,
                "tHi": threshold.get("tHi") if threshold else None,
                "valueBucket": _floor_bucket(threshold.get("tLo") if threshold else None),
                "b": reviewer_limit,
                "source": belief.get("source") if belief else None,
                "limitAudit": limit_audit,
                "fairExactEligible": bool(
                    proven_class == "fair" and charge_kind == "exact" and
                    reviewer_limit is not None and limit_audit == "consistent"
                ),
                "fraudDownshiftEligible": bool(
                    proven_class == "fraud" and charge_kind == "lower_bound" and accepted and
                    reviewer_limit is not None and charge is not None and
                    float(reviewer_limit) >= float(charge)
                ),
                "hiddenFraudEligible": bool(
                    proven_class == "fraud" and charge_kind == "hidden" and not accepted and
                    reviewer_limit is not None and threshold is not None
                ),
            })
        for row in matrix.values():
            row["cost"] = _money(row["cost"])
        unproven["cost"] = _money(unproven["cost"])
        total_cost = _money(sum(float(row["actualCost"]) for row in cells))
        return {
            "schemaVersion": 1,
            "generatedAt": generated_at,
            "team": US,
            "cells": cells,
            "summary": {
                "cells": len(cells),
                "provenCells": sum(row["provenClass"] in {"fair", "fraud"} for row in cells),
                "unprovenCells": sum(row["provenClass"] not in {"fair", "fraud"} for row in cells),
                "observedReviewerCost": total_cost,
                "loggedLimits": sum(row["b"] is not None for row in cells),
                "limitConsistent": sum(row["limitAudit"] == "consistent" for row in cells),
                "limitInconsistent": sum(row["limitAudit"] == "inconsistent" for row in cells),
                "limitIndeterminate": sum(row["limitAudit"] == "indeterminate" for row in cells),
                "limitMissing": sum(row["limitAudit"] == "missing" for row in cells),
                "fairExactEligible": sum(row["fairExactEligible"] for row in cells),
                "fraudDownshiftEligible": sum(row["fraudDownshiftEligible"] for row in cells),
                "hiddenFraudEligible": sum(row["hiddenFraudEligible"] for row in cells),
                "matrix": matrix,
                "unproven": unproven,
            },
            "denominators": {
                "cell": "one Oasis review decision for one opponent charge group",
                "pricedFair": "exact proven-fair charge with a logged b that reconciles to the recorded decision",
                "pricedFraud": "accepted proven-fraud payout lower bound where candidate b falls strictly below that bound",
                "hiddenExposure": "rejected proven-fraud charge with unknown amount where raised b exceeds the sanctioned floor",
                "cost": "observed Oasis reviewer settlement in EUR; hidden rejected fraud remains zero and unpriced",
            },
            "blindSpot": (
                "Rejected fraudulent charges have unknown submitted amounts. A b raise above the proven floor "
                "can expose such groups, but neither the crossing count nor euro cost can be known. "
                "Counterfactual totals therefore cover only explicitly priced cells and are never total tournament impact."
            ),
        }

    @staticmethod
    def _empty_item_economics() -> dict[str, Any]:
        return {
            "issuerIncome": 0.0, "reviewerCost": 0.0, "netContribution": 0.0,
            "grossObservedFlow": 0.0, "reviewDecisions": 0, "hiddenFraud": 0,
            "unresolved": {"cost": 0.0, "count": 0},
            "matrix": {
                "acceptFair": {"cost": 0.0, "count": 0},
                "rejectFair": {"cost": 0.0, "count": 0},
                "acceptFraud": {"cost": 0.0, "count": 0},
                "rejectFraud": {"cost": 0.0, "count": 0},
            },
        }

    def _game_item_economics(self, game: int) -> dict[int, dict[str, Any]]:
        rows: dict[int, dict[str, Any]] = defaultdict(self._empty_item_economics)
        for row_game, issuer, _reviewer, item, _accepted, amount in self._rows_by_game.get(game, []):
            if row_game == game and issuer == US:
                rows[item]["issuerIncome"] += amount
        for (row_game, item, issuer), group in self._groups.items():
            if row_game != game or issuer == US or US not in group.decisions:
                continue
            accepted, _amount = group.decisions[US]
            cost, label = self._reviewer_cost(group, US)
            row = rows[item]
            row["reviewerCost"] += cost
            row["reviewDecisions"] += 1
            if label in {"fair", "fraud"}:
                key = ("accept" if accepted else "reject") + label.title()
                row["matrix"][key]["cost"] += cost
                row["matrix"][key]["count"] += 1
                if (label == "fraud" and not accepted and
                        group.observed()["chargeKind"] == "hidden"):
                    row["hiddenFraud"] += 1
            else:
                row["unresolved"]["cost"] += cost
                row["unresolved"]["count"] += 1
        for row in rows.values():
            row["issuerIncome"] = _money(row["issuerIncome"])
            row["reviewerCost"] = _money(row["reviewerCost"])
            row["netContribution"] = _money(row["issuerIncome"] - row["reviewerCost"])
            row["grossObservedFlow"] = _money(row["issuerIncome"] + row["reviewerCost"])
            row["unresolved"]["cost"] = _money(row["unresolved"]["cost"])
            for cell in row["matrix"].values():
                cell["cost"] = _money(cell["cost"])
        return dict(rows)

    def _game_economics(self, game: int) -> dict[str, Any]:
        rows = self._rows_by_game.get(game, [])
        income = sum(amount for _, issuer, _, _, _, amount in rows if issuer == US)
        groups = [group for (g, _, _), group in self._groups.items() if g == game]
        cells = {
            "acceptFair": {"cost": 0.0, "count": 0},
            "rejectFair": {"cost": 0.0, "count": 0},
            "acceptFraud": {"cost": 0.0, "count": 0},
            "rejectFraud": {"cost": 0.0, "count": 0},
        }
        unresolved = {"cost": 0.0, "count": 0}
        conflicts = 0
        hidden_fraud = 0
        for group in groups:
            if group.issuer == US or US not in group.decisions:
                continue
            accepted, _ = group.decisions[US]
            cost, label = self._reviewer_cost(group, US)
            if label == "fair":
                key = "acceptFair" if accepted else "rejectFair"
                cells[key]["cost"] += cost
                cells[key]["count"] += 1
            elif label == "fraud":
                key = "acceptFraud" if accepted else "rejectFraud"
                cells[key]["cost"] += cost
                cells[key]["count"] += 1
                if not accepted and group.observed()["chargeKind"] == "hidden":
                    hidden_fraud += 1
            else:
                unresolved["cost"] += cost
                unresolved["count"] += 1
                conflicts += int(label == "conflict")
        raw_cost = sum(float(cell["cost"]) for cell in cells.values()) + float(unresolved["cost"])
        for cell in cells.values():
            cell["cost"] = _money(cell["cost"])
        unresolved["cost"] = _money(unresolved["cost"])
        return {
            "income": _money(income), "cost": _money(raw_cost),
            "net": _money(income - raw_cost),
            "matrix": cells, "unresolved": unresolved, "hiddenFraud": hidden_fraud,
            "conflicts": conflicts,
        }

    def _build_trends(self, score_rows: list[tuple[Any, ...]]) -> tuple[
            dict[int, dict[str, Any]], dict[str, Any]]:
        games = sorted(self._rows_by_game)
        score_lookup = {(int(g), str(team)): _finite(score) for g, team, score in score_rows}
        summaries: dict[int, dict[str, Any]] = {}
        economics = []
        stream = []
        errors = []
        buckets = {
            "0–50": {"min": 0, "max": 50},
            "50–400": {"min": 50, "max": 400},
            "400–1200": {"min": 400, "max": 1200},
            "1200+": {"min": 1200, "max": None},
        }
        bucket_rows: dict[str, list[dict[str, Any]]] = {name: [] for name in buckets}
        decisions = self._events.get("decisions", {})
        for game in games:
            econ = self._game_economics(game)
            official = score_lookup.get((game, US))
            delta = None if official is None else round(econ["net"] - official, 6)
            summaries[game] = {
                "played": True, "net": econ["net"], "income": econ["income"],
                "cost": econ["cost"], "officialScore": None if official is None else round(official, 2),
                "scoreReconciliationDelta": delta,
            }
            economics.append({"game": game, **{k: econ[k] for k in ("income", "cost", "net")}})
            proven_cost = sum(cell["cost"] for cell in econ["matrix"].values())
            stream.append({
                "game": game,
                **{key: {"euros": value["cost"], "count": value["count"],
                         "share": round(value["cost"] / proven_cost, 5) if proven_cost else 0}
                   for key, value in econ["matrix"].items()},
                "denominatorEuros": round(proven_cost, 2),
                "unresolved": econ["unresolved"], "hiddenFraud": econ["hiddenFraud"],
            })
            vals = []
            for (g, item), decision in decisions.items():
                if g != game:
                    continue
                threshold = self._thresholds.get((g, item))
                if not threshold or threshold["tLo"] <= 0 or decision["a"] <= 0:
                    continue
                ratio = math.log(decision["a"] / threshold["tLo"])
                vals.append(round(ratio, 4))
                lo = threshold["tLo"]
                for name, limits in buckets.items():
                    if lo >= limits["min"] and (limits["max"] is None or lo < limits["max"]):
                        status = ("under" if decision["a"] < lo else
                                  "over" if threshold["tHi"] is not None and decision["a"] > threshold["tHi"]
                                  else "not-proven-wrong")
                        bucket_rows[name].append({"game": g, "error": ratio, "status": status})
                        break
            errors.append({"game": game, "values": vals,
                           "median": _median(vals), "count": len(vals)})
        nets = [row["net"] for row in economics]
        for row, rolling in zip(economics, _rolling_median(nets)):
            row["rollingMedian5"] = rolling
        bucket_trends = []
        for name, values in bucket_rows.items():
            per_game: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for row in values:
                per_game[row["game"]].append(row)
            bucket_trends.append({
                "bucket": name,
                "games": [{
                    "game": game, "count": len(rows),
                    "medianLogError": _median([r["error"] for r in rows]),
                    "underRate": round(sum(r["status"] == "under" for r in rows) / len(rows), 4),
                    "overRate": round(sum(r["status"] == "over" for r in rows) / len(rows), 4),
                } for game, rows in sorted(per_game.items())],
            })
        return summaries, {
            "economics": economics, "decisionStream": stream,
            "estimationErrors": errors, "valueBuckets": bucket_trends,
            "overchargeCurve": self._overcharge_curve(),
            "concentration": self._concentration(),
            "opponents": self._opponents(),
        }

    def _overcharge_curve(self) -> list[dict[str, Any]]:
        specs = [(1, 1.5, "1–1.5×", 0.158), (1.5, 2.5, "1.5–2.5×", 0.194),
                 (2.5, 5, "2.5–5×", 0.093), (5, 10, "5–10×", None),
                 (10, None, "10×+", 0.034)]
        buckets = [{"lo": lo, "hi": hi, "label": label, "reference": reference,
                    "accepted": 0, "decisions": 0, "items": 0}
                   for lo, hi, label, reference in specs]
        for (game, item), decision in self._events.get("decisions", {}).items():
            threshold = self._thresholds.get((game, item))
            if not threshold or not threshold["tHi"] or decision["a"] <= threshold["tHi"]:
                continue
            ratio = decision["a"] / threshold["tHi"]
            group = self._groups.get((game, item, US))
            if group is None:
                continue
            for bucket in buckets:
                if ratio >= bucket["lo"] and (bucket["hi"] is None or ratio < bucket["hi"]):
                    bucket["items"] += 1
                    bucket["accepted"] += sum(accepted for accepted, _ in group.decisions.values())
                    bucket["decisions"] += len(group.decisions)
                    break
        return [{
            "label": b["label"], "items": b["items"], "decisions": b["decisions"],
            "acceptRate": round(b["accepted"] / b["decisions"], 4) if b["decisions"] else None,
            "referenceRate": b["reference"],
        } for b in buckets]

    def _concentration(self) -> dict[str, Any]:
        entries = []
        for (game, item), decision in self._events.get("decisions", {}).items():
            threshold = self._thresholds.get((game, item))
            if not threshold or threshold["tLo"] <= 0 or decision["a"] >= threshold["tLo"]:
                continue
            loss = 16 * (threshold["tLo"] - decision["a"])
            entries.append({"game": game, "item": item, "foregoneLowerBound": round(loss, 2),
                            "charge": decision["a"], "tLo": threshold["tLo"]})
        entries.sort(key=lambda row: row["foregoneLowerBound"], reverse=True)
        total = sum(row["foregoneLowerBound"] for row in entries)
        running = 0.0
        for rank, row in enumerate(entries, start=1):
            running += row["foregoneLowerBound"]
            row["rank"] = rank
            row["cumulativeShare"] = round(running / total, 5) if total else 0
        return {"totalLowerBound": round(total, 2), "itemCount": len(entries),
                "items": entries[:100],
                "denominator": "16 × (proven floor − Oasis charge), only where charge < floor"}

    def _opponents(self) -> list[dict[str, Any]]:
        teams = sorted({group.issuer for group in self._groups.values()} | {
            reviewer for group in self._groups.values() for reviewer in group.decisions
        })
        out = []
        for team in teams:
            if team == US:
                continue
            accepts = total_reviews = 0
            income_from = cost_to = 0.0
            ratios: list[float] = []
            charge_groups = 0
            review_cells = {
                "acceptFair": {"count": 0, "euros": 0.0},
                "rejectFair": {"count": 0, "euros": 0.0},
                "acceptFraud": {"count": 0, "euros": 0.0},
                "rejectFraud": {"count": 0, "euros": 0.0},
                "unresolved": {"count": 0, "euros": 0.0},
            }
            issued = {
                "under": 0, "over": 0, "inside": 0, "open": 0,
                "unobservable": 0, "labelled": 0,
            }
            exchange_by_game: dict[int, dict[str, float]] = defaultdict(
                lambda: {"income": 0.0, "cost": 0.0}
            )
            for (game, item, issuer), group in self._groups.items():
                if issuer == US and team in group.decisions:
                    accepted, amount = group.decisions[team]
                    accepts += int(accepted)
                    total_reviews += 1
                    income_from += amount
                    exchange_by_game[game]["income"] += amount
                    cost, classification = self._reviewer_cost(group, team)
                    key = "unresolved"
                    if classification == "fair":
                        key = "acceptFair" if accepted else "rejectFair"
                    elif classification == "fraud":
                        key = "acceptFraud" if accepted else "rejectFraud"
                    review_cells[key]["count"] += 1
                    review_cells[key]["euros"] += cost
                if issuer == team:
                    charge_groups += 1
                    if US in group.decisions:
                        reviewer_cost = self._reviewer_cost(group, US)[0]
                        cost_to += reviewer_cost
                        exchange_by_game[game]["cost"] += reviewer_cost
                    threshold = self._thresholds.get((game, item))
                    observed = group.observed()
                    if threshold and threshold["tLo"] > 0 and observed["charge"] is not None:
                        ratios.append(float(observed["charge"]) / threshold["tLo"])
                    if threshold:
                        issued["labelled"] += 1
                        charge = observed.get("charge")
                        kind = observed.get("chargeKind")
                        if charge is None:
                            issued["unobservable"] += 1
                        elif threshold["tHi"] is not None and charge > threshold["tHi"]:
                            # A lower-bound payout above t_hi still proves the original
                            # submitted charge was fraudulent.
                            issued["over"] += 1
                        elif kind == "exact" and charge < threshold["tLo"]:
                            issued["under"] += 1
                        elif kind == "exact" and threshold["tHi"] is None:
                            issued["open"] += 1
                        elif kind == "exact":
                            issued["inside"] += 1
                        else:
                            issued["unobservable"] += 1
            fair_reviews = review_cells["acceptFair"]["count"] + review_cells["rejectFair"]["count"]
            fraud_reviews = review_cells["acceptFraud"]["count"] + review_cells["rejectFraud"]["count"]
            for cell in review_cells.values():
                cell["euros"] = round(cell["euros"], 2)
            timeline = []
            cumulative = 0.0
            for game in sorted(exchange_by_game):
                income = exchange_by_game[game]["income"]
                cost = exchange_by_game[game]["cost"]
                net = income - cost
                cumulative += net
                timeline.append({
                    "game": game, "incomeFromTeam": round(income, 2),
                    "costToTeam": round(cost, 2), "netExchange": round(net, 2),
                    "cumulativeNet": round(cumulative, 2),
                })
            worst = min(timeline, key=lambda row: row["netExchange"], default=None)
            best = max(timeline, key=lambda row: row["netExchange"], default=None)
            out.append({
                "team": team,
                "acceptRateAgainstUs": round(accepts / total_reviews, 4) if total_reviews else None,
                "reviewDecisions": total_reviews,
                "incomeFromTeam": round(income_from, 2), "costToTeam": round(cost_to, 2),
                "netExchange": round(income_from - cost_to, 2),
                "medianObservedChargeToFloor": _median(ratios),
                "aggressionCoverage": round(len(ratios) / charge_groups, 4) if charge_groups else 0,
                "chargeGroups": charge_groups,
                "fairRejectRateAgainstUs": round(
                    review_cells["rejectFair"]["count"] / fair_reviews, 4
                ) if fair_reviews else None,
                "fraudAcceptRateAgainstUs": round(
                    review_cells["acceptFraud"]["count"] / fraud_reviews, 4
                ) if fraud_reviews else None,
                "reviewCells": review_cells,
                "issuedEvidence": issued,
                "timeline": timeline,
                "worstExchangeGame": worst,
                "bestExchangeGame": best,
            })
        return out

    def _build_market(self, generated_at: str, race: dict[str, Any]) -> dict[str, Any]:
        """Build a description-free issuer→reviewer market ledger from observed settlements."""
        teams = sorted({group.issuer for group in self._groups.values()} | {
            reviewer for group in self._groups.values() for reviewer in group.decisions
        }, key=lambda team: (team != US, team.casefold()))
        games = list(race.get("gameIds", []))
        outcome_names = ("acceptFair", "rejectFair", "acceptFraud", "rejectFraud")

        def edge_row(issuer: str, reviewer: str) -> dict[str, Any]:
            row: dict[str, Any] = {
                "issuer": issuer, "reviewer": reviewer,
                "decisions": 0, "accepted": 0,
                "issuerIncome": 0.0, "reviewerCost": 0.0,
                "penaltyWedge": 0.0, "wrongCost": 0.0,
                "unresolvedCount": 0, "unresolvedCost": 0.0,
                "hiddenFraud": 0,
            }
            for outcome in outcome_names:
                row[f"{outcome}Count"] = 0
                row[f"{outcome}Cost"] = 0.0
            return row

        def record_edge_decision(
            row: dict[str, Any], accepted: bool, issuer_income: float,
            reviewer_cost: float, classification: str | None,
            observed: dict[str, Any],
        ) -> str | None:
            """Apply one observed decision to an edge without reconstructing hidden EUR."""
            row["decisions"] += 1
            row["accepted"] += int(accepted)
            row["issuerIncome"] += issuer_income
            row["reviewerCost"] += reviewer_cost
            row["penaltyWedge"] += reviewer_cost - issuer_income
            outcome = None
            if classification in {"fair", "fraud"}:
                outcome = ("accept" if accepted else "reject") + classification.title()
                row[f"{outcome}Count"] += 1
                row[f"{outcome}Cost"] += reviewer_cost
                if outcome in {"rejectFair", "acceptFraud"}:
                    row["wrongCost"] += reviewer_cost
                if outcome == "rejectFraud" and observed.get("chargeKind") == "hidden":
                    row["hiddenFraud"] += 1
            else:
                row["unresolvedCount"] += 1
                row["unresolvedCost"] += reviewer_cost
            return outcome

        def team_row(team: str) -> dict[str, Any]:
            return {
                "team": team, "issuedIncome": 0.0, "reviewerCost": 0.0,
                "net": 0.0, "issuedDecisions": 0, "reviewedDecisions": 0,
                "acceptedByMarket": 0, "reviewerAccepts": 0,
                "wrongReviewCost": 0.0, "rejectFairCount": 0,
                "rejectFairCost": 0.0, "acceptFraudCount": 0,
                "acceptFraudCost": 0.0, "hiddenFraud": 0,
                "chargeGroups": 0, "aggressionObservations": 0,
                "medianChargeToFloor": None, "aggressionCoverage": 0.0,
                "officialTotal": None, "scoreReconciliationDelta": None,
            }

        edges = {(issuer, reviewer): edge_row(issuer, reviewer)
                 for issuer in teams for reviewer in teams if issuer != reviewer}
        edge_timeline = {
            (int(game), issuer, reviewer): {
                "game": int(game), **edge_row(issuer, reviewer),
            }
            for game in games for issuer in teams for reviewer in teams if issuer != reviewer
        }
        summaries = {team: team_row(team) for team in teams}
        timeline: dict[tuple[str, int], dict[str, Any]] = {
            (team, int(game)): {
                "team": team, "game": int(game), "issuedIncome": 0.0,
                "reviewerCost": 0.0, "net": 0.0, "cumulativeNet": 0.0,
                "issuedDecisions": 0, "acceptedByMarket": 0,
                "reviewedDecisions": 0, "reviewerAccepts": 0,
                "officialScore": None, "officialCumulativeScore": None,
                "scoreReconciliationDelta": None,
            }
            for team in teams for game in games
        }
        aggression: dict[str, list[float]] = defaultdict(list)

        for (game, item, issuer), group in self._groups.items():
            if issuer not in summaries:
                continue
            summaries[issuer]["chargeGroups"] += 1
            observed = group.observed()
            threshold = self._thresholds.get((game, item))
            charge = observed.get("charge")
            if threshold and float(threshold["tLo"]) > 0 and charge is not None:
                aggression[issuer].append(float(charge) / float(threshold["tLo"]))
            for reviewer, (accepted, issuer_income) in group.decisions.items():
                if reviewer == issuer or (issuer, reviewer) not in edges:
                    continue
                reviewer_cost, classification = self._reviewer_cost(group, reviewer)
                edge = edges[(issuer, reviewer)]
                outcome = record_edge_decision(
                    edge, accepted, issuer_income, reviewer_cost, classification, observed
                )
                frame_edge = edge_timeline.get((game, issuer, reviewer))
                if frame_edge is not None:
                    frame_outcome = record_edge_decision(
                        frame_edge, accepted, issuer_income, reviewer_cost,
                        classification, observed,
                    )
                    if frame_outcome != outcome:
                        raise AssertionError("market frame classification diverged")

                issuer_summary = summaries[issuer]
                reviewer_summary = summaries[reviewer]
                issuer_summary["issuedIncome"] += issuer_income
                issuer_summary["issuedDecisions"] += 1
                issuer_summary["acceptedByMarket"] += int(accepted)
                reviewer_summary["reviewerCost"] += reviewer_cost
                reviewer_summary["reviewedDecisions"] += 1
                reviewer_summary["reviewerAccepts"] += int(accepted)
                if outcome == "rejectFair":
                    reviewer_summary["wrongReviewCost"] += reviewer_cost
                    reviewer_summary["rejectFairCount"] += 1
                    reviewer_summary["rejectFairCost"] += reviewer_cost
                elif outcome == "acceptFraud":
                    reviewer_summary["wrongReviewCost"] += reviewer_cost
                    reviewer_summary["acceptFraudCount"] += 1
                    reviewer_summary["acceptFraudCost"] += reviewer_cost
                elif outcome == "rejectFraud" and observed.get("chargeKind") == "hidden":
                    reviewer_summary["hiddenFraud"] += 1

                point_issuer = timeline.get((issuer, game))
                point_reviewer = timeline.get((reviewer, game))
                if point_issuer is not None:
                    point_issuer["issuedIncome"] += issuer_income
                    point_issuer["issuedDecisions"] += 1
                    point_issuer["acceptedByMarket"] += int(accepted)
                if point_reviewer is not None:
                    point_reviewer["reviewerCost"] += reviewer_cost
                    point_reviewer["reviewedDecisions"] += 1
                    point_reviewer["reviewerAccepts"] += int(accepted)

        race_by_team = {str(row["team"]): row for row in race.get("series", [])}
        summary_rows = []
        timeline_rows = []
        for team in teams:
            summary = summaries[team]
            summary["issuedIncome"] = _money(summary["issuedIncome"])
            summary["reviewerCost"] = _money(summary["reviewerCost"])
            summary["net"] = _money(summary["issuedIncome"] - summary["reviewerCost"])
            summary["wrongReviewCost"] = _money(summary["wrongReviewCost"])
            summary["rejectFairCost"] = _money(summary["rejectFairCost"])
            summary["acceptFraudCost"] = _money(summary["acceptFraudCost"])
            summary["marketAcceptRate"] = (
                round(summary["acceptedByMarket"] / summary["issuedDecisions"], 5)
                if summary["issuedDecisions"] else None
            )
            summary["reviewerAcceptRate"] = (
                round(summary["reviewerAccepts"] / summary["reviewedDecisions"], 5)
                if summary["reviewedDecisions"] else None
            )
            ratios = aggression.get(team, [])
            summary["aggressionObservations"] = len(ratios)
            summary["medianChargeToFloor"] = _median(ratios)
            summary["aggressionCoverage"] = (
                round(len(ratios) / summary["chargeGroups"], 5)
                if summary["chargeGroups"] else 0.0
            )
            race_row = race_by_team.get(team)
            official_total = race_row.get("total") if race_row else None
            summary["officialTotal"] = None if official_total is None else _money(official_total)
            summary["scoreReconciliationDelta"] = (
                None if official_total is None else round(summary["net"] - float(official_total), 6)
            )
            summary_rows.append(summary)

            cumulative = 0.0
            official_cumulative = 0.0
            rounds = race_row.get("rounds", []) if race_row else []
            scores = race_row.get("scores", []) if race_row else []
            for index, game in enumerate(games):
                point = timeline[(team, int(game))]
                point["issuedIncome"] = _money(point["issuedIncome"])
                point["reviewerCost"] = _money(point["reviewerCost"])
                point["net"] = _money(point["issuedIncome"] - point["reviewerCost"])
                cumulative += point["net"]
                point["cumulativeNet"] = _money(cumulative)
                point["marketAcceptRate"] = (
                    round(point["acceptedByMarket"] / point["issuedDecisions"], 5)
                    if point["issuedDecisions"] else None
                )
                point["reviewerAcceptRate"] = (
                    round(point["reviewerAccepts"] / point["reviewedDecisions"], 5)
                    if point["reviewedDecisions"] else None
                )
                official_round = rounds[index] if index < len(rounds) else None
                point["officialScore"] = None if official_round is None else _money(official_round)
                if official_round is not None:
                    official_cumulative += float(official_round)
                official_cumulative_score = (
                    scores[index] if index < len(scores) else
                    official_cumulative if official_round is not None else None
                )
                point["officialCumulativeScore"] = (
                    None if official_cumulative_score is None else _money(official_cumulative_score)
                )
                point["scoreReconciliationDelta"] = (
                    None if official_round is None else round(point["net"] - float(official_round), 6)
                )
                timeline_rows.append(point)

        edge_rows = []
        money_fields = [
            "issuerIncome", "reviewerCost", "penaltyWedge", "wrongCost",
            "unresolvedCost", *(f"{outcome}Cost" for outcome in outcome_names),
        ]
        def finalize_edge(edge: dict[str, Any], *, money_digits: int = 2) -> None:
            for field_name in money_fields:
                edge[field_name] = round(float(edge[field_name]), money_digits)
            edge["acceptRate"] = (
                round(edge["accepted"] / edge["decisions"], 5)
                if edge["decisions"] else None
            )
            edge["netExchange"] = _money(edge["issuerIncome"] - edge["reviewerCost"])

        for edge in edges.values():
            finalize_edge(edge)
            edge_rows.append(edge)
        edge_rows.sort(key=lambda row: (row["issuer"].casefold(), row["reviewer"].casefold()))

        # The temporal cube is array-encoded because 17 × 16 × played-games rows would
        # otherwise repeat long field and team names thousands of times. The public
        # column contract keeps the encoding explicit and independently checkable.
        edge_timeline_columns = [
            "game", "issuerIndex", "reviewerIndex", "decisions", "accepted",
            "issuerIncome", "reviewerCost", "penaltyWedge", "wrongCost",
            "unresolvedCount", "unresolvedCost", "hiddenFraud",
            "acceptFairCount", "acceptFairCost", "rejectFairCount", "rejectFairCost",
            "acceptFraudCount", "acceptFraudCost", "rejectFraudCount", "rejectFraudCost",
        ]
        team_index = {team: index for index, team in enumerate(teams)}
        edge_timeline_rows = []
        for game in games:
            for issuer in teams:
                for reviewer in teams:
                    if issuer == reviewer:
                        continue
                    frame = edge_timeline[(int(game), issuer, reviewer)]
                    # Preserve sub-cent arithmetic inside replay frames. Rounding every
                    # edge/game cell to cents before a cumulative replay can otherwise
                    # manufacture visible drift when hundreds of cells are summed.
                    finalize_edge(frame, money_digits=6)
                    encoded = {
                        **frame,
                        "issuerIndex": team_index[issuer],
                        "reviewerIndex": team_index[reviewer],
                    }
                    edge_timeline_rows.append([
                        encoded[column] for column in edge_timeline_columns
                    ])

        return {
            "schemaVersion": 2, "generatedAt": generated_at, "team": US,
            "gameIds": games, "teams": teams, "edges": edge_rows,
            "summaries": summary_rows, "timeline": timeline_rows,
            "edgeTimeline": {
                "encoding": "dense-array-v1",
                "columns": edge_timeline_columns,
                "rows": edge_timeline_rows,
            },
            "denominators": {
                "edge": "one ordered issuer→reviewer relationship across played games",
                "edgeFrame": "one ordered issuer→reviewer relationship in one played game",
                "decision": "one recorded reviewer decision on one issuer charge group",
                "issuerIncome": "sum of recorded issuer payouts in EUR",
                "reviewerCost": "payoff-matrix settlement in EUR; rejected fair is 1.5 × exact charge",
                "wrongCost": "observed reviewer settlement for reject-fair plus accept-fraud decisions",
                "aggression": "observable issuer charge divided by sanctioned floor; hidden charges excluded",
            },
            "blindSpot": (
                "Rejected fraudulent charges record zero and their attempted sizes are invisible. "
                "Wrong-review cost, penalty, and market-flow views are therefore observed lower bounds; "
                "they are descriptive settlement accounting, not counterfactual tournament impact."
            ),
        }

    def _refresh_leaderboard(self, now: float) -> None:
        # Slow timer plus bounded circuit-breaker cooldown protects the local proxy.
        interval = min(120.0, 15.0 * (2 ** min(self._leaderboard_failures, 3)))
        if now - self._leaderboard_last_attempt < interval:
            return
        self._leaderboard_last_attempt = now
        request = urllib.request.Request(
            self.leaderboard_url, headers={"Accept": "application/json", "User-Agent": "OasisViz/1"}
        )
        try:
            with urllib.request.urlopen(request, timeout=1.5) as response:
                if response.status != 200:
                    raise DataUnavailable(f"local leaderboard HTTP {response.status}")
                raw = response.read(MAX_REMOTE_BYTES + 1)
                if len(raw) > MAX_REMOTE_BYTES:
                    raise DataUnavailable("local leaderboard response too large")
                payload = json.loads(raw)
                if not isinstance(payload, dict) or not isinstance(payload.get("standings"), list):
                    raise DataUnavailable("local leaderboard schema mismatch")
            self._leaderboard = payload
            self._leaderboard_failures = 0
            self._dependencies["leaderboard"] = {
                "ok": True, "critical": False, "mode": "local-proxy",
                "fetchedAt": payload.get("fetched_at"),
            }
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError,
                DataUnavailable) as exc:
            self._leaderboard_failures += 1
            self._dependencies["leaderboard"] = {
                "ok": False, "critical": False, "mode": "degraded-stale-cache",
                "error": type(exc).__name__, "retryAfterSeconds": interval,
                "hasStaleData": self._leaderboard is not None,
            }

    def _operations_context(self, now_dt: datetime) -> dict[str, Any]:
        """Build claim-free recorder freshness and deadline evidence from sanitized events."""
        played_games = [
            int(game) for game in (self._overview or {}).get("race", {}).get("gameIds", [])
        ]
        played_set = set(played_games)
        pipelines = self._events.get("pipelines", {})
        all_games = sorted(played_set | {int(game) for game in pipelines})
        stage_envelope_values: dict[str, list[float]] = defaultdict(list)
        rows = []
        timestamp_candidates: list[tuple[float, str]] = []

        def valid_time(value: Any) -> float | None:
            number = _finite(value, float("nan"))
            return number if math.isfinite(number) and number >= 0 else None

        for game in all_games:
            pipeline = pipelines.get(game, {})
            milestones = pipeline.get("milestones", []) if isinstance(pipeline, dict) else []
            activities = pipeline.get("activities", []) if isinstance(pipeline, dict) else []
            event_counts = pipeline.get("eventCounts", {}) if isinstance(pipeline, dict) else {}
            recorded = bool(pipeline.get("available")) if isinstance(pipeline, dict) else False
            stage_times: dict[str, float | None] = {}
            observed_stages = []
            stage_candidates: list[tuple[float, str, str]] = []
            for stage in PIPELINE_CORE:
                observed = int(event_counts.get(stage, 0)) > 0
                if observed:
                    observed_stages.append(stage)
                candidates = [
                    valid_time(row.get("elapsedFromStartMs"))
                    for row in milestones if row.get("type") == stage
                ]
                candidates.extend(
                    valid_time(row.get("elapsedFromStartMs"))
                    for row in activities if row.get("type") == stage
                )
                finite = [value for value in candidates if value is not None]
                stage_time = min(finite) if finite else None
                stage_times[stage] = stage_time
                if stage_time is not None:
                    stage_envelope_values[stage].append(stage_time)
                    stage_rows = [row for row in milestones if row.get("type") == stage]
                    stage_rows.extend(row for row in activities if row.get("type") == stage)
                    timestamp = next((str(row.get("ts") or row.get("firstTs") or "")
                                      for row in stage_rows
                                      if row.get("ts") or row.get("firstTs")), "")
                    stage_candidates.append((stage_time, stage, timestamp))

            sends = [row for row in milestones if row.get("type") == "submission.sent"]
            tier_one = [row for row in sends if row.get("tier") == 1]
            tier_two = [row for row in sends if row.get("tier") == 2]

            def earliest_elapsed(entries: list[dict[str, Any]]) -> float | None:
                values = [valid_time(row.get("elapsedFromStartMs")) for row in entries]
                finite = [value for value in values if value is not None]
                return min(finite) if finite else None

            def target_status(entries: list[dict[str, Any]], elapsed: float | None,
                              target_ms: float) -> str:
                if not entries:
                    return "unobserved"
                if elapsed is None:
                    return "timing-unavailable"
                return "met" if elapsed <= target_ms else "late"

            first_send_ms = earliest_elapsed(sends)
            tier_one_ms = earliest_elapsed(tier_one)
            tier_two_ms = earliest_elapsed(tier_two)
            if stage_candidates:
                last_elapsed, last_stage, last_stage_at = max(stage_candidates)
            else:
                last_elapsed, last_stage, last_stage_at = None, None, ""
            if last_stage_at:
                _, epoch = _event_time(last_stage_at)
                if epoch is not None:
                    timestamp_candidates.append((epoch, last_stage_at))
            alerts = sum(int(value) for value in pipeline.get("alerts", {}).values()) \
                if isinstance(pipeline, dict) else 0
            failed_calls = sum(row.get("ok") is False for row in sends)
            successful_calls = sum(row.get("ok") is True for row in sends)
            rows.append({
                "game": game, "played": game in played_set, "recorded": recorded,
                "coreCoverage": _finite(pipeline.get("completeness")) if recorded else 0.0,
                "eventCount": int(pipeline.get("eventCount", 0)) if recorded else 0,
                "observedStages": observed_stages, "stageTimesMs": stage_times,
                "firstSendMs": first_send_ms, "tier1SendMs": tier_one_ms,
                "tier2SendMs": tier_two_ms,
                "tier1TargetStatus": target_status(tier_one, tier_one_ms, 2_000),
                "tier2DeadlineStatus": target_status(tier_two, tier_two_ms, 52_000),
                "submissionCalls": len(sends), "successfulCalls": successful_calls,
                "failedCalls": failed_calls, "alerts": alerts,
                "roundPlayedObserved": int(event_counts.get("round.played", 0)) > 0,
                "lastStage": last_stage, "lastStageAt": last_stage_at,
                "lastElapsedMs": last_elapsed,
                "observedSpanMs": pipeline.get("observedSpanMs") if recorded else None,
            })

        recorded_rows = [row for row in rows if row["recorded"]]
        recorded_played = [row for row in recorded_rows if row["played"]]
        latest_recorded_game = max((row["game"] for row in recorded_rows), default=None)
        latest_played_game = max(played_games, default=None)
        lag_played_games = (
            len([game for game in played_games if game > latest_recorded_game])
            if latest_recorded_game is not None else len(played_games)
        )

        live_rows = self._events.get("live", [])
        for row in live_rows:
            timestamp, epoch = _event_time(row.get("ts"))
            if epoch is not None:
                timestamp_candidates.append((epoch, timestamp))
        latest_event_at = max(timestamp_candidates)[1] if timestamp_candidates else None
        latest_event_epoch = max((value[0] for value in timestamp_candidates), default=None)
        latest_event_age_seconds = (
            None if latest_event_epoch is None
            else round(max(0.0, now_dt.timestamp() - latest_event_epoch), 1)
        )
        sent_live = [row for row in live_rows if row.get("type") == "submission.sent"]
        latest_submission_at = None
        latest_submission_epoch = None
        for row in sent_live:
            timestamp, epoch = _event_time(row.get("ts"))
            if epoch is not None and (latest_submission_epoch is None or epoch > latest_submission_epoch):
                latest_submission_at, latest_submission_epoch = timestamp, epoch
        latest_submission_age_seconds = (
            None if latest_submission_epoch is None
            else round(max(0.0, now_dt.timestamp() - latest_submission_epoch), 1)
        )

        if not recorded_rows:
            telemetry_status = "unavailable"
        elif lag_played_games > 0:
            telemetry_status = "stale-played-rounds"
        elif latest_event_age_seconds is None:
            telemetry_status = "timestamp-unavailable"
        elif latest_event_age_seconds > CADENCE_SECONDS * 2:
            telemetry_status = "stale-clock"
        else:
            telemetry_status = "current"
        self._dependencies["operationsTelemetry"] = {
            "ok": telemetry_status == "current", "critical": False,
            "mode": telemetry_status, "latestRecordedGame": latest_recorded_game,
            "latestPlayedGame": latest_played_game, "lagPlayedGames": lag_played_games,
        }

        tier_one_values = [row["tier1SendMs"] for row in recorded_rows
                           if row["tier1SendMs"] is not None]
        tier_two_values = [row["tier2SendMs"] for row in recorded_rows
                           if row["tier2SendMs"] is not None]
        stage_envelope = [{
            "stage": stage, "observations": len(stage_envelope_values.get(stage, [])),
            "p10Ms": _percentile(stage_envelope_values.get(stage, []), 0.1),
            "p50Ms": _percentile(stage_envelope_values.get(stage, []), 0.5),
            "p90Ms": _percentile(stage_envelope_values.get(stage, []), 0.9),
        } for stage in PIPELINE_CORE]
        return {
            "schemaVersion": 1, "stages": list(PIPELINE_CORE),
            "telemetryStatus": telemetry_status,
            "latestPlayedGame": latest_played_game,
            "latestRecordedGame": latest_recorded_game,
            "lagPlayedGames": lag_played_games,
            "latestEventAt": latest_event_at,
            "latestEventAgeSeconds": latest_event_age_seconds,
            "latestSubmissionAt": latest_submission_at,
            "latestSubmissionAgeSeconds": latest_submission_age_seconds,
            "games": rows, "stageEnvelope": stage_envelope,
            "summary": {
                "playedGames": len(played_games), "pipelineGames": len(recorded_rows),
                "recordedPlayedGames": len(recorded_played),
                "missingPlayedGames": len(played_games) - len(recorded_played),
                "recordedCoverage": (
                    round(len(recorded_played) / len(played_games), 4) if played_games else None
                ),
                "completeCoreGames": sum(row["coreCoverage"] == 1 for row in recorded_rows),
                "meanCoreCoverage": (
                    round(statistics.mean(row["coreCoverage"] for row in recorded_rows), 4)
                    if recorded_rows else None
                ),
                "tier1Observed": len(tier_one_values),
                "tier1AtOrUnderTarget": sum(value <= 2_000 for value in tier_one_values),
                "tier1TargetRate": (
                    round(sum(value <= 2_000 for value in tier_one_values) /
                          len(tier_one_values), 4) if tier_one_values else None
                ),
                "tier1P50Ms": _percentile(tier_one_values, 0.5),
                "tier1P95Ms": _percentile(tier_one_values, 0.95),
                "tier2Observed": len(tier_two_values),
                "tier2AtOrUnderDeadline": sum(value <= 52_000 for value in tier_two_values),
                "tier2DeadlineRate": (
                    round(sum(value <= 52_000 for value in tier_two_values) /
                          len(tier_two_values), 4) if tier_two_values else None
                ),
                "tier2P50Ms": _percentile(tier_two_values, 0.5),
                "tier2P95Ms": _percentile(tier_two_values, 0.95),
                "failedSubmissionCalls": sum(row["failedCalls"] for row in recorded_rows),
                "alerts": sum(row["alerts"] for row in recorded_rows),
            },
        }

    def _live_context(self) -> dict[str, Any]:
        payload = self._leaderboard or {}
        games = payload.get("games") if isinstance(payload.get("games"), list) else []
        next_game = None
        now_raw = payload.get("server_now")
        try:
            now_dt = datetime.fromisoformat(str(now_raw).replace("Z", "+00:00"))
        except ValueError:
            now_dt = datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)
        for game in games:
            try:
                start = datetime.fromisoformat(str(game.get("start_time")).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                continue
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if start > now_dt:
                next_game = {"game": int(game["id"]), "startTime": start.isoformat()}
                break
        if next_game is None and self._overview:
            for game in self._overview.get("games", []):
                if not game.get("played") and game.get("startTime"):
                    next_game = {"game": game["id"], "startTime": game["startTime"]}
                    break
        sent = [row for row in self._events.get("live", []) if row["type"] == "submission.sent"]
        latencies = [row["latencyMs"] for row in sent if row.get("latencyMs") is not None]
        tier_rows: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in sent:
            if isinstance(row.get("tier"), int):
                tier_rows[row["tier"]].append(row)
        telemetry = {
            "submissions": len(sent),
            "successRate": round(sum(bool(row.get("ok")) for row in sent) / len(sent), 4) if sent else None,
            "p50LatencyMs": _percentile(latencies, 0.5),
            "p95LatencyMs": _percentile(latencies, 0.95),
            "lastLatencyMs": latencies[-1] if latencies else None,
            "timeline": [{"seq": row["seq"], "game": row["game"], "tier": row.get("tier"),
                          "latencyMs": row.get("latencyMs"), "ok": row.get("ok"), "status": row.get("status")}
                         for row in sent[-80:]],
            "tiers": [{
                "tier": tier, "submissions": len(rows),
                "successRate": round(sum(bool(row.get("ok")) for row in rows) / len(rows), 4),
                "p50LatencyMs": _percentile(
                    [row["latencyMs"] for row in rows if row.get("latencyMs") is not None], 0.5),
            } for tier, rows in sorted(tier_rows.items())],
        }
        return {
            "serverNow": now_dt.isoformat(), "nextRound": next_game,
            "eventsMaxSeq": self._events.get("maxSeq", 0),
            "recent": self._events.get("live", [])[-40:],
            "performance": payload.get("performance"),
            "standingsTotal": [
                {"team": row.get("team_name"), "total": _money(row.get("total"))}
                for row in payload.get("standings", []) if isinstance(row, dict)
            ],
            "telemetry": telemetry,
            "operations": self._operations_context(now_dt),
        }

    def _dependency_summary(self) -> dict[str, Any]:
        critical_ok = all(row.get("ok") for row in self._dependencies.values()
                          if row.get("critical"))
        degraded = any(not row.get("ok") for row in self._dependencies.values()
                       if not row.get("critical"))
        return {"ready": critical_ok, "degraded": degraded,
                "items": self._dependencies.copy()}

    def overview(self) -> dict[str, Any]:
        self.refresh()
        if self._overview is None:
            raise DataUnavailable("overview is not available")
        with self._lock:
            return copy.deepcopy(self._overview)

    def reviewer(self) -> dict[str, Any]:
        self.refresh()
        if self._reviewer_lab is None:
            raise DataUnavailable("reviewer evidence is not available")
        with self._lock:
            return copy.deepcopy(self._reviewer_lab)

    def market(self) -> dict[str, Any]:
        self.refresh()
        if self._market is None:
            raise DataUnavailable("market evidence is not available")
        with self._lock:
            return copy.deepcopy(self._market)

    def game(self, game: int) -> dict[str, Any]:
        if not 0 <= game <= 100:
            raise ValueError("game must be between 0 and 100")
        self.refresh()
        with self._lock:
            cached = self._game_cache.get(game)
            if cached is not None:
                return copy.deepcopy(cached)
            payload = self._build_game(game)
            self._game_cache[game] = payload
            _atomic_json(self.cache_dir / "games" / f"game-{game}.json", payload)
            return copy.deepcopy(payload)

    def _build_game(self, game: int) -> dict[str, Any]:
        econ = self._game_economics(game)
        item_economics = self._game_item_economics(game)
        item_ids = sorted({item for (g, item, _) in self._groups if g == game} |
                          {item for (g, item) in self._thresholds if g == game} |
                          {item for (g, item) in self._events.get("decisions", {}) if g == game})
        items = []
        for item in item_ids:
            item_flow = item_economics.get(item, self._empty_item_economics())
            decision = self._events.get("decisions", {}).get((game, item))
            belief = self._events.get("beliefs", {}).get((game, item))
            threshold = self._thresholds.get((game, item))
            opponents = []
            for (g, it, issuer), group in self._groups.items():
                if g != game or it != item or issuer == US:
                    continue
                observed = group.observed()
                opponents.append({"team": issuer, **observed})
            opponents.sort(key=lambda row: row["team"].casefold())
            status = "unlabelled"
            if decision and threshold:
                if decision["a"] < threshold["tLo"]:
                    status = "under"
                elif threshold["tHi"] is not None and decision["a"] > threshold["tHi"]:
                    status = "over"
                elif threshold["tHi"] is None:
                    status = "above-floor-open-ceiling"
                else:
                    status = "inside-bracket"
            items.append({
                "idx": item, "decision": decision, "belief": belief,
                "threshold": threshold, "status": status, "opponents": opponents,
                "rules": self._events.get("rules", {}).get((game, item), []),
                "economics": item_flow,
            })
        official = None
        reconciliation = None
        if self._overview:
            summary = next((row for row in self._overview["games"] if row["id"] == game), None)
            official = summary.get("officialScore") if summary else None
            reconciliation = summary.get("scoreReconciliationDelta") if summary else None
        return {
            "game": game, "economics": econ, "items": items, "officialScore": official,
            "scoreReconciliationDelta": reconciliation,
            "flight": copy.deepcopy(self._events.get("pipelines", {}).get(game, {
                "game": game, "available": False, "milestones": [], "activities": [],
                "eventCounts": {}, "eventCount": 0, "alerts": {}, "completeness": 0,
                "observedCoreStages": 0, "coreStageDenominator": len(PIPELINE_CORE),
                "observedSpanMs": None, "startTs": "",
            })) | {"latestRecordedGame": self._events.get("latestPipelineGame")},
            "replay": copy.deepcopy(self._events.get("replays", {}).get(game, {
                "game": game, "available": False, "events": [], "eventCount": 0,
                "itemCount": 0, "itemsWithBelief": 0, "itemsWithDecision": 0,
                "beliefEvents": 0, "ruleEvents": 0, "decisionEvents": 0,
                "startTs": "",
            })),
            "denominators": {
                "income": "sum of Oasis issuer payout across opponent reviewers",
                "cost": "Oasis reviewer settlement cost; rejected fair is 1.5 × issuer payout",
                "matrix": "one Oasis review decision per opponent charge with a proven side",
                "opponentCharge": "exact only after a paid rejection; otherwise lower-bound or hidden",
                "itemFlow": "observed Oasis issuer settlement minus observed Oasis reviewer settlement, per item",
                "flight": "sanitized append-only event records; elapsed time is between logged boundaries",
                "replay": "one sanitized item.belief, rule.fired, or item.decided event",
            },
            "blindSpot": ("Rejected fraudulent charges settle at €0 and hide their submitted size. "
                          "Actual paid cost is observable; attempted-fraud and counterfactual exposure are lower bounds."),
        }

    def item(self, game: int, item: int) -> dict[str, Any]:
        payload = self.game(game)
        base = next((row for row in payload["items"] if row["idx"] == item), None)
        if base is None:
            raise KeyError(f"game {game} item {item} is unavailable")
        opponents = []
        for (g, it, issuer), group in self._groups.items():
            if g != game or it != item or issuer == US:
                continue
            observed = group.observed()
            decision = group.decisions.get(US)
            accepted, paid = decision if decision is not None else (None, None)
            cost, _ = self._reviewer_cost(group, US)
            opponents.append({
                "team": issuer, **observed, "weAccepted": accepted,
                "issuerPayout": None if paid is None else round(paid, 2),
                "ourReviewerCost": None if decision is None else round(cost, 2),
            })
        opponents.sort(key=lambda row: row["team"].casefold())
        return {**base, "game": game, "opponentDecisions": opponents,
                "blindSpot": ("A lower-bound marker is an observed fraudulent payout, not the original charge. "
                              "A hidden marker means every reviewer rejected it and no charge amount is recoverable.")}

    def live(self, after: int = 0) -> dict[str, Any]:
        self.refresh()
        with self._lock:
            events = [row for row in self._events.get("live", []) if row["seq"] > after]
            return {"events": copy.deepcopy(events[-80:]),
                    "maxSeq": self._events.get("maxSeq", 0),
                    "context": copy.deepcopy(self._live_context()),
                    "dependencies": copy.deepcopy(self._dependency_summary()),
                    "overviewRevision": self._overview.get("generatedAt") if self._overview else None}

    def health(self) -> dict[str, Any]:
        try:
            self.refresh()
        except DataUnavailable:
            pass
        return self._dependency_summary()
