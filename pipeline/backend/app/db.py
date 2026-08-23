"""SQLite store. One file under data/, idempotent upserts, WAL so the API server
can read while sync writes."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id          INTEGER PRIMARY KEY,
    start_time  TEXT NOT NULL,
    status      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scores (            -- matrix cells: official per-game net
    game_id     INTEGER NOT NULL,
    team        TEXT NOT NULL,
    score       REAL,
    PRIMARY KEY (game_id, team)
);
CREATE TABLE IF NOT EXISTS performance (       -- official aggregates, one row per team
    team        TEXT PRIMARY KEY,
    income      REAL, costs REAL, net REAL,
    issued_count INTEGER, issued_accepted INTEGER,
    reviewed_count INTEGER, reviewed_accepted INTEGER,
    reviewed_accepted_right INTEGER, reviewed_accepted_wrong INTEGER,
    reviewed_correct_rejections INTEGER, reviewed_penalties INTEGER
);
CREATE TABLE IF NOT EXISTS transactions (
    game_id     INTEGER NOT NULL,
    issuer      TEXT NOT NULL,
    reviewer    TEXT NOT NULL,
    line_item   INTEGER NOT NULL,
    accepted    INTEGER NOT NULL,
    amount      REAL NOT NULL,
    PRIMARY KEY (game_id, issuer, reviewer, line_item)
);
CREATE TABLE IF NOT EXISTS harvested (         -- (game, team) pairs already fetched
    game_id     INTEGER NOT NULL,
    team        TEXT NOT NULL,
    rows        INTEGER NOT NULL,
    PRIMARY KEY (game_id, team)
);
CREATE TABLE IF NOT EXISTS keys (
    game_id     INTEGER PRIMARY KEY,
    key         TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cases (             -- decrypted case files, extracted state
    game_id     INTEGER PRIMARY KEY,
    dir         TEXT NOT NULL,
    n_files     INTEGER NOT NULL
);

-- Derived layers (rebuilt by bounds.py; DROP+CREATE is fine)
CREATE TABLE IF NOT EXISTS issuer_prices (     -- reconstructed charge a per (game, issuer, item)
    game_id INTEGER, issuer TEXT, line_item INTEGER,
    a REAL,            -- best reconstruction of the charge
    a_source TEXT,     -- penalty | accepted | unknown
    n_accepted INTEGER, n_rejected_paid INTEGER, n_rejected_zero INTEGER,
    PRIMARY KEY (game_id, issuer, line_item)
);
CREATE TABLE IF NOT EXISTS item_bounds (       -- interval-censored t per (game, item)
    game_id INTEGER, line_item INTEGER,
    t_lo REAL,         -- max proven-fair charge  (t >= t_lo)
    t_hi REAL,         -- min proven-fraud charge (t <  t_hi), NULL if none
    n_evidence INTEGER,
    PRIMARY KEY (game_id, line_item)
);
CREATE INDEX IF NOT EXISTS idx_tx_game ON transactions (game_id);
CREATE INDEX IF NOT EXISTS idx_tx_issuer ON transactions (issuer, game_id);
CREATE INDEX IF NOT EXISTS idx_tx_reviewer ON transactions (reviewer, game_id);
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.executescript(SCHEMA)
    return con
