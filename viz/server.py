"""Dependency-light local HTTP server for the Oasis Tournament Observatory."""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from viz.data_layer import PIPELINE_CORE, DataUnavailable, ROOT, RUNTIME, TournamentStore


STATIC = Path(__file__).resolve().parent / "static"
MAX_QUERY_LENGTH = 2048
MAX_QUERY_FIELDS = 25
TOKEN = re.compile(r"^(?:pdf|image)-[1-9][0-9]*$")


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


class CaseService:
    """Bounded, credential-free subprocess boundary for document decryption."""

    def __init__(self, root: Path = ROOT, runtime: Path = RUNTIME) -> None:
        self.root = root.resolve()
        self.runtime = runtime.resolve()
        self._locks: dict[int, threading.Lock] = {}
        self._guard = threading.Lock()
        self._cache: dict[int, dict[str, Any]] = {}
        self._worker_capacity = threading.BoundedSemaphore(2)

    def _lock(self, game: int) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(game, threading.Lock())

    def ensure(self, game: int) -> dict[str, Any]:
        if not 0 <= game <= 100:
            raise ValueError("game must be between 0 and 100")
        with self._lock(game):
            cached = self._cache.get(game)
            if cached is not None:
                return cached
            manifest_path = self.runtime / "manifests" / f"game-{game}.json"
            env = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "PYTHONPATH": str(self.root),
                "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
            }
            if not self._worker_capacity.acquire(timeout=0.25):
                raise DataUnavailable("case worker capacity is busy; retry shortly")
            try:
                try:
                    proc = subprocess.run(
                        [sys.executable, "-m", "viz.case_worker", "--root", str(self.root),
                         "--runtime", str(self.runtime), "--game", str(game)],
                        cwd=self.runtime, env=env, capture_output=True, text=True,
                        timeout=45, check=False,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise DataUnavailable("case decryption exceeded 45 seconds") from exc
                except OSError as exc:
                    raise DataUnavailable(f"case worker unavailable: {type(exc).__name__}") from exc
            finally:
                self._worker_capacity.release()
            if proc.returncode != 0:
                failure = "CaseWorkerError"
                try:
                    failure = str(json.loads(proc.stderr.splitlines()[-1]).get("error") or failure)
                except (IndexError, json.JSONDecodeError, AttributeError):
                    pass
                raise DataUnavailable(f"case documents unavailable ({failure})")
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise DataUnavailable("case manifest could not be read") from exc
            if manifest.get("game") != game or not isinstance(manifest.get("media"), dict):
                raise DataUnavailable("case manifest schema mismatch")
            self._cache[game] = manifest
            return manifest

    def public_manifest(self, game: int) -> dict[str, Any]:
        manifest = self.ensure(game)
        return {
            key: value for key, value in manifest.items()
            if key not in {"media", "version"}
        } | {
            "pdfs": [{**row, "url": f"/api/media?game={game}&token={row['token']}"}
                     for row in manifest.get("pdfs", [])],
            "images": [{**row, "url": f"/api/media?game={game}&token={row['token']}"}
                       for row in manifest.get("images", [])],
        }

    def media(self, game: int, token: str) -> tuple[Path, str]:
        if TOKEN.fullmatch(token) is None:
            raise ValueError("invalid media token")
        manifest = self.ensure(game)
        row = manifest["media"].get(token)
        if not isinstance(row, dict):
            raise KeyError("media token not found")
        path = (self.runtime / str(row.get("path") or "")).resolve()
        if not _inside(path, self.runtime / "cases") or not path.is_file():
            raise DataUnavailable("media file is unavailable")
        mime = str(row.get("mime") or "application/octet-stream")
        if mime not in {"application/pdf", "image/png", "image/jpeg", "image/webp", "image/gif"}:
            raise DataUnavailable("media type is not allow-listed")
        return path, mime


class ObservatoryServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address: tuple[str, int], handler: type[BaseHTTPRequestHandler],
                 store: TournamentStore, cases: CaseService) -> None:
        self.store = store
        self.cases = cases
        super().__init__(address, handler)


class Handler(BaseHTTPRequestHandler):
    server: ObservatoryServer
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        # High-volume success access logs are intentionally suppressed. Failures are
        # emitted as structured records from _problem with a request correlation ID.
        return

    def _security_headers(self, *, cache: str = "no-store") -> None:
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
            "connect-src 'self'; frame-src 'self' blob:; object-src 'self'; base-uri 'none'; "
            "form-action 'none'; frame-ancestors 'self'",
        )
        self.send_header("X-Request-ID", self.request_id)

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self._security_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _problem(self, status: int, title: str, detail: str,
                 *, failure_class: str) -> None:
        record = {
            "level": "ERROR" if status >= 500 else "WARN",
            "requestId": self.request_id, "status": status,
            "failureClass": failure_class, "path": urlparse(self.path).path,
        }
        print(json.dumps(record, separators=(",", ":")), file=sys.stderr)
        self._send_json({
            "type": "about:blank", "title": title, "status": status,
            "detail": detail, "requestId": self.request_id,
        }, status)

    @staticmethod
    def _integer(query: dict[str, list[str]], name: str, lo: int, hi: int) -> int:
        values = query.get(name)
        if not values or len(values) != 1 or not values[0].isdigit():
            raise ValueError(f"{name} must be an integer")
        value = int(values[0])
        if not lo <= value <= hi:
            raise ValueError(f"{name} must be between {lo} and {hi}")
        return value

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        self.request_id = uuid.uuid4().hex[:16]
        if len(self.path) > MAX_QUERY_LENGTH:
            self._problem(414, "URI too long", "The request URI exceeds the local safety limit.",
                          failure_class="InputLimit")
            return
        parsed = urlparse(self.path)
        try:
            query = parse_qs(
                parsed.query,
                keep_blank_values=True,
                max_num_fields=MAX_QUERY_FIELDS,
            )
        except ValueError:
            self._problem(
                400,
                "Invalid query",
                f"The request exceeds the {MAX_QUERY_FIELDS}-field local safety limit.",
                failure_class="InputLimit",
            )
            return
        try:
            if parsed.path == "/api/overview":
                self._send_json(self.server.store.overview())
            elif parsed.path == "/api/reviewer":
                self._send_json(self.server.store.reviewer())
            elif parsed.path == "/api/market":
                self._send_json(self.server.store.market())
            elif parsed.path == "/api/game":
                game = self._integer(query, "id", 0, 100)
                self._send_json(self.server.store.game(game))
            elif parsed.path == "/api/item":
                game = self._integer(query, "game", 0, 100)
                item = self._integer(query, "item", 1, 500)
                self._send_json(self.server.store.item(game, item))
            elif parsed.path == "/api/case":
                game = self._integer(query, "game", 0, 100)
                self._send_json(self.server.cases.public_manifest(game))
            elif parsed.path == "/api/media":
                game = self._integer(query, "game", 0, 100)
                values = query.get("token")
                if not values or len(values) != 1:
                    raise ValueError("token is required")
                self._send_media(*self.server.cases.media(game, values[0]))
            elif parsed.path == "/api/live":
                after = self._integer(query, "after", 0, 10**12) if "after" in query else 0
                self._send_json(self.server.store.live(after))
            elif parsed.path == "/api/health/live":
                self._send_json({"live": True, "semantics": "HTTP process can serve requests"})
            elif parsed.path == "/api/health/ready":
                health = self.server.store.health()
                self._send_json(health, 200 if health.get("ready") else 503)
            elif parsed.path.startswith("/api/"):
                self._problem(404, "Not found", "The requested API endpoint does not exist.",
                              failure_class="NotFound")
            else:
                self._send_static(parsed.path)
        except ValueError as exc:
            self._problem(400, "Invalid request", str(exc), failure_class="InputValidation")
        except KeyError:
            self._problem(404, "Not found", "The requested tournament record is unavailable.",
                          failure_class="MissingRecord")
        except DataUnavailable as exc:
            self._problem(503, "Data unavailable", str(exc), failure_class="DependencyUnavailable")
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:  # noqa: BLE001 - final HTTP fault boundary
            self._problem(500, "Internal error", "The request failed safely.",
                          failure_class=type(exc).__name__)

    def do_HEAD(self) -> None:  # noqa: N802
        self.request_id = uuid.uuid4().hex[:16]
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._send_static(parsed.path, head_only=True)
        else:
            self._problem(405, "Method not allowed", "HEAD is available only for static entrypoints.",
                          failure_class="MethodNotAllowed")

    def do_POST(self) -> None:  # noqa: N802
        self.request_id = uuid.uuid4().hex[:16]
        self._problem(405, "Read only", "This application exposes no mutation endpoints.",
                      failure_class="ReadOnlyBoundary")

    def do_PUT(self) -> None:  # noqa: N802
        self.do_POST()

    def do_DELETE(self) -> None:  # noqa: N802
        self.do_POST()

    def _send_static(self, route: str, *, head_only: bool = False) -> None:
        relative = "index.html" if route in {"", "/", "/index.html"} else route.lstrip("/")
        if not re.fullmatch(r"[A-Za-z0-9_.\-/]+", relative):
            raise ValueError("invalid static path")
        path = (STATIC / relative).resolve()
        if not _inside(path, STATIC) or not path.is_file():
            self._problem(404, "Not found", "The requested asset does not exist.",
                          failure_class="StaticNotFound")
            return
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body = path.read_bytes()
        self.send_response(200)
        self._security_headers(cache="public, max-age=300" if path.name != "index.html" else "no-cache")
        self.send_header("Content-Type", f"{mime}; charset=utf-8" if mime.startswith("text/") or mime.endswith("javascript") else mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _send_media(self, path: Path, mime: str) -> None:
        size = path.stat().st_size
        start, end = 0, size - 1
        status = HTTPStatus.OK
        range_header = self.headers.get("Range")
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
            if match is None:
                self._problem(416, "Invalid range", "Only one byte range is supported.",
                              failure_class="RangeValidation")
                return
            first, last = match.groups()
            if first:
                start = int(first)
                end = int(last) if last else size - 1
            elif last:
                length = int(last)
                start = max(0, size - length)
                end = size - 1
            if start < 0 or end < start or start >= size:
                self._problem(416, "Range unavailable", "The byte range is outside this media file.",
                              failure_class="RangeBounds")
                return
            end = min(end, size - 1)
            status = HTTPStatus.PARTIAL_CONTENT
        length = end - start + 1
        self.send_response(status)
        self._security_headers(cache="private, max-age=60")
        self.send_header("Content-Type", mime)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Disposition", "inline")
        self.send_header("Content-Length", str(length))
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining:
                chunk = handle.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)


def _replay_checks(game: dict[str, object]) -> dict[str, bool]:
    replay = game.get("replay") if isinstance(game.get("replay"), dict) else {}
    events = replay.get("events") if isinstance(replay.get("events"), list) else []
    items = game.get("items") if isinstance(game.get("items"), list) else []
    item_by_id = {
        int(item["idx"]): item for item in items
        if isinstance(item, dict) and isinstance(item.get("idx"), int)
    }
    allowed = {
        "item.belief": {"type", "seq", "ts", "elapsedFromStartMs", "item",
                        "median", "sigma", "source"},
        "rule.fired": {"type", "seq", "ts", "elapsedFromStartMs", "item",
                       "rule", "shadow", "from", "to"},
        "item.decided": {"type", "seq", "ts", "elapsedFromStartMs", "item",
                         "a", "b", "covered"},
    }
    typed_events = [row for row in events if isinstance(row, dict)]
    latest_decisions: dict[int, dict[str, object]] = {}
    latest_beliefs: dict[int, dict[str, object]] = {}
    for row in typed_events:
        if not isinstance(row.get("item"), int):
            continue
        if row.get("type") == "item.decided":
            latest_decisions[int(row["item"])] = row
        elif row.get("type") == "item.belief":
            latest_beliefs[int(row["item"])] = row
    decision_match = all(
        item_id in item_by_id and
        isinstance(item_by_id[item_id].get("decision"), dict) and
        all(item_by_id[item_id]["decision"].get(key) == row.get(key)
            for key in ("seq", "a", "b", "covered"))
        for item_id, row in latest_decisions.items()
    )
    belief_match = all(
        item_id in item_by_id and
        isinstance(item_by_id[item_id].get("belief"), dict) and
        all(item_by_id[item_id]["belief"].get(key) == row.get(key)
            for key in ("seq", "median", "sigma", "source"))
        for item_id, row in latest_beliefs.items()
    )
    return {
        "counts": (
            replay.get("eventCount") == len(typed_events) and
            replay.get("beliefEvents") == sum(row.get("type") == "item.belief"
                                               for row in typed_events) and
            replay.get("ruleEvents") == sum(row.get("type") == "rule.fired"
                                             for row in typed_events) and
            replay.get("decisionEvents") == sum(row.get("type") == "item.decided"
                                                 for row in typed_events)
        ),
        "sequence": [row.get("seq") for row in typed_events] == sorted(
            row.get("seq") for row in typed_events
        ),
        "knownItems": all(row.get("item") in item_by_id for row in typed_events),
        "allowListed": all(
            row.get("type") in allowed and set(row) <= allowed[str(row.get("type"))]
            for row in typed_events
        ),
        "latestState": decision_match and belief_match,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Oasis read-only tournament observatory")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--allow-non-loopback", action="store_true")
    parser.add_argument("--check", action="store_true",
                        help="materialise and validate data, then exit without binding a port")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not 1 <= args.port <= 65535:
        print("invalid port", file=sys.stderr)
        return 2
    if args.host not in {"127.0.0.1", "::1", "localhost"} and not args.allow_non_loopback:
        print("refusing a non-loopback bind without --allow-non-loopback", file=sys.stderr)
        return 2
    store = TournamentStore()
    if args.check:
        try:
            overview = store.overview()
            reviewer = store.reviewer()
            market = store.market()
            health = store.health()
        except DataUnavailable as exc:
            print(f"check failed: {exc}", file=sys.stderr)
            return 1
        game_count = len(overview["race"]["gameIds"])
        played = [row for row in overview["games"] if row.get("played")]
        game_payloads = [store.game(int(row["id"])) for row in played]
        reconciled = all(
            row.get("scoreReconciliationDelta") is not None and
            abs(float(row["scoreReconciliationDelta"])) <= 0.011
            for row in played
        )
        rule_intelligence = overview.get("intelligence", {}).get("rules", {})
        portfolio = rule_intelligence.get("portfolios", {})
        raw_rule_records = rule_intelligence.get("records", [])
        portfolio_records = portfolio.get("records", [])
        raw_by_portfolio_key: dict[tuple[str, int, int], list[dict[str, object]]] = {}
        for record in raw_rule_records:
            key = (str(record.get("id")), int(record.get("game", -1)),
                   int(record.get("item", -1)))
            raw_by_portfolio_key.setdefault(key, []).append(record)
        portfolio_rule_sizes = {
            str(row.get("id")): int(row.get("uniqueItems", 0))
            for row in portfolio.get("rules", [])
        }
        replay_checks = [_replay_checks(game) for game in game_payloads]
        quality_by_game = {
            int(row["game"]): row
            for row in overview.get("intelligence", {}).get("quality", [])
        }
        index_by_game: dict[int, list[dict[str, object]]] = {}
        for row in overview.get("itemIndex", []):
            index_by_game.setdefault(int(row["game"]), []).append(row)
        document_by_game = {
            int(row["id"]): bool(row.get("documentsAvailable"))
            for row in overview.get("games", [])
        }
        reviewer_cells = reviewer.get("cells", [])
        reviewer_summary = reviewer.get("summary", {})
        reviewer_matrix = reviewer_summary.get("matrix", {})
        reviewer_cell_fields = {
            "game", "item", "opponent", "actualAccepted", "actualCost", "outcome",
            "provenClass", "evidenceKind", "charge", "chargeKind", "tLo", "tHi",
            "valueBucket", "b", "source", "limitAudit", "fairExactEligible",
            "fraudDownshiftEligible", "hiddenFraudEligible",
        }
        market_edge_fields = {
            "issuer", "reviewer", "decisions", "accepted", "acceptRate",
            "issuerIncome", "reviewerCost", "penaltyWedge", "wrongCost",
            "unresolvedCount", "unresolvedCost", "hiddenFraud", "netExchange",
            "acceptFairCount", "acceptFairCost", "rejectFairCount", "rejectFairCost",
            "acceptFraudCount", "acceptFraudCost", "rejectFraudCount", "rejectFraudCost",
        }
        market_summary_fields = {
            "team", "issuedIncome", "reviewerCost", "net", "issuedDecisions",
            "reviewedDecisions", "acceptedByMarket", "reviewerAccepts",
            "marketAcceptRate", "reviewerAcceptRate", "wrongReviewCost",
            "rejectFairCount", "rejectFairCost", "acceptFraudCount", "acceptFraudCost",
            "hiddenFraud", "chargeGroups", "aggressionObservations",
            "medianChargeToFloor", "aggressionCoverage", "officialTotal",
            "scoreReconciliationDelta",
        }
        market_timeline_fields = {
            "team", "game", "issuedIncome", "reviewerCost", "net", "cumulativeNet",
            "issuedDecisions", "acceptedByMarket", "reviewedDecisions", "reviewerAccepts",
            "marketAcceptRate", "reviewerAcceptRate", "officialScore",
            "officialCumulativeScore",
            "scoreReconciliationDelta",
        }
        market_edge_timeline_columns = [
            "game", "issuerIndex", "reviewerIndex", "decisions", "accepted",
            "issuerIncome", "reviewerCost", "penaltyWedge", "wrongCost",
            "unresolvedCount", "unresolvedCost", "hiddenFraud",
            "acceptFairCount", "acceptFairCost", "rejectFairCount", "rejectFairCost",
            "acceptFraudCount", "acceptFraudCost", "rejectFraudCount", "rejectFraudCost",
        ]
        market_edges = market.get("edges", [])
        market_summaries = market.get("summaries", [])
        market_timeline = market.get("timeline", [])
        market_teams = market.get("teams", [])
        market_edge_cube = market.get("edgeTimeline", {})
        market_edge_frame_rows = [
            dict(zip(market_edge_timeline_columns, row, strict=True))
            for row in market_edge_cube.get("rows", [])
            if isinstance(row, list) and len(row) == len(market_edge_timeline_columns)
        ]
        market_team_by_index = {index: team for index, team in enumerate(market_teams)}
        market_frame_edge_rollups: dict[tuple[object, object], dict[str, float]] = {}
        market_frame_team_rollups: dict[tuple[object, object], dict[str, float]] = {}
        for row in market_edge_frame_rows:
            row["issuer"] = market_team_by_index.get(row.get("issuerIndex"))
            row["reviewer"] = market_team_by_index.get(row.get("reviewerIndex"))
            edge_rollup = market_frame_edge_rollups.setdefault(
                (row["issuer"], row["reviewer"]),
                {"decisions": 0.0, "issuerIncome": 0.0, "reviewerCost": 0.0},
            )
            for field in edge_rollup:
                edge_rollup[field] += float(row.get(field, 0))
            issuer_rollup = market_frame_team_rollups.setdefault(
                (row.get("game"), row["issuer"]),
                {"issuedIncome": 0.0, "reviewerCost": 0.0},
            )
            reviewer_rollup = market_frame_team_rollups.setdefault(
                (row.get("game"), row["reviewer"]),
                {"issuedIncome": 0.0, "reviewerCost": 0.0},
            )
            issuer_rollup["issuedIncome"] += float(row.get("issuerIncome", 0))
            reviewer_rollup["reviewerCost"] += float(row.get("reviewerCost", 0))
        operations = overview.get("live", {}).get("operations", {})
        operation_rows = operations.get("games", [])
        operation_envelope = operations.get("stageEnvelope", [])
        operation_summary = operations.get("summary", {})
        operation_game_fields = {
            "game", "played", "recorded", "coreCoverage", "eventCount",
            "observedStages", "stageTimesMs", "firstSendMs", "tier1SendMs",
            "tier2SendMs", "tier1TargetStatus", "tier2DeadlineStatus",
            "submissionCalls", "successfulCalls", "failedCalls", "alerts",
            "roundPlayedObserved", "lastStage", "lastStageAt", "lastElapsedMs",
            "observedSpanMs",
        }
        operation_envelope_fields = {"stage", "observations", "p10Ms", "p50Ms", "p90Ms"}
        operation_summary_fields = {
            "playedGames", "pipelineGames", "recordedPlayedGames", "missingPlayedGames",
            "recordedCoverage", "completeCoreGames", "meanCoreCoverage",
            "tier1Observed", "tier1AtOrUnderTarget", "tier1TargetRate",
            "tier1P50Ms", "tier1P95Ms", "tier2Observed",
            "tier2AtOrUnderDeadline", "tier2DeadlineRate", "tier2P50Ms",
            "tier2P95Ms", "failedSubmissionCalls", "alerts",
        }
        invariants = {
            "teamCount17": overview["race"]["teamCount"] == 17,
            "raceSeriesAligned": all(len(row["scores"]) == game_count and
                                     len(row["rounds"]) == game_count
                                     for row in overview["race"]["series"]),
            "scoresReconciled": reconciled,
            "itemIndexCoversThresholds": len(overview.get("itemIndex", [])) >=
                                         overview["thresholdCount"],
            "riskLatticeAccountsForLabelledItems":
                overview.get("intelligence", {}).get("valueRisk", {}).get("labelledItems") ==
                sum(row.get("tLo") is not None for row in overview.get("itemIndex", [])),
            "opponentCount16": len(overview.get("trends", {}).get("opponents", [])) == 16,
            "opponentReviewCellsReconcile": all(
                sum(cell.get("count", 0) for cell in row.get("reviewCells", {}).values()) ==
                row.get("reviewDecisions", 0)
                for row in overview.get("trends", {}).get("opponents", [])
            ),
            "robustRaceFieldsPresent": all(
                all(isinstance(row.get(field), (int, float)) for field in (
                    "medianPaceTotal", "winsorizedTotal", "withoutTop3Positive",
                    "withoutWorst3Negative", "positiveTop3Share",
                ))
                for row in overview["race"]["series"]
            ),
            "ruleFiringsAccounted": sum(
                row.get("firings", 0)
                for row in overview.get("intelligence", {}).get("rules", {}).get("rules", [])
            ) == overview.get("intelligence", {}).get("rules", {}).get("firings", 0),
            "rulePairsAccounted": sum(
                row.get("paired", 0)
                for row in overview.get("intelligence", {}).get("rules", {}).get("rules", [])
            ) == len(overview.get("intelligence", {}).get("rules", {}).get("records", [])),
            "ruleFixedDenominatorsMatch": all(
                row.get("before", {}).get("bestPossible") ==
                row.get("after", {}).get("bestPossible")
                for row in overview.get("intelligence", {}).get("rules", {}).get("rules", [])
            ),
            "portfolioDedupeReconciles": all(
                row.get("pairedFirings") == row.get("uniqueItems") + row.get("duplicateFirings")
                for row in overview.get("intelligence", {}).get("rules", {}).get(
                    "portfolios", {}
                ).get("rules", [])
            ),
            "portfolioRecordsAccounted": sum(
                row.get("uniqueItems", 0)
                for row in overview.get("intelligence", {}).get("rules", {}).get(
                    "portfolios", {}
                ).get("rules", [])
            ) == len(overview.get("intelligence", {}).get("rules", {}).get(
                "portfolios", {}
            ).get("records", [])),
            "portfolioFixedDenominatorsMatch": all(
                row.get("before", {}).get("bestPossible") ==
                row.get("after", {}).get("bestPossible")
                for row in overview.get("intelligence", {}).get("rules", {}).get(
                    "portfolios", {}
                ).get("rules", [])
            ),
            "portfolioKeysUnique": len({
                (row.get("id"), row.get("game"), row.get("item"))
                for row in portfolio_records
            }) == len(portfolio_records),
            "portfolioLatestSequenceRetained": all(
                (raw_rows := raw_by_portfolio_key.get(
                    (str(row.get("id")), int(row.get("game", -1)),
                     int(row.get("item", -1))), []
                )) and
                int(row.get("seq") or 0) == max(int(raw.get("seq") or 0)
                                                for raw in raw_rows)
                for row in portfolio_records
            ),
            "portfolioRepeatMetadataReconciles": all(
                (raw_rows := raw_by_portfolio_key.get(
                    (str(row.get("id")), int(row.get("game", -1)),
                     int(row.get("item", -1))), []
                )) and
                row.get("repeatFirings") == len(raw_rows) and
                row.get("candidateStable") == (len({
                    tuple(raw.get("after") or []) for raw in raw_rows
                }) == 1)
                for row in portfolio_records
            ),
            "portfolioOverlapsBounded": all(
                int(row.get("items", 0)) <= min(
                    portfolio_rule_sizes.get(str(row.get("left")), 0),
                    portfolio_rule_sizes.get(str(row.get("right")), 0),
                ) and
                int(row.get("directionComparable", 0)) <= int(row.get("items", 0)) and
                int(row.get("directionAgreement", 0)) +
                int(row.get("directionOpposition", 0)) ==
                int(row.get("directionComparable", 0))
                for row in portfolio.get("overlaps", [])
            ),
            "itemFlowsReconcile": all(
                abs(sum(item.get("economics", {}).get("issuerIncome", 0)
                        for item in game.get("items", [])) - game["economics"]["income"]) <= 0.51 and
                abs(sum(item.get("economics", {}).get("reviewerCost", 0)
                        for item in game.get("items", [])) - game["economics"]["cost"]) <= 0.51
                for game in game_payloads
            ),
            "flightCoreDenominatorsStable": all(
                game.get("flight", {}).get("coreStageDenominator") == len(PIPELINE_CORE)
                for game in game_payloads
            ),
            "flightPayloadExcludesSensitiveFields": all(
                not ({"detail", "msg", "note", "case", "rules", "trace"} & {
                    key for row in (
                        game.get("flight", {}).get("milestones", []) +
                        game.get("flight", {}).get("activities", [])
                    ) for key in row
                })
                for game in game_payloads
            ),
            "replayCountsReconcile": all(row["counts"] for row in replay_checks),
            "replaySequenceOrdered": all(row["sequence"] for row in replay_checks),
            "replayItemsKnown": all(row["knownItems"] for row in replay_checks),
            "replayPayloadAllowListed": all(row["allowListed"] for row in replay_checks),
            "replayLatestStateReconciles": all(row["latestState"]
                                               for row in replay_checks),
            "evidenceAtlasFieldsPresent": all(
                {"replayCount", "documentsAvailable", "ruleCount", "shadowCount",
                 "field"} <= set(row)
                for row in overview.get("itemIndex", [])
            ),
            "evidenceQualityReconciles": all(
                (quality := quality_by_game.get(game)) is not None and
                quality.get("items") == len(items) and
                quality.get("beliefs") == sum(row.get("median") is not None
                                               for row in items) and
                quality.get("decisions") == sum(row.get("a") is not None
                                                 for row in items) and
                quality.get("ruleTraces") == sum(int(row.get("ruleCount", 0)) > 0
                                                  for row in items) and
                quality.get("replayedItems") == sum(int(row.get("replayCount", 0)) > 0
                                                     for row in items) and
                quality.get("documentsAvailable") == document_by_game.get(game)
                for game, items in index_by_game.items()
            ),
            "evidenceDocumentsConsistent": all(
                bool(row.get("documentsAvailable")) == document_by_game.get(int(row["game"]))
                for row in overview.get("itemIndex", [])
            ),
            "operationsSchemaCurrent": operations.get("schemaVersion") == 1 and
                operations.get("stages") == list(PIPELINE_CORE),
            "operationsPayloadAllowListed": all(
                set(row) == operation_game_fields and
                set(row.get("stageTimesMs", {})) == set(PIPELINE_CORE) and
                set(row.get("observedStages", [])) <= set(PIPELINE_CORE)
                for row in operation_rows
            ) and all(set(row) == operation_envelope_fields for row in operation_envelope) and
                set(operation_summary) == operation_summary_fields,
            "operationsGamesCoverPlayed": len({row.get("game") for row in operation_rows}) ==
                len(operation_rows) and set(overview["race"]["gameIds"]) <= {
                    row.get("game") for row in operation_rows
                },
            "operationsCoverageReconciles": (
                recorded_played := [row for row in operation_rows
                                    if row.get("recorded") and row.get("played")]
            ) is not None and
                operation_summary.get("playedGames") == game_count and
                operation_summary.get("recordedPlayedGames") == len(recorded_played) and
                operation_summary.get("missingPlayedGames") == game_count - len(recorded_played) and
                operation_summary.get("pipelineGames") == sum(
                    bool(row.get("recorded")) for row in operation_rows
                ),
            "operationsDeadlineDenominatorsReconcile": (
                tier_one_observed := [row for row in operation_rows
                                      if row.get("tier1SendMs") is not None]
            ) is not None and (
                tier_two_observed := [row for row in operation_rows
                                      if row.get("tier2SendMs") is not None]
            ) is not None and
                operation_summary.get("tier1Observed") == len(tier_one_observed) and
                operation_summary.get("tier1AtOrUnderTarget") == sum(
                    float(row["tier1SendMs"]) <= 2_000 for row in tier_one_observed
                ) and operation_summary.get("tier2Observed") == len(tier_two_observed) and
                operation_summary.get("tier2AtOrUnderDeadline") == sum(
                    float(row["tier2SendMs"]) <= 52_000 for row in tier_two_observed
                ),
            "operationsStageEnvelopeReconciles": len(operation_envelope) == len(PIPELINE_CORE) and
                all(
                    row.get("observations") == sum(
                        game.get("stageTimesMs", {}).get(row.get("stage")) is not None
                        for game in operation_rows
                    )
                    for row in operation_envelope
                ),
            "operationsFreshnessIsExplicit": (
                operations.get("lagPlayedGames", 0) == 0 or
                operations.get("telemetryStatus") == "stale-played-rounds"
            ) and (
                dependency := health.get("items", {}).get("operationsTelemetry", {})
            ) is not None and dependency.get("critical") is False and
                dependency.get("mode") == operations.get("telemetryStatus") and
                dependency.get("ok") == (operations.get("telemetryStatus") == "current"),
            "operationsPayloadExcludesClaimContent": not any(
                token in json.dumps(operations).casefold()
                for token in ("description", "policy", "damage", "photo", "fair_charges")
            ),
            "reviewerCellsAccounted": reviewer_summary.get("cells") == len(reviewer_cells) and
                reviewer_summary.get("provenCells", 0) +
                reviewer_summary.get("unprovenCells", 0) == len(reviewer_cells),
            "reviewerMatrixCountsReconcile": sum(
                int(row.get("count", 0)) for row in reviewer_matrix.values()
            ) + int(reviewer_summary.get("unproven", {}).get("count", 0)) ==
                len(reviewer_cells),
            "reviewerCostsReconcile": abs(
                sum(float(row.get("actualCost", 0)) for row in reviewer_cells) -
                sum(float(game.get("economics", {}).get("cost", 0))
                    for game in game_payloads)
            ) <= 0.51,
            "reviewerLimitAuditsPartition": sum(
                int(reviewer_summary.get(key, 0)) for key in (
                    "limitConsistent", "limitInconsistent", "limitIndeterminate", "limitMissing"
                )
            ) == len(reviewer_cells),
            "reviewerPayloadAllowListed": all(
                set(row) == reviewer_cell_fields for row in reviewer_cells
            ),
            "reviewerEligibilityConservative": all(
                (not row.get("fairExactEligible") or (
                    row.get("provenClass") == "fair" and row.get("chargeKind") == "exact" and
                    row.get("limitAudit") == "consistent" and row.get("b") is not None
                )) and
                (not row.get("fraudDownshiftEligible") or (
                    row.get("provenClass") == "fraud" and
                    row.get("chargeKind") == "lower_bound" and
                    row.get("actualAccepted") is True and row.get("charge") is not None and
                    row.get("b") is not None and float(row["b"]) >= float(row["charge"])
                )) and
                (not row.get("hiddenFraudEligible") or (
                    row.get("provenClass") == "fraud" and row.get("chargeKind") == "hidden" and
                    row.get("actualAccepted") is False and row.get("b") is not None and
                    row.get("tLo") is not None
                ))
                for row in reviewer_cells
            ),
            "marketTeamCount17": len(market_teams) == 17 and
                set(market_teams) == {row.get("team") for row in overview["race"]["series"]},
            "marketSchemaCurrent": market.get("schemaVersion") == 2,
            "marketDirectedEdgesComplete": len(market_edges) == 17 * 16 and
                len({(row.get("issuer"), row.get("reviewer")) for row in market_edges}) ==
                len(market_edges),
            "marketPayloadAllowListed": all(
                set(row) == market_edge_fields for row in market_edges
            ) and all(set(row) == market_summary_fields for row in market_summaries) and all(
                set(row) == market_timeline_fields for row in market_timeline
            ),
            "marketDecisionPartitionsReconcile": all(
                int(row.get("decisions", 0)) ==
                int(row.get("acceptFairCount", 0)) +
                int(row.get("rejectFairCount", 0)) +
                int(row.get("acceptFraudCount", 0)) +
                int(row.get("rejectFraudCount", 0)) +
                int(row.get("unresolvedCount", 0)) and
                0 <= int(row.get("accepted", 0)) <= int(row.get("decisions", 0))
                for row in market_edges
            ),
            "marketEdgeTimelineContract": (
                market_edge_cube.get("encoding") == "dense-array-v1" and
                market_edge_cube.get("columns") == market_edge_timeline_columns and
                len(market_edge_frame_rows) == 17 * 16 * game_count and
                len(market_edge_frame_rows) == len(market_edge_cube.get("rows", [])) and
                len({
                    (row.get("game"), row.get("issuerIndex"), row.get("reviewerIndex"))
                    for row in market_edge_frame_rows
                }) == len(market_edge_frame_rows) and
                all(
                    row.get("game") in overview["race"]["gameIds"] and
                    row.get("issuer") in market_teams and
                    row.get("reviewer") in market_teams and
                    row.get("issuer") != row.get("reviewer")
                    for row in market_edge_frame_rows
                )
            ),
            "marketEdgeTimelinePartitionsReconcile": all(
                int(row.get("decisions", 0)) ==
                int(row.get("acceptFairCount", 0)) +
                int(row.get("rejectFairCount", 0)) +
                int(row.get("acceptFraudCount", 0)) +
                int(row.get("rejectFraudCount", 0)) +
                int(row.get("unresolvedCount", 0)) and
                0 <= int(row.get("accepted", 0)) <= int(row.get("decisions", 0))
                for row in market_edge_frame_rows
            ),
            "marketEdgeTimelineSumsReconcile": all(
                (rollup := market_frame_edge_rollups.get(
                    (edge.get("issuer"), edge.get("reviewer")), {}
                )) and
                int(rollup.get("decisions", -1)) == int(edge.get("decisions", 0)) and
                abs(float(rollup.get("issuerIncome", 0)) -
                    float(edge.get("issuerIncome", 0))) <= 0.011 and
                abs(float(rollup.get("reviewerCost", 0)) -
                    float(edge.get("reviewerCost", 0))) <= 0.011
                for edge in market_edges
            ),
            "marketDecisionCountsReconcile": sum(
                int(row.get("decisions", 0)) for row in market_edges
            ) == sum(int(row.get("issuedDecisions", 0)) for row in market_summaries) == sum(
                int(row.get("reviewedDecisions", 0)) for row in market_summaries
            ),
            "marketMoneyReconciles": all(
                abs(sum(float(edge.get("issuerIncome", 0)) for edge in market_edges
                        if edge.get("issuer") == row.get("team")) -
                    float(row.get("issuedIncome", 0))) <= 0.51 and
                abs(sum(float(edge.get("reviewerCost", 0)) for edge in market_edges
                        if edge.get("reviewer") == row.get("team")) -
                    float(row.get("reviewerCost", 0))) <= 0.51
                for row in market_summaries
            ),
            "marketScoresReconcile": all(
                row.get("scoreReconciliationDelta") is not None and
                abs(float(row.get("scoreReconciliationDelta", 1))) <= 0.011
                for row in market_summaries
            ) and all(
                row.get("scoreReconciliationDelta") is not None and
                abs(float(row.get("scoreReconciliationDelta", 1))) <= 0.011
                for row in market_timeline
            ),
            "marketTimelineReconciles": len(market_timeline) == len(market_teams) * game_count and
                all(
                    abs(sum(float(point.get("issuedIncome", 0)) for point in market_timeline
                            if point.get("team") == row.get("team")) -
                        float(row.get("issuedIncome", 0))) <= 0.51 and
                    abs(sum(float(point.get("reviewerCost", 0)) for point in market_timeline
                            if point.get("team") == row.get("team")) -
                        float(row.get("reviewerCost", 0))) <= 0.51
                    for row in market_summaries
                ) and all(
                    (points := [point for point in market_timeline
                                if point.get("team") == row.get("team")]) and
                    points[-1].get("officialCumulativeScore") == row.get("officialTotal")
                    for row in market_summaries
                ),
            "marketEdgeFramesReconcileTeamTimeline": all(
                (rollup := market_frame_team_rollups.get(
                    (point.get("game"), point.get("team")), {}
                )) and
                abs(float(rollup.get("issuedIncome", 0)) -
                    float(point.get("issuedIncome", 0))) <= 0.011 and
                abs(float(rollup.get("reviewerCost", 0)) -
                    float(point.get("reviewerCost", 0))) <= 0.011
                for point in market_timeline
            ),
        }
        result = {
            "ok": bool(health.get("ready")) and all(invariants.values()),
            "degraded": bool(health.get("degraded")),
            "teams": overview["race"]["teamCount"],
            "playedGames": game_count,
            "thresholds": overview["thresholdCount"],
            "indexedItems": len(overview.get("itemIndex", [])),
            "reviewerCells": len(reviewer_cells),
            "marketEdges": len(market_edges),
            "marketEdgeFrames": len(market_edge_frame_rows),
            "operationsStatus": operations.get("telemetryStatus"),
            "operationsRecordedPlayedGames": operation_summary.get("recordedPlayedGames"),
            "schemaVersion": overview.get("schemaVersion"),
            "readOnlyDatabase": health.get("items", {}).get("database", {}).get("mode") == "read-only",
            "invariants": invariants,
        }
        print(json.dumps(result, separators=(",", ":")))
        return 0 if result["ok"] else 1
    cases = CaseService()
    try:
        server = ObservatoryServer((args.host, args.port), Handler, store, cases)
    except OSError as exc:
        print(f"could not bind {args.host}:{args.port}: {exc}", file=sys.stderr)
        return 1
    print(f"Oasis observatory listening on http://{args.host}:{args.port}", file=sys.stderr)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        # User-initiated foreground shutdown only; the app never signals another process.
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
