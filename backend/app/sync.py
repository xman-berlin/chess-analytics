from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .chesscom_client import (
    ChessComClient,
    extract_opening,
    game_id_from_url,
    is_coach_game,
    public_game_url,
)
from .config import get_settings
from .db import db


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _user_color(game: dict[str, Any], username: str) -> str | None:
    uname = username.lower()
    white = (game.get("white") or {}).get("username", "").lower()
    black = (game.get("black") or {}).get("username", "").lower()
    if white == uname:
        return "white"
    if black == uname:
        return "black"
    return None


def _user_result(game: dict[str, Any], color: str | None) -> str | None:
    if not color:
        return None
    side = game.get(color) or {}
    return side.get("result")


def _normalize_result(user_result: str | None) -> str | None:
    if not user_result:
        return None
    wins = {"win"}
    draws = {"agreed", "repetition", "stalemate", "insufficient", "50move", "timevsinsufficient"}
    losses = {"checkmated", "timeout", "resigned", "abandoned", "lose"}
    if user_result in wins:
        return "win"
    if user_result in draws:
        return "draw"
    if user_result in losses:
        return "loss"
    return user_result


def purge_coach_games() -> int:
    with db.connect() as conn:
        ids = [
            row["id"]
            for row in conn.execute(
                """
                SELECT id FROM games
                WHERE pgn LIKE '%[Event "Play vs Coach"]%'
                   OR white_username LIKE 'Coach-%'
                   OR black_username LIKE 'Coach-%'
                """
            ).fetchall()
        ]
        if not ids:
            return 0
        marks = ",".join("?" * len(ids))
        for table in ("move_issues", "analyses", "quiz_attempts"):
            conn.execute(f"DELETE FROM {table} WHERE game_id IN ({marks})", ids)
        conn.execute(f"DELETE FROM games WHERE id IN ({marks})", ids)
    return len(ids)


def sync_games(force_full: bool = False) -> dict[str, Any]:
    settings = get_settings()
    client = ChessComClient(settings.chess_username)
    allowed = set(settings.time_class_list)
    # Always re-scan newest months for new games; full history only with force_full
    recent_months = 18

    with db.connect() as conn:
        conn.execute(
            "UPDATE sync_state SET status = ?, message = ? WHERE id = 1",
            ("syncing", "Partien werden von chess.com geladen…"),
        )

    try:
        archives = list(reversed(client.get_archives()))
        if not force_full:
            archives = archives[:recent_months]

        inserted = 0
        scanned = 0
        daily_seen = 0
        purge_coach_games()

        for archive_url in archives:
            games = client.get_games_for_archive(archive_url)
            for game in games:
                scanned += 1
                time_class = game.get("time_class") or ""
                if time_class not in allowed:
                    continue

                daily_seen += 1
                raw_url = game.get("url") or ""
                pgn = game.get("pgn") or ""
                if not raw_url or not pgn:
                    continue

                gid = game_id_from_url(raw_url)
                url = public_game_url(raw_url, pgn, game.get("uuid"))
                white = game.get("white") or {}
                black = game.get("black") or {}
                if is_coach_game(pgn, white.get("username"), black.get("username")):
                    continue
                color = _user_color(game, settings.chess_username)
                user_result_raw = _user_result(game, color)
                eco, opening_name = extract_opening(pgn)

                with db.connect() as conn:
                    existing = conn.execute(
                        "SELECT id FROM games WHERE id = ?", (gid,)
                    ).fetchone()
                    if existing:
                        continue
                    conn.execute(
                        """
                        INSERT INTO games (
                            id, url, username, time_class, rated,
                            white_username, black_username, white_rating, black_rating,
                            result, user_color, user_result, opening_eco, opening_name,
                            end_time, pgn, synced_at, analyzed
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                        """,
                        (
                            gid,
                            url,
                            settings.chess_username,
                            time_class,
                            1 if game.get("rated") else 0,
                            white.get("username"),
                            black.get("username"),
                            white.get("rating"),
                            black.get("rating"),
                            None,
                            color,
                            _normalize_result(user_result_raw),
                            eco,
                            opening_name,
                            game.get("end_time"),
                            pgn,
                            _utcnow(),
                        ),
                    )
                    inserted += 1

        with db.connect() as conn:
            total = conn.execute("SELECT COUNT(*) AS c FROM games").fetchone()["c"]
            conn.execute(
                """
                UPDATE sync_state
                SET last_sync_at = ?, games_synced = ?, status = ?, message = ?
                WHERE id = 1
                """,
                (
                    _utcnow(),
                    total,
                    "idle",
                    f"Sync fertig: {inserted} neu, {total} gesamt (Daily gesehen: {daily_seen})",
                ),
            )

        return {
            "inserted": inserted,
            "total": total,
            "scanned": scanned,
            "daily_seen": daily_seen,
        }
    except Exception as exc:
        with db.connect() as conn:
            conn.execute(
                "UPDATE sync_state SET status = ?, message = ? WHERE id = 1",
                ("error", f"Sync-Fehler: {exc}"),
            )
        raise
