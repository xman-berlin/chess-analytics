from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import chess

from .config import get_settings
from .db import db, rows_to_dicts
from .explain import explain_position

# Player-POV centipawns. Mate scores stay at ±100000 and still pass these cuts.
CLEAR_ADVANTAGE_CP = 200
ADVANTAGE_KEPT_CP = 80
EQUAL_LOW_CP = -80
EQUAL_HIGH_CP = 120
NOW_LOST_CP = -120
NEVER_EQUAL_CP = -50

THROWN_WIN = "thrown_win"
THROWN_DRAW = "thrown_draw"
LOST_EARLY = "lost_early"
OTHER = "other"

TARGET_RATING = 1500
RECENT_WINDOW = 20
QUIZ_LIMIT = 12

LABELS = {
    THROWN_WIN: "Gewinn verschenkt",
    THROWN_DRAW: "Remis verspielt",
    LOST_EARLY: "Schon früh verloren",
}

WHY = {
    THROWN_WIN: "Eine klar bessere Stellung wurde durch einen eigenen Fehler abgegeben.",
    THROWN_DRAW: "Aus einer ausgeglichenen Stellung hat ein einzelner Fehler die Partie verloren.",
    LOST_EARLY: "Nach der Eröffnung war die Stellung nicht mehr ausgeglichen.",
}

PROMPTS = {
    THROWN_WIN: "Du standest klar besser. Welcher Zug hält den Vorteil?",
    THROWN_DRAW: "Die Stellung ist ausgeglichen. Welcher Zug hält das Remis?",
    LOST_EARLY: "Hier ist die Partie früh gekippt. Welcher Zug war besser?",
}

FOCUS_ORDER = (THROWN_WIN, THROWN_DRAW, LOST_EARLY)


def _serious(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for issue in issues:
        if issue.get("severity") not in ("blunder", "mistake"):
            continue
        if issue.get("eval_before") is None or issue.get("eval_after") is None:
            continue
        out.append(issue)
    return out


def _is_thrown_win(issue: dict[str, Any]) -> bool:
    return issue["eval_before"] >= CLEAR_ADVANTAGE_CP and issue["eval_after"] <= ADVANTAGE_KEPT_CP


def _is_thrown_draw(issue: dict[str, Any]) -> bool:
    return EQUAL_LOW_CP <= issue["eval_before"] <= EQUAL_HIGH_CP and issue["eval_after"] <= NOW_LOST_CP


def _pick_largest_drop(issues: list[dict[str, Any]]) -> dict[str, Any]:
    return max(issues, key=lambda issue: (issue["eval_before"] - issue["eval_after"], issue.get("cpl") or 0))


def classify_game(issues: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify one game from the player's mistake and blunder rows."""
    serious = _serious(issues)
    if not serious:
        return {"category": OTHER, "issue": None}

    thrown_wins = [issue for issue in serious if _is_thrown_win(issue)]
    if thrown_wins:
        return {"category": THROWN_WIN, "issue": _pick_largest_drop(thrown_wins)}

    thrown_draws = [issue for issue in serious if _is_thrown_draw(issue)]
    if thrown_draws:
        return {"category": THROWN_DRAW, "issue": _pick_largest_drop(thrown_draws)}

    max_before = max(issue["eval_before"] for issue in serious)
    if max_before < NEVER_EQUAL_CP:
        opening = [issue for issue in serious if issue.get("phase") == "opening"]
        decisive = min(opening or serious, key=lambda issue: issue["ply"])
        return {"category": LOST_EARLY, "issue": decisive}

    return {"category": OTHER, "issue": None}


def san_to_uci(fen: str, san: str) -> str | None:
    board = chess.Board(fen)
    try:
        move = board.parse_san(san)
    except ValueError:
        return None
    return move.uci()


def uci_to_san(fen: str, uci: str) -> str | None:
    board = chess.Board(fen)
    try:
        move = chess.Move.from_uci(uci)
    except ValueError:
        return None
    if move not in board.legal_moves:
        return None
    return board.san(move)


def _bucket() -> dict[str, int]:
    return {THROWN_WIN: 0, THROWN_DRAW: 0, LOST_EARLY: 0, OTHER: 0}


def _annotate(games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annotated = []
    for game in games:
        classified = classify_game(game["issues"])
        annotated.append({**game, "category": classified["category"], "issue": classified["issue"]})
    return annotated


def _counts(games: list[dict[str, Any]]) -> dict[str, int]:
    counts = _bucket()
    for game in games:
        counts[game["category"]] += 1
    return counts


def _focus(counts: dict[str, int]) -> str | None:
    best: str | None = None
    best_n = 0
    for category in FOCUS_ORDER:
        n = counts[category]
        if n > best_n:
            best = category
            best_n = n
    return best


def _load_games(limit: int) -> list[dict[str, Any]]:
    settings = get_settings()
    with db.connect() as conn:
        games = rows_to_dicts(
            conn.execute(
                """
                SELECT g.id, g.url, g.user_result, g.opening_name, g.end_time
                FROM games g
                JOIN analyses a ON a.game_id = g.id
                WHERE g.username = ?
                ORDER BY g.end_time DESC
                LIMIT ?
                """,
                (settings.chess_username, limit),
            ).fetchall()
        )
        if not games:
            return []
        ids = [game["id"] for game in games]
        placeholders = ",".join("?" * len(ids))
        issues = rows_to_dicts(
            conn.execute(
                f"SELECT * FROM move_issues WHERE game_id IN ({placeholders})",
                ids,
            ).fetchall()
        )
    by_game: dict[str, list[dict[str, Any]]] = {}
    for issue in issues:
        by_game.setdefault(issue["game_id"], []).append(issue)
    for game in games:
        game["issues"] = by_game.get(game["id"], [])
    return games


def _playable_issue(game: dict[str, Any]) -> dict[str, Any] | None:
    category = game["category"]
    serious = _serious(game["issues"])
    if category == THROWN_WIN:
        candidates = [issue for issue in serious if _is_thrown_win(issue)]
        candidates.sort(key=lambda issue: issue["eval_before"] - issue["eval_after"], reverse=True)
    elif category == THROWN_DRAW:
        candidates = [issue for issue in serious if _is_thrown_draw(issue)]
        candidates.sort(key=lambda issue: issue.get("cpl") or 0, reverse=True)
    elif category == LOST_EARLY:
        opening = [issue for issue in serious if issue.get("phase") == "opening"]
        candidates = sorted(opening or serious, key=lambda issue: issue["ply"])
    else:
        return None

    for issue in candidates:
        fen = issue.get("fen_before")
        san = issue.get("best_move_san")
        if not fen or not san:
            continue
        if san_to_uci(fen, san) is None:
            continue
        return issue
    return None


def _solved_keys() -> set[tuple[str, int]]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT game_id, ply FROM quiz_attempts WHERE correct = 1"
        ).fetchall()
    return {(row["game_id"], row["ply"]) for row in rows}


def _position(game: dict[str, Any], issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "game_id": game["id"],
        "ply": issue["ply"],
        "fen": issue["fen_before"],
        "opening_name": game.get("opening_name"),
        "user_result": game.get("user_result"),
        "phase": issue.get("phase"),
        "eval_before": issue["eval_before"],
        "cpl": issue.get("cpl"),
        "url": game.get("url"),
    }


def get_leak_report(window: int = RECENT_WINDOW) -> dict[str, Any]:
    games = _annotate(_load_games(window * 2))
    recent = games[:window]
    prior = games[window : window * 2]
    recent_counts = _counts(recent)
    prior_counts = _counts(prior)
    focus = _focus(recent_counts)
    return {
        "target_rating": TARGET_RATING,
        "window": window,
        "recent": {
            "games": len(recent),
            "thrown_wins": recent_counts[THROWN_WIN],
            "thrown_draws": recent_counts[THROWN_DRAW],
            "lost_early": recent_counts[LOST_EARLY],
            "other": recent_counts[OTHER],
        },
        "prior": {
            "games": len(prior),
            "thrown_wins": prior_counts[THROWN_WIN],
            "thrown_draws": prior_counts[THROWN_DRAW],
            "lost_early": prior_counts[LOST_EARLY],
            "other": prior_counts[OTHER],
        },
        "focus": focus,
        "focus_label": LABELS.get(focus) if focus else None,
        "focus_why": WHY.get(focus) if focus else None,
        "prompt": PROMPTS.get(focus) if focus else None,
    }


def get_quiz(window: int = RECENT_WINDOW) -> dict[str, Any]:
    report = get_leak_report(window)
    focus = report["focus"]
    games = _annotate(_load_games(window))
    solved = _solved_keys()
    candidates: list[dict[str, Any]] = []
    if focus:
        for game in games:
            if game["category"] != focus:
                continue
            issue = _playable_issue(game)
            if issue is None:
                continue
            candidates.append(_position(game, issue))
        candidates.sort(key=lambda item: item.get("cpl") or 0, reverse=True)

    solved_n = sum(1 for item in candidates if (item["game_id"], item["ply"]) in solved)
    remaining = [
        item for item in candidates if (item["game_id"], item["ply"]) not in solved
    ][:QUIZ_LIMIT]
    return {
        "target_rating": report["target_rating"],
        "focus": focus,
        "focus_label": report["focus_label"],
        "focus_why": report["focus_why"],
        "prompt": report["prompt"],
        "available": len(candidates),
        "solved": solved_n,
        "positions": remaining,
    }


def record_quiz_attempt(game_id: str, ply: int, uci: str) -> dict[str, Any]:
    settings = get_settings()
    with db.connect() as conn:
        issue = conn.execute(
            """
            SELECT i.* FROM move_issues i
            JOIN games g ON g.id = i.game_id
            WHERE i.game_id = ? AND i.ply = ? AND g.username = ?
            """,
            (game_id, ply, settings.chess_username),
        ).fetchone()
        if issue is None:
            return {"error": "not_found"}
        issue = dict(issue)

    fen = issue.get("fen_before")
    best_san = issue.get("best_move_san")
    if not fen or not best_san:
        return {"error": "unplayable"}

    best_uci = san_to_uci(fen, best_san)
    attempt_san = uci_to_san(fen, uci)
    if best_uci is None or attempt_san is None:
        return {"error": "illegal"}

    correct = uci.lower() == best_uci.lower()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO quiz_attempts (game_id, ply, correct, attempted_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(game_id, ply) DO UPDATE SET
                correct = excluded.correct,
                attempted_at = excluded.attempted_at
            """,
            (
                game_id,
                ply,
                1 if correct else 0,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    return {
        "correct": correct,
        "best_san": best_san,
        "played_san": issue.get("move_san"),
        "attempt_san": attempt_san,
        "why": explain_position(
            fen,
            issue.get("move_san"),
            best_san,
            issue.get("eval_before"),
            issue.get("eval_after"),
        ),
    }


def reset_quiz() -> None:
    with db.connect() as conn:
        conn.execute("DELETE FROM quiz_attempts")
