from __future__ import annotations

import io
import re
import time
from collections import defaultdict
from typing import Any

import chess.pgn

from .config import get_settings
from .db import _utcnow, db, rows_to_dicts

# Same cut as the analyzer: the first ten moves are the opening.
OPENING_MOVES = 10
MIN_GAMES = 2
MIN_CHESSLY_GAMES = 2
MIN_CHESSLY_PLIES = 4
WINDOWS = (90, 180, 0)
SERIOUS = {"mistake", "blunder"}

SEVERITY_LABEL = {
    "blunder": "Patzer",
    "mistake": "Fehler",
    "inaccuracy": "Ungenauigkeit",
}

# Chess.com names append the move order after the variation title: "3...d6 4.Nf3".
_MOVE_SPLIT = re.compile(r"\s+(?=\d+\.{1,3})")


def split_opening(name: str | None) -> tuple[str, str | None]:
    raw = (name or "").strip() or "Unbekannt"
    match = _MOVE_SPLIT.search(raw)
    if not match:
        return raw, None
    family = raw[: match.start()].strip()
    variation = raw[match.end() :].strip()
    return family or raw, variation or None


def move_number(ply: int) -> int:
    return (int(ply) + 1) // 2


def moves_from_pgn(pgn: str | None, limit: int = 16) -> list[str]:
    game = chess.pgn.read_game(io.StringIO(pgn or ""))
    if game is None:
        return []
    board = game.board()
    sans: list[str] = []
    for ply, move in enumerate(game.mainline_moves()):
        if ply >= limit:
            break
        sans.append(board.san(move))
        board.push(move)
    return sans


def majority_moves(sequences: list[list[str]], max_plies: int = 10) -> list[str]:
    """Most common move order from ply 1, until the games leave that path."""
    if not sequences:
        return []
    line: list[str] = []
    active = sequences
    for ply in range(max_plies):
        votes: dict[str, int] = defaultdict(int)
        for sequence in active:
            if ply < len(sequence):
                votes[sequence[ply]] += 1
        if not votes:
            break
        san, count = max(votes.items(), key=lambda item: (item[1], item[0]))
        if len(sequences) > 1 and count < 2:
            break
        line.append(san)
        active = [sequence for sequence in active if ply < len(sequence) and sequence[ply] == san]
    return line


def ply_count(moves: str | None) -> int:
    if not moves:
        return 0
    return sum(1 for part in moves.split() if not part.endswith("."))


def worth_chessly(games: int, moves: str | None) -> bool:
    return games >= MIN_CHESSLY_GAMES and ply_count(moves) >= MIN_CHESSLY_PLIES


def format_moves(sans: list[str]) -> str | None:
    if not sans:
        return None
    parts: list[str] = []
    for ply, san in enumerate(sans):
        if ply % 2 == 0:
            parts.append(f"{ply // 2 + 1}. {san}")
        else:
            parts.append(san)
    return " ".join(parts)


def _faults(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    faults: list[dict[str, Any]] = []
    by_game: dict[str, dict[str, Any]] = {}
    for error in errors:
        fault = by_game.get(error["game_id"])
        if fault is None:
            fault = {
                "game_id": error["game_id"],
                "url": error.get("url"),
                "result": error.get("result"),
                "ply": error["ply"],
                "slips": [],
            }
            by_game[error["game_id"]] = fault
            faults.append(fault)
        fault["slips"].append(
            {
                "ply": error["ply"],
                "move_number": error["move_number"],
                "move_san": error.get("move_san"),
                "best_move_san": error.get("best_move_san"),
                "severity": error["severity"],
                "label": error["label"],
            }
        )
    return faults


def _when(move_counts: list[tuple[int, int]]) -> str:
    if not move_counts:
        return "In der Eröffnung kein Fehler und kein Patzer."
    parts = [f"Zug {move} ({count}-mal)" for move, count in move_counts[:3]]
    if len(parts) == 1:
        return f"Schwere Fehler vor allem in {parts[0]}."
    return "Schwere Fehler vor allem in " + " und ".join([", ".join(parts[:-1]), parts[-1]]) + "."


def _summary(game_count: int, errors: list[dict[str, Any]]) -> str:
    if game_count == 0:
        return "Noch keine analysierten Partien."
    if not errors:
        return (
            f"In {game_count} analysierten Partien gibt es in den ersten {OPENING_MOVES} Zügen "
            "keinen Fehler und keinen Patzer."
        )
    games_with = len({error["game_id"] for error in errors})
    counts: dict[int, int] = defaultdict(int)
    for error in errors:
        counts[move_number(error["ply"])] += 1
    move = min(counts, key=lambda number: (-counts[number], number))
    return (
        f"In {games_with} von {game_count} Partien passiert in den ersten {OPENING_MOVES} Zügen "
        f"ein Fehler oder Patzer. Am häufigsten in Zug {move}."
    )


def build_opening_report(
    games: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    trained: set[tuple[str, str]] | None = None,
    days: int = 90,
) -> dict[str, Any]:
    trained = trained or set()
    issues_by_game: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for issue in issues:
        if issue.get("phase") != "opening":
            continue
        issues_by_game[issue["game_id"]].append(issue)

    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    for game in games:
        color = game.get("user_color")
        if color not in ("white", "black"):
            continue
        family, _variation = split_opening(game.get("opening_name"))
        key = (color, family)
        bucket = buckets.get(key)
        if bucket is None:
            bucket = {
                "color": color,
                "name": family,
                "games": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "inaccuracies": 0,
                "errors": [],
                "sequences": [],
            }
            buckets[key] = bucket
        bucket["games"] += 1
        if game.get("moves"):
            bucket["sequences"].append(game["moves"])
        result = game.get("user_result")
        if result == "win":
            bucket["wins"] += 1
        elif result == "draw":
            bucket["draws"] += 1
        elif result == "loss":
            bucket["losses"] += 1
        for issue in issues_by_game.get(game["id"], []):
            if issue.get("severity") == "inaccuracy":
                bucket["inaccuracies"] += 1
                continue
            if issue.get("severity") not in SERIOUS:
                continue
            _family, variation = split_opening(game.get("opening_name"))
            bucket["errors"].append(
                {
                    "game_id": game["id"],
                    "ply": issue["ply"],
                    "move_number": move_number(issue["ply"]),
                    "move_san": issue.get("move_san"),
                    "best_move_san": issue.get("best_move_san"),
                    "severity": issue["severity"],
                    "label": SEVERITY_LABEL.get(issue["severity"], issue["severity"]),
                    "variation": variation,
                    "result": result,
                    "url": game.get("url"),
                }
            )

    serious = [error for bucket in buckets.values() for error in bucket["errors"]]
    colors = []
    for color, label in (("white", "Weiß"), ("black", "Schwarz")):
        lines = []
        for bucket in buckets.values():
            if bucket["color"] != color:
                continue
            if bucket["games"] < MIN_GAMES and not bucket["errors"]:
                continue
            errors = sorted(bucket["errors"], key=lambda error: (error["ply"], error["game_id"]))
            counts: dict[int, int] = defaultdict(int)
            for error in errors:
                counts[error["move_number"]] += 1
            ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
            moves = format_moves(majority_moves(bucket["sequences"]))
            lines.append(
                {
                    "name": bucket["name"],
                    "moves": moves,
                    "games": bucket["games"],
                    "wins": bucket["wins"],
                    "draws": bucket["draws"],
                    "losses": bucket["losses"],
                    "inaccuracies": bucket["inaccuracies"],
                    "serious": len(errors),
                    "when": _when(ranked),
                    "spots": [{"move": move, "count": count} for move, count in ranked[:3]],
                    "faults": _faults(errors),
                    "trained": (color, bucket["name"]) in trained,
                    "chessly": worth_chessly(bucket["games"], moves),
                }
            )
        lines.sort(key=lambda line: (-line["serious"], -line["games"], line["name"]))
        if lines:
            colors.append(
                {
                    "color": color,
                    "label": label,
                    "lines": lines,
                    "recommend": [line for line in lines if line["chessly"] and not line["trained"]],
                    "done": [line for line in lines if line["trained"]],
                }
            )

    window = "alle Partien" if days == 0 else f"die letzten {days} Tage"
    return {
        "games": len(games),
        "days": days,
        "window": window,
        "summary": f"Auswertung für {window}. " + _summary(len(games), serious),
        "colors": colors,
    }


def _cutoff(days: int) -> int:
    if days == 0:
        return 0
    return int(time.time() - days * 86400)


def _trained_keys() -> set[tuple[str, str]]:
    with db.connect() as conn:
        rows = conn.execute("SELECT color, name FROM opening_trained").fetchall()
    return {(row["color"], row["name"]) for row in rows}


def set_opening_trained(color: str, name: str, trained: bool, days: int = 90) -> dict[str, Any]:
    if color not in ("white", "black"):
        raise ValueError("color")
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("name")
    with db.connect() as conn:
        if trained:
            conn.execute(
                """
                INSERT INTO opening_trained (color, name, trained_at)
                VALUES (?, ?, ?)
                ON CONFLICT(color, name) DO UPDATE SET trained_at = excluded.trained_at
                """,
                (color, cleaned, _utcnow()),
            )
        else:
            conn.execute(
                "DELETE FROM opening_trained WHERE color = ? AND name = ?",
                (color, cleaned),
            )
    return get_opening_report(days)


def get_opening_report(days: int = 90) -> dict[str, Any]:
    if days not in WINDOWS:
        days = 90
    settings = get_settings()
    cutoff = _cutoff(days)
    with db.connect() as conn:
        games = rows_to_dicts(
            conn.execute(
                """
                SELECT id, opening_name, user_color, user_result, url, pgn
                FROM games
                WHERE analyzed = 1 AND username = ?
                  AND (? = 0 OR end_time >= ?)
                """,
                (settings.chess_username, cutoff, cutoff),
            ).fetchall()
        )
        for game in games:
            game["moves"] = moves_from_pgn(game.pop("pgn", None))
        issues = rows_to_dicts(
            conn.execute(
                """
                SELECT i.game_id, i.ply, i.move_san, i.best_move_san, i.severity, i.phase
                FROM move_issues i
                JOIN games g ON g.id = i.game_id
                WHERE i.phase = 'opening' AND g.analyzed = 1 AND g.username = ?
                  AND (? = 0 OR g.end_time >= ?)
                """,
                (settings.chess_username, cutoff, cutoff),
            ).fetchall()
        )
    return build_opening_report(games, issues, _trained_keys(), days)
