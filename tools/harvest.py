#!/usr/bin/env python3
"""Build the gitignored valuation dataset from completed tournament games.

This program is deliberately read-only with respect to tournament state.  Its
network surface consists of public leaderboard GETs and authenticated key GETs;
there is no submission client in this module.  Every expensive result is cached
under ``data/harvest`` so an interrupted run resumes without re-fetching it.

Real descriptions, policy text, and decrypted files never leave ``data/``.
Console output contains counts and error classes only, never claim contents or
decryption keys.

    PYTHONPATH=. .venv/bin/python tools/harvest.py
    PYTHONPATH=. .venv/bin/python tools/harvest.py --offline
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import shutil
import sqlite3
import stat
import tempfile
import time
import zipfile
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import requests

from c2f.estimate.pricebook import lookup, match_rate, unit_class
from c2f.core.models import Case
from c2f.ingest.decrypt import extract
from c2f.ingest.parse import build_case
from c2f.scheduler import find_archive


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ARCHIVES = ROOT / "public-cases-ehl" / "cases"
DEFAULT_DATA = ROOT / "data" / "harvest"
DEFAULT_DB = ROOT / "data" / "c2f.sqlite"
LEADERBOARD_BASE = "https://c2f.public.quantco.cloud/leaderboard/api"
TEAM_BASE = "https://c2f.public.quantco.cloud"
SCHEMA_VERSION = 1
HTTP_ATTEMPTS = 3
MAX_PAGES = 100
UNPARSED_DESCRIPTION = "(row not parsed)"

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY,
    start_time TEXT,
    status TEXT,
    seen_at REAL
);
CREATE TABLE IF NOT EXISTS scores (
    game_id INTEGER,
    team TEXT,
    score REAL,
    PRIMARY KEY (game_id, team)
);
CREATE TABLE IF NOT EXISTS transactions (
    game_id INTEGER,
    issuer TEXT,
    reviewer TEXT,
    line_item INTEGER,
    accepted INTEGER,
    amount REAL,
    PRIMARY KEY (game_id, issuer, reviewer, line_item)
);
CREATE INDEX IF NOT EXISTS ix_tx_issuer ON transactions(issuer, game_id);
CREATE INDEX IF NOT EXISTS ix_tx_reviewer ON transactions(reviewer, game_id);
CREATE TABLE IF NOT EXISTS harvested (
    game_id INTEGER,
    team TEXT,
    rows INTEGER,
    fetched_at REAL,
    PRIMARY KEY (game_id, team)
);
"""


class HarvestError(RuntimeError):
    """A contextual, user-actionable harvest failure."""


class EvidenceError(HarvestError):
    """Transaction evidence contradicts the payoff model or is malformed."""


@dataclass(frozen=True)
class ThresholdEvidence:
    """Identified interval for one threshold, plus audit counters.

    ``lower`` is inclusive and ``upper`` is exclusive.  ``upper=None`` means
    right-censored.  A fraud label can lack a numeric upper bound when every
    reviewer rejected: the feed then reports only zero payments and does not
    expose the issuer's submitted charge.
    """

    lower: float
    upper: float | None
    fair_issuers: int
    fraud_issuers: int
    fraud_issuers_with_price: int
    fraud_issuers_without_price: int
    unlabeled_issuers: int


class ReadOnlyHttp:
    """Small GET-only JSON client with bounded, jittered retries."""

    def __init__(self, timeout: tuple[float, float] = (2.0, 8.0)) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        last = "request not attempted"
        for attempt in range(HTTP_ATTEMPTS):
            try:
                response = self.session.get(
                    url, params=params, headers=headers, timeout=self.timeout
                )
            except requests.RequestException as exc:
                last = f"{type(exc).__name__}: {exc}"
            else:
                if response.ok:
                    try:
                        body = response.json()
                    except ValueError as exc:
                        raise HarvestError(
                            f"GET returned invalid JSON: {type(exc).__name__}"
                        ) from exc
                    if not isinstance(body, dict):
                        raise HarvestError(
                            f"GET returned {type(body).__name__}, expected object"
                        )
                    return body
                last = f"HTTP {response.status_code}: {response.text[:160]}"
                if response.status_code < 500 and response.status_code != 429:
                    raise HarvestError(last)

            if attempt + 1 < HTTP_ATTEMPTS:
                # GET is idempotent.  Bound retries so a dependency outage cannot
                # turn the harvester into a retry storm.
                time.sleep(0.25 * (2**attempt) + random.uniform(0.0, 0.15))
        raise HarvestError(f"GET failed after {HTTP_ATTEMPTS} attempts ({last})")

    def close(self) -> None:
        self.session.close()


def _atomic_write(path: Path, body: str, *, private: bool = False) -> None:
    """Durably replace one cache file without exposing a partial result."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(raw_tmp)
    try:
        if private:
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        tmp.replace(path)
    except BaseException:
        try:
            tmp.unlink(missing_ok=True)
        finally:
            raise


def atomic_json(path: Path, value: Any, *, private: bool = False) -> None:
    _atomic_write(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        private=private,
    )


def atomic_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    body = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )
    _atomic_write(path, body)


def connect(path: Path = DEFAULT_DB) -> sqlite3.Connection:
    """Open the transaction cache used by ``tools/thresholds.py``.

    This compatibility surface predates the line-item dataset.  Keeping the raw
    public feed here means analysis tools can re-derive labels independently
    instead of trusting the derived JSONL.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(SQLITE_SCHEMA)
    return connection


def write_transactions_db(
    path: Path,
    game_id: int,
    rows: list[dict[str, Any]],
    teams: list[str],
) -> None:
    connection = connect(path)
    try:
        now = time.time()
        records = [
            (
                game_id,
                row["issuer"],
                row["reviewer"],
                row["line_item_index"],
                1 if row["accepted"] else 0,
                row["amount"],
            )
            for row in rows
        ]
        with connection:
            connection.executemany(
                "INSERT OR REPLACE INTO transactions"
                "(game_id,issuer,reviewer,line_item,accepted,amount) VALUES(?,?,?,?,?,?)",
                records,
            )
            for team in teams:
                visible = sum(
                    team in (row["issuer"], row["reviewer"])
                    for row in rows
                )
                connection.execute(
                    "INSERT OR REPLACE INTO harvested(game_id,team,rows,fetched_at) "
                    "VALUES(?,?,?,?)",
                    (game_id, team, visible, now),
                )
    finally:
        connection.close()


def stats(connection: sqlite3.Connection) -> None:
    """Print aggregate-only cache statistics; never print claim fields."""

    def scalar(sql: str, *args: Any) -> int:
        return int(connection.execute(sql, args).fetchone()[0])

    known = scalar("SELECT COUNT(*) FROM games")
    completed = scalar("SELECT COUNT(*) FROM games WHERE status = ?", "completed")
    transactions = scalar("SELECT COUNT(*) FROM transactions")
    transaction_games = scalar("SELECT COUNT(DISTINCT game_id) FROM transactions")
    scores = scalar("SELECT COUNT(*) FROM scores")
    print(f"sqlite games: {known} known, {completed} completed")
    print(f"sqlite scores: {scores} cells")
    print(f"sqlite transactions: {transactions} rows over {transaction_games} game(s)")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_games(raw: str | None) -> set[int] | None:
    if not raw:
        return None
    out: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo_raw, hi_raw = part.split("-", 1)
            lo, hi = int(lo_raw), int(hi_raw)
            if lo > hi:
                raise argparse.ArgumentTypeError(f"invalid game range {part!r}")
            out.update(range(lo, hi + 1))
        else:
            out.add(int(part))
    if any(game < 1 for game in out):
        raise argparse.ArgumentTypeError("game ids must be positive")
    return out


def _validate_member(name: str, mode: int) -> None:
    """Reject archive members capable of escaping the extraction directory."""

    if not name or "\x00" in name:
        raise HarvestError("archive contains an empty or NUL-containing path")
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or (path.parts and ":" in path.parts[0]):
        raise HarvestError("archive contains an unsafe member path")
    if stat.S_IFMT(mode) == stat.S_IFLNK:
        raise HarvestError("archive contains a symbolic link")


def validate_archive_members(archive: Path) -> None:
    try:
        with zipfile.ZipFile(archive) as zipped:
            infos = zipped.infolist()
    except (OSError, zipfile.BadZipFile) as exc:
        raise HarvestError(f"invalid archive: {type(exc).__name__}: {exc}") from exc
    if not infos:
        raise HarvestError("archive contains no members")
    for info in infos:
        _validate_member(info.filename, info.external_attr >> 16)


def ensure_extracted(archive: Path, password: str, destination: Path) -> list[Path]:
    """Extract once into a validated, atomically published directory."""

    archive_hash = sha256_file(archive)
    marker = destination / ".harvest-complete.json"
    if marker.is_file():
        try:
            recorded = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HarvestError(
                f"invalid extraction marker for {destination.name}: {type(exc).__name__}"
            ) from exc
        if recorded.get("archive_sha256") != archive_hash:
            raise HarvestError(
                f"archive changed after extraction for {destination.name}; "
                "move the old gitignored directory aside before retrying"
            )
        files = sorted(
            path for path in destination.rglob("*")
            if path.is_file() and path != marker
        )
        if not files:
            raise HarvestError(f"completed extraction {destination.name} has no files")
        return files
    if destination.exists():
        raise HarvestError(
            f"incomplete extraction directory exists: {destination}; "
            "move it aside before retrying"
        )

    validate_archive_members(archive)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    try:
        files = extract(archive, password, temp)
        if not files:
            raise HarvestError("decryption produced no files")
        relative = sorted(str(path.relative_to(temp)) for path in files)
        atomic_json(
            temp / marker.name,
            {
                "schema_version": SCHEMA_VERSION,
                "archive_sha256": archive_hash,
                "files": relative,
            },
        )
        temp.rename(destination)
    except BaseException:
        # ``temp`` is created by us under the exact destination parent.  Keep the
        # guard explicit because recursive deletion must never take a broad path.
        if temp.exists() and temp.parent.resolve() == destination.parent.resolve():
            shutil.rmtree(temp)
        raise
    return sorted(
        path for path in destination.rglob("*")
        if path.is_file() and path.name != marker.name
    )


def _normalize_transaction(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise EvidenceError(f"transaction is {type(row).__name__}, expected object")
    required = {"issuer", "reviewer", "line_item_index", "accepted", "amount"}
    missing = sorted(required - row.keys())
    if missing:
        raise EvidenceError(f"transaction missing fields {missing}")
    issuer, reviewer = str(row["issuer"]).strip(), str(row["reviewer"]).strip()
    if not issuer or not reviewer or issuer == reviewer:
        raise EvidenceError("transaction has invalid issuer/reviewer")
    if not isinstance(row["accepted"], bool):
        raise EvidenceError("transaction accepted field is not boolean")
    try:
        index = int(row["line_item_index"])
        amount = float(row["amount"])
    except (TypeError, ValueError) as exc:
        raise EvidenceError("transaction index/amount is not numeric") from exc
    if index < 1 or not math.isfinite(amount) or amount < 0:
        raise EvidenceError("transaction index/amount is outside its valid domain")
    return {
        "issuer": issuer,
        "reviewer": reviewer,
        "line_item_index": index,
        "accepted": row["accepted"],
        "amount": amount,
    }


def derive_threshold_evidence(rows: list[dict[str, Any]], index: int) -> ThresholdEvidence:
    """Derive the identified threshold interval from a full pairwise matrix.

    Rejected-and-paid identifies a fair issuer charge; rejected-and-unpaid
    identifies a fraudulent issuer charge.  Accepted rows are never labels.
    For fraud, a positive payment from another reviewer is a conservative upper
    bound even if the cap bound: it is ``min(a, c) > t`` whenever positive,
    because ``a > t`` and the game guarantees ``c >= 4t``.
    """

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in rows:
        row = _normalize_transaction(raw)
        if row["line_item_index"] == index:
            grouped[row["issuer"]].append(row)

    lows: list[float] = []
    highs: list[float] = []
    fair = fraud = fraud_priced = fraud_unpriced = unlabeled = 0
    for issuer_rows in grouped.values():
        rejected = [row for row in issuer_rows if not row["accepted"]]
        if not rejected:
            unlabeled += 1
            continue
        paid_states = {row["amount"] > 0 for row in rejected}
        if len(paid_states) != 1:
            raise EvidenceError(
                f"item {index}: one issuer has both paid and unpaid rejections"
            )
        if True in paid_states:
            fair += 1
            rejected_prices = {row["amount"] for row in rejected}
            if len(rejected_prices) != 1:
                raise EvidenceError(
                    f"item {index}: fair rejected payments disagree for one issuer"
                )
            lows.append(next(iter(rejected_prices)))
            continue

        fraud += 1
        positive = [row["amount"] for row in issuer_rows if row["amount"] > 0]
        if positive:
            fraud_priced += 1
            # All accepted payments for an issuer/item should be the same
            # min(a,c).  Disagreement would invalidate the inferred bound.
            if len(set(positive)) != 1:
                raise EvidenceError(
                    f"item {index}: fraud payments disagree for one issuer"
                )
            highs.append(positive[0])
        else:
            fraud_unpriced += 1

    lower = max(lows, default=0.0)
    upper = min(highs) if highs else None
    if upper is not None and upper <= lower:
        raise EvidenceError(
            f"item {index}: contradictory threshold interval [{lower}, {upper})"
        )
    return ThresholdEvidence(
        lower=lower,
        upper=upper,
        fair_issuers=fair,
        fraud_issuers=fraud,
        fraud_issuers_with_price=fraud_priced,
        fraud_issuers_without_price=fraud_unpriced,
        unlabeled_issuers=unlabeled,
    )


def actual_team_score(rows: list[dict[str, Any]], team: str) -> dict[str, float]:
    """Reconstruct one team's income/cost/net from the transaction feed."""

    normalized = [_normalize_transaction(row) for row in rows]
    income = sum(row["amount"] for row in normalized if row["issuer"] == team)
    cost = sum(
        row["amount"] if row["accepted"] else 1.5 * row["amount"]
        for row in normalized
        if row["reviewer"] == team
    )
    return {
        "income": round(income, 2),
        "cost": round(cost, 2),
        "net": round(income - cost, 2),
    }


def reconcile_case_item_count(case: Case, transaction_indices: list[int]) -> Case:
    """Use complete matrix identities to remove only synthetic parser gaps.

    The regex parser deliberately fills every apparent printed-position gap with a
    placeholder. A footer can resemble a final position, and a numbered non-item line
    can create an interior placeholder. The complete transaction matrix is
    authoritative for tournament item identities. It is safe to discard a parser-only
    row only when that row is explicitly synthetic; every real parsed row and every
    transaction index must still match exactly.

    This is an offline-harvest exception to ``LineItem.idx`` normally being contiguous:
    preserving a server-side gap keeps later features aligned with their transaction
    labels. Re-indexing after dropping a placeholder would silently train on the wrong
    line items.
    """

    if (
        not transaction_indices
        or transaction_indices != sorted(set(transaction_indices))
        or transaction_indices[0] < 1
    ):
        raise HarvestError("transaction item indices are invalid")
    parsed = {item.idx: item for item in case.items}
    missing = [index for index in transaction_indices if index not in parsed]
    if missing:
        raise HarvestError(
            f"parsed rows do not cover {len(missing)} transaction item index(es)"
        )
    authoritative = set(transaction_indices)
    excess = [item for item in case.items if item.idx not in authoritative]
    unsafe_excess = [item for item in excess if item.description != UNPARSED_DESCRIPTION]
    if unsafe_excess:
        raise HarvestError(
            f"parsed {len(case.items)} items but transactions identify "
            f"{len(transaction_indices)}; excess includes a non-synthetic row"
        )
    return replace(case, items=tuple(parsed[index] for index in transaction_indices))


class Harvester:
    def __init__(
        self,
        *,
        data_dir: Path,
        archives_dir: Path,
        db_path: Path,
        team: str,
        pause: float,
        offline: bool,
        refresh: bool,
        http: ReadOnlyHttp | None = None,
    ) -> None:
        if not team.strip():
            raise HarvestError("team name must not be blank")
        if not 0 <= pause <= 5:
            raise HarvestError("pause must be between 0 and 5 seconds")
        self.data_dir = data_dir.resolve()
        self.archives_dir = archives_dir.resolve()
        self.db_path = db_path.resolve()
        self.team = team.strip()
        self.pause = pause
        self.offline = offline
        self.refresh = refresh
        self.http = http or ReadOnlyHttp()
        self.schedule_file = self.data_dir / "games.json"
        self.matrix_file = self.data_dir / "matrix.json"
        self.keys_file = self.data_dir / "keys.json"
        self.tx_dir = self.data_dir / "transactions"
        self.case_dir = self.data_dir / "cases"
        self.row_dir = self.data_dir / "rows"

    def close(self) -> None:
        self.http.close()

    def completed_games(self) -> list[int]:
        if self.offline:
            if not self.schedule_file.is_file():
                raise HarvestError("offline mode has no cached games.json")
            try:
                body = json.loads(self.schedule_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise HarvestError(f"invalid cached games.json: {type(exc).__name__}") from exc
        else:
            body = self.http.get_json(
                f"{LEADERBOARD_BASE}/games",
                params={"page": 1, "page_size": 1000},
            )
            atomic_json(self.schedule_file, body)
        items = body.get("items")
        if not isinstance(items, list):
            raise HarvestError("games response has no items list")
        connection = connect(self.db_path)
        try:
            now = time.time()
            records = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                try:
                    records.append(
                        (int(item["id"]), str(item.get("start_time", "")),
                         str(item.get("status", "")), now)
                    )
                except (KeyError, TypeError, ValueError):
                    continue
            with connection:
                connection.executemany(
                    "INSERT INTO games(id,start_time,status,seen_at) VALUES(?,?,?,?) "
                    "ON CONFLICT(id) DO UPDATE SET start_time=excluded.start_time, "
                    "status=excluded.status, seen_at=excluded.seen_at",
                    records,
                )
        finally:
            connection.close()
        self._sync_scores()
        return sorted(
            int(item["id"])
            for item in items
            if isinstance(item, dict) and str(item.get("status", "")).lower() == "completed"
        )

    def _sync_scores(self) -> None:
        if self.offline:
            if not self.matrix_file.is_file():
                return
            try:
                body = json.loads(self.matrix_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise HarvestError(f"invalid cached matrix.json: {type(exc).__name__}") from exc
        else:
            body = self.http.get_json(
                f"{LEADERBOARD_BASE}/matrix",
                params={"page": 1, "page_size": 1000, "game_limit": 100},
            )
            atomic_json(self.matrix_file, body)
        game_ids = body.get("game_ids", [])
        items = body.get("items", [])
        if not isinstance(game_ids, list) or not isinstance(items, list):
            raise HarvestError("matrix response has an invalid shape")
        records: list[tuple[int, str, float]] = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("cells"), list):
                raise HarvestError("matrix team row has an invalid shape")
            team = str(item.get("team_name", "")).strip()
            if not team:
                raise HarvestError("matrix team row has no team_name")
            for game_id, cell in zip(game_ids, item["cells"]):
                if cell is None:
                    continue
                try:
                    score = float(cell)
                    parsed_game = int(game_id)
                except (TypeError, ValueError) as exc:
                    raise HarvestError("matrix score is not numeric") from exc
                if not math.isfinite(score):
                    raise HarvestError("matrix score is not finite")
                records.append((parsed_game, team, score))
        connection = connect(self.db_path)
        try:
            with connection:
                connection.executemany(
                    "INSERT OR REPLACE INTO scores(game_id,team,score) VALUES(?,?,?)",
                    records,
                )
        finally:
            connection.close()

    def _load_keys(self) -> dict[str, str]:
        if not self.keys_file.is_file():
            return {}
        try:
            raw = json.loads(self.keys_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HarvestError(f"invalid key cache: {type(exc).__name__}") from exc
        if not isinstance(raw, dict) or not all(
            isinstance(key, str) and isinstance(value, str) and value
            for key, value in raw.items()
        ):
            raise HarvestError("key cache has an invalid shape")
        return raw

    def key_for(self, game_id: int) -> str:
        keys = self._load_keys()
        cached = keys.get(str(game_id))
        if cached:
            return cached
        if self.offline:
            raise HarvestError(f"offline mode has no cached key for game {game_id}")
        team_key = os.environ.get("TEAM_API_KEY", "")
        if not team_key:
            raise HarvestError("TEAM_API_KEY is not set")
        body = self.http.get_json(
            f"{TEAM_BASE}/api/games/{game_id}/key",
            headers={"X-API-Key": team_key},
        )
        key = body.get("decryption_key")
        if not isinstance(key, str) or not key:
            raise HarvestError(f"key response for game {game_id} has no decryption_key")
        keys[str(game_id)] = key
        atomic_json(self.keys_file, keys, private=True)
        return key

    @staticmethod
    def _team_cache_name(team: str) -> str:
        return hashlib.sha256(team.encode("utf-8")).hexdigest()[:20] + ".json"

    def _transaction_cache(self, game_id: int, team: str) -> Path:
        return self.tx_dir / f"game_{game_id:03d}" / self._team_cache_name(team)

    def transaction_view(self, game_id: int, team: str) -> list[dict[str, Any]]:
        cache = self._transaction_cache(game_id, team)
        if cache.is_file() and not self.refresh:
            try:
                stored = json.loads(cache.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise HarvestError(
                    f"invalid transaction cache for game {game_id}: {type(exc).__name__}"
                ) from exc
            if stored.get("team") != team or not isinstance(stored.get("rows"), list):
                raise HarvestError(f"transaction cache shape mismatch for game {game_id}")
            return [_normalize_transaction(row) for row in stored["rows"]]
        if self.offline:
            raise HarvestError(
                f"offline mode has no transaction cache for game {game_id}, requested team"
            )

        rows: list[dict[str, Any]] = []
        page = 1
        reported_total: int | None = None
        while True:
            body = self.http.get_json(
                f"{LEADERBOARD_BASE}/transactions",
                params={
                    "game_id": game_id,
                    "team": team,
                    "page": page,
                    "page_size": 1000,
                },
            )
            page_rows = body.get("items")
            if not isinstance(page_rows, list):
                raise HarvestError(
                    f"transactions game {game_id} page {page} has no items list"
                )
            rows.extend(_normalize_transaction(row) for row in page_rows)
            try:
                total_pages = int(body.get("total_pages", 1))
                reported_total = int(body.get("total", len(rows)))
            except (TypeError, ValueError) as exc:
                raise HarvestError("transaction pagination metadata is invalid") from exc
            if not 1 <= total_pages <= MAX_PAGES:
                raise HarvestError(f"transaction total_pages={total_pages} is unsafe")
            if page >= total_pages:
                break
            page += 1
        if reported_total is not None and len(rows) != reported_total:
            raise HarvestError(
                f"transactions game {game_id}: fetched {len(rows)}, API reports {reported_total}"
            )
        atomic_json(
            cache,
            {"schema_version": SCHEMA_VERSION, "game_id": game_id, "team": team, "rows": rows},
        )
        return rows

    def all_transactions(self, game_id: int) -> tuple[list[dict[str, Any]], list[str]]:
        first = self.transaction_view(game_id, self.team)
        if not first:
            raise HarvestError(f"game {game_id}: no transactions for configured team")
        teams = sorted(
            {row["issuer"] for row in first} | {row["reviewer"] for row in first}
        )
        if self.team not in teams or len(teams) < 2:
            raise HarvestError(f"game {game_id}: could not discover participating teams")

        union: dict[tuple[str, str, int], dict[str, Any]] = {}
        for team in teams:
            fetched_from_network = (
                team != self.team
                and (self.refresh or not self._transaction_cache(game_id, team).is_file())
                and not self.offline
            )
            view = first if team == self.team else self.transaction_view(game_id, team)
            for row in view:
                key = (row["issuer"], row["reviewer"], row["line_item_index"])
                previous = union.get(key)
                if previous is not None and previous != row:
                    raise EvidenceError(
                        f"game {game_id}: duplicate transaction views disagree"
                    )
                union[key] = row
            if team != teams[-1] and fetched_from_network and self.pause:
                time.sleep(self.pause)

        rows = [union[key] for key in sorted(union)]
        indices = {row["line_item_index"] for row in rows}
        expected = len(indices) * len(teams) * (len(teams) - 1)
        if len(rows) != expected:
            raise HarvestError(
                f"game {game_id}: pairwise matrix incomplete "
                f"({len(rows)}/{expected} rows)"
            )
        return rows, teams

    @staticmethod
    def _image_features(paths: tuple[str, ...]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for raw in paths:
            path = Path(raw)
            feature: dict[str, Any] = {"suffix": path.suffix.lower(), "bytes": path.stat().st_size}
            try:
                from PIL import Image

                with Image.open(path) as image:
                    feature.update({"width": image.width, "height": image.height, "mode": image.mode})
            except (ImportError, OSError):
                feature.update({"width": None, "height": None, "mode": None})
            out.append(feature)
        return out

    def build_game(self, game_id: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        archive = find_archive(self.archives_dir, game_id)
        if archive is None:
            raise HarvestError(f"game {game_id}: archive not found")
        archive = archive.resolve()
        if not archive.is_relative_to(self.archives_dir):
            raise HarvestError(f"game {game_id}: archive resolved outside archive directory")

        key = self.key_for(game_id)
        extracted = ensure_extracted(
            archive, key, self.case_dir / f"case_{game_id:03d}"
        )
        case = build_case(str(game_id), extracted)
        transactions, teams = self.all_transactions(game_id)
        write_transactions_db(self.db_path, game_id, transactions, teams)
        indices = sorted({row["line_item_index"] for row in transactions})
        case = reconcile_case_item_count(case, indices)
        expected_indices = [item.idx for item in case.items]
        if indices != expected_indices:
            raise HarvestError(
                f"game {game_id}: parsed indices {expected_indices} do not match "
                f"transaction indices {indices}"
            )

        image_features = self._image_features(case.image_paths)
        score = actual_team_score(transactions, self.team)
        rows: list[dict[str, Any]] = []
        for item in case.items:
            evidence = derive_threshold_evidence(transactions, item.idx)
            pricebook = lookup(item)
            matched = match_rate(item)
            rows.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "game_id": game_id,
                    "line_item_index": item.idx,
                    "features": {
                        # This is real claim material and is safe only because the
                        # complete dataset lives below gitignored data/.
                        "description": item.description,
                        "quantity": item.qty,
                        "unit": item.unit,
                        "unit_class": unit_class(item.unit),
                        "trade": matched.trade,
                        "damage_description": case.damage_description,
                        "policy_text": case.policy_text,
                        "image_metadata": image_features,
                        "pricebook_median": pricebook.median,
                        "pricebook_sigma": pricebook.sigma,
                        "pricebook_source": pricebook.source,
                    },
                    "label": {
                        "lower": evidence.lower,
                        "lower_inclusive": True,
                        "upper": evidence.upper,
                        "upper_exclusive": True,
                        "fair_issuers": evidence.fair_issuers,
                        "fraud_issuers": evidence.fraud_issuers,
                        "fraud_issuers_with_price": evidence.fraud_issuers_with_price,
                        "fraud_issuers_without_price": evidence.fraud_issuers_without_price,
                        "unlabeled_issuers": evidence.unlabeled_issuers,
                    },
                }
            )

        summary = {
            "schema_version": SCHEMA_VERSION,
            "game_id": game_id,
            "line_items": len(rows),
            "teams": len(teams),
            "transactions": len(transactions),
            "expected_transactions": len(rows) * len(teams) * (len(teams) - 1),
            "matrix_complete": True,
            "finite_intervals": sum(row["label"]["upper"] is not None for row in rows),
            "right_censored_intervals": sum(row["label"]["upper"] is None for row in rows),
            "team_score": score,
        }
        atomic_jsonl(self.row_dir / f"game_{game_id:03d}.jsonl", rows)
        atomic_json(self.row_dir / f"game_{game_id:03d}.summary.json", summary)
        return rows, summary

    def merge_dataset(self, completed: list[int]) -> int:
        rows: list[dict[str, Any]] = []
        missing: list[int] = []
        for game_id in completed:
            path = self.row_dir / f"game_{game_id:03d}.jsonl"
            if not path.is_file():
                missing.append(game_id)
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rows.append(json.loads(line))
        rows.sort(key=lambda row: (row["game_id"], row["line_item_index"]))
        atomic_jsonl(self.data_dir / "line_items.jsonl", rows)
        atomic_json(
            self.data_dir / "dataset.json",
            {
                "schema_version": SCHEMA_VERSION,
                "completed_games": completed,
                "missing_games": missing,
                "rows": len(rows),
            },
        )
        return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harvest")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--archives-dir", type=Path, default=DEFAULT_ARCHIVES)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB,
                        help="raw transaction SQLite cache used by thresholds.py")
    parser.add_argument("--team", default="Oasis")
    parser.add_argument("--games", help="completed game selection, e.g. 1-4 or 1,3")
    parser.add_argument("--pause", type=float, default=0.2, help="seconds between team views")
    parser.add_argument("--offline", action="store_true", help="use caches only; make no requests")
    parser.add_argument("--refresh", action="store_true", help="refresh transaction GET caches")
    # Compatibility with the first SQLite-only harvester.  ``--once`` is now an
    # explicit alias for the default full pass; ``--watch`` repeats that safe,
    # resumable pass as games complete.
    parser.add_argument("--once", action="store_true", help="one full pass, then exit")
    parser.add_argument("--watch", action="store_true", help="repeat full passes")
    parser.add_argument("--stats", action="store_true", help="show SQLite cache counts")
    parser.add_argument("--interval", type=float, default=300.0,
                        help="seconds between --watch passes")
    parser.add_argument("--budget", type=int, default=400,
                        help="deprecated compatibility option; caches bound requests")
    args = parser.parse_args(argv)
    if args.offline and args.refresh:
        parser.error("--offline and --refresh are mutually exclusive")
    if args.offline and args.watch:
        parser.error("--offline and --watch are mutually exclusive")
    if args.interval < 10:
        parser.error("--interval must be at least 10 seconds")
    if args.stats and not (args.once or args.watch or args.games):
        connection = connect(args.db)
        try:
            stats(connection)
        finally:
            connection.close()
        return 0
    try:
        selected = _parse_games(args.games)
    except (ValueError, argparse.ArgumentTypeError) as exc:
        parser.error(str(exc))

    harvester = Harvester(
        data_dir=args.data_dir,
        archives_dir=args.archives_dir,
        db_path=args.db,
        team=args.team,
        pause=args.pause,
        offline=args.offline,
        refresh=args.refresh,
    )
    def run_pass() -> int:
        failures: list[tuple[int, str]] = []
        completed = harvester.completed_games()
        if selected is not None:
            not_completed = sorted(selected - set(completed))
            if not_completed:
                raise HarvestError(f"requested games are not completed: {not_completed}")
            completed = [game for game in completed if game in selected]
        if not completed:
            raise HarvestError("no completed games selected")
        print(f"completed games: {len(completed)}")
        for game_id in completed:
            try:
                rows, summary = harvester.build_game(game_id)
            except Exception as exc:  # noqa: BLE001 -- one game must not kill the sweep
                failures.append((game_id, f"{type(exc).__name__}: {exc}"))
                print(f"game {game_id:>3}: FAILED {type(exc).__name__}: {exc}")
                continue
            print(
                f"game {game_id:>3}: {len(rows):>2} items, "
                f"{summary['transactions']} transactions, "
                f"{summary['finite_intervals']} finite intervals"
            )
        row_count = harvester.merge_dataset(completed)
        print(f"dataset rows: {row_count}")
        print(f"dataset path: {harvester.data_dir / 'line_items.jsonl'}")
        if failures:
            print(f"failed games: {len(failures)}")
            return 1
        return 0

    try:
        if args.watch:
            print(f"watching completed games every {args.interval:.0f}s; ctrl-c to stop")
            while True:
                run_pass()
                time.sleep(args.interval)
        result = run_pass()
        if args.stats:
            connection = connect(args.db)
            try:
                stats(connection)
            finally:
                connection.close()
        return result
    except KeyboardInterrupt:
        print("harvest stopped")
        return 0
    except (HarvestError, OSError, ValueError) as exc:
        print(f"harvest failed: {type(exc).__name__}: {exc}")
        return 1
    finally:
        harvester.close()


if __name__ == "__main__":
    raise SystemExit(main())
