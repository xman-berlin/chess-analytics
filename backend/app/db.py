from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import get_settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    username TEXT NOT NULL,
    time_class TEXT NOT NULL,
    rated INTEGER NOT NULL DEFAULT 1,
    white_username TEXT,
    black_username TEXT,
    white_rating INTEGER,
    black_rating INTEGER,
    result TEXT,
    user_color TEXT,
    user_result TEXT,
    opening_eco TEXT,
    opening_name TEXT,
    end_time INTEGER,
    pgn TEXT NOT NULL,
    synced_at TEXT NOT NULL,
    analyzed INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS analyses (
    game_id TEXT PRIMARY KEY REFERENCES games(id),
    acpl REAL,
    blunders INTEGER NOT NULL DEFAULT 0,
    mistakes INTEGER NOT NULL DEFAULT 0,
    inaccuracies INTEGER NOT NULL DEFAULT 0,
    opening_acpl REAL,
    middlegame_acpl REAL,
    endgame_acpl REAL,
    analyzed_at TEXT NOT NULL,
    engine_depth INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS move_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL REFERENCES games(id),
    ply INTEGER NOT NULL,
    move_san TEXT,
    severity TEXT NOT NULL,
    phase TEXT NOT NULL,
    cpl REAL,
    eval_before REAL,
    eval_after REAL,
    best_move_san TEXT,
    motif TEXT,
    fen_before TEXT
);

CREATE TABLE IF NOT EXISTS training_plans (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    generated_at TEXT NOT NULL,
    window_size INTEGER NOT NULL,
    items_json TEXT NOT NULL,
    insights_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plan_progress (
    item_id TEXT PRIMARY KEY,
    completed INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    game_id TEXT NOT NULL,
    ply INTEGER NOT NULL,
    correct INTEGER NOT NULL,
    attempted_at TEXT NOT NULL,
    PRIMARY KEY (game_id, ply)
);

CREATE TABLE IF NOT EXISTS opening_trained (
    color TEXT NOT NULL,
    name TEXT NOT NULL,
    trained_at TEXT NOT NULL,
    PRIMARY KEY (color, name)
);

CREATE TABLE IF NOT EXISTS training_weeks (
    week_start TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    closed_at TEXT,
    verdict_json TEXT
);

CREATE TABLE IF NOT EXISTS week_items (
    week_start TEXT NOT NULL,
    item_key TEXT NOT NULL,
    kind TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (week_start, item_key)
);

CREATE TABLE IF NOT EXISTS position_mastered (
    game_id TEXT NOT NULL,
    ply INTEGER NOT NULL,
    mastered_at TEXT NOT NULL,
    PRIMARY KEY (game_id, ply)
);

CREATE TABLE IF NOT EXISTS sync_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_sync_at TEXT,
    last_analysis_at TEXT,
    games_synced INTEGER NOT NULL DEFAULT 0,
    games_analyzed INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'idle',
    message TEXT
);

CREATE INDEX IF NOT EXISTS idx_games_end_time ON games(end_time DESC);
CREATE INDEX IF NOT EXISTS idx_games_analyzed ON games(analyzed);
CREATE INDEX IF NOT EXISTS idx_move_issues_game ON move_issues(game_id);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path | None = None) -> None:
        settings = get_settings()
        self.path = path or settings.db_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            conn.execute(
                "INSERT OR IGNORE INTO sync_state (id, status, message) VALUES (1, 'idle', 'Bereit')"
            )


db = Database()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]
