from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import chess

from .config import get_settings
from .db import db, rows_to_dicts
from .leaks import _is_thrown_draw, _is_thrown_win
from .openings import get_opening_report

BERLIN = ZoneInfo("Europe/Berlin")
POSITIONS_PER_WEEK = 5
OPENING_DAYS = 90

WEEKDAYS = (
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
)
MONTHS = (
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
)
RESULT_WORDS = {"win": "Sieg", "loss": "Niederlage", "draw": "Remis"}
RULE = (
    "Sonntag entscheidet der Check. Eine Stellung wird ersetzt, wenn du den Zug "
    "in dieser Woche einmal richtig findest. Sonst kommt dieselbe Stellung wieder. "
    "Eine Eröffnung wird ersetzt, wenn du die Linie als trainiert markierst. Sonst bleibt sie."
)


def berlin_today() -> date:
    return datetime.now(BERLIN).date()


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def week_label(monday: date) -> str:
    sunday = monday + timedelta(days=6)
    if monday.month == sunday.month:
        return f"{monday.day}.–{sunday.day}. {MONTHS[monday.month - 1]}"
    return (
        f"{monday.day}. {MONTHS[monday.month - 1]} – "
        f"{sunday.day}. {MONTHS[sunday.month - 1]}"
    )


def _start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=BERLIN)


def in_week(attempted_at: str | None, monday: date) -> bool:
    if not attempted_at:
        return False
    stamp = datetime.fromisoformat(attempted_at)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    start = _start(monday)
    return start <= stamp < start + timedelta(days=7)


def is_quiet(fen: str | None, san: str | None) -> bool:
    if not fen or not san:
        return False
    board = chess.Board(fen)
    try:
        move = board.parse_san(san)
    except ValueError:
        return False
    return not board.is_capture(move) and not board.gives_check(move)


def _kept(issue: dict[str, Any]) -> bool:
    if issue.get("eval_before") is None or issue.get("eval_after") is None:
        return False
    if issue.get("phase") != "middlegame":
        return False
    if issue.get("severity") not in ("mistake", "blunder"):
        return False
    if not _is_thrown_win(issue) and not _is_thrown_draw(issue):
        return False
    return is_quiet(issue.get("fen_before"), issue.get("best_move_san"))


def assign_positions(
    fresh: list[dict[str, Any]],
    repeats: list[dict[str, Any]],
    mastered: set[tuple[str, int]],
    limit: int = POSITIONS_PER_WEEK,
) -> list[dict[str, Any]]:
    chosen: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()

    def take(item: dict[str, Any]) -> None:
        key = (item["game_id"], int(item["ply"]))
        if key in mastered or key in seen or len(chosen) >= limit:
            return
        chosen.append(item)
        seen.add(key)

    for item in repeats:
        take(item)
    ranked = sorted(fresh, key=lambda item: (-(item.get("cpl") or 0), item["game_id"], item["ply"]))
    for item in ranked:
        take(item)
    return chosen


def assign_openings(
    lines_by_color: dict[str, list[dict[str, Any]]],
    pinned: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    chosen: list[dict[str, Any]] = []
    for color in ("white", "black"):
        pin = pinned.get(color)
        if pin and not pin.get("trained"):
            chosen.append(pin)
            continue
        for line in lines_by_color.get(color, []):
            if line.get("trained"):
                continue
            chosen.append(
                {
                    "color": color,
                    "name": line["name"],
                    "moves": line.get("moves"),
                }
            )
            break
    return chosen


def position_verdict(solved: bool) -> tuple[str, str, str]:
    if solved:
        return "advance", "Neue Stellung", "In dieser Woche richtig gelöst."
    return "repeat", "Dieselbe Stellung", "In dieser Woche nicht richtig gelöst."


def opening_verdict(trained: bool) -> tuple[str, str, str]:
    if trained:
        return "advance", "Nächste Variante", "Als trainiert markiert."
    return "repeat", "Dieselbe Linie", "Noch nicht als trainiert markiert."


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loads(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    return json.loads(raw)


def _opponent(color: str | None, white: str | None, black: str | None) -> str:
    if color == "white":
        return black or "Gegner"
    return white or "Gegner"


def _position_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "game_id": row["game_id"],
        "ply": int(row["ply"]),
        "fen": row.get("fen") or row.get("fen_before"),
        "move_san": row.get("move_san"),
        "best_move_san": row.get("best_move_san"),
        "opening_name": row.get("opening_name"),
        "opponent": row.get("opponent")
        or _opponent(row.get("user_color"), row.get("white_username"), row.get("black_username")),
        "cpl": row.get("cpl"),
        "prompt": "Was droht? Welcher Zug hält die Stellung?",
    }


def _opening_payload(row: dict[str, Any]) -> dict[str, Any]:
    color = row["color"]
    return {
        "color": color,
        "color_label": "Weiß" if color == "white" else "Schwarz",
        "name": row["name"],
        "moves": row.get("moves"),
    }


def _fresh_positions(since: int) -> list[dict[str, Any]]:
    settings = get_settings()
    with db.connect() as conn:
        rows = rows_to_dicts(
            conn.execute(
                """
                SELECT i.game_id, i.ply, i.move_san, i.best_move_san, i.fen_before,
                       i.cpl, i.eval_before, i.eval_after, i.phase, i.severity,
                       g.opening_name, g.user_color, g.white_username, g.black_username
                FROM move_issues i
                JOIN games g ON g.id = i.game_id
                WHERE g.username = ? AND g.analyzed = 1 AND g.end_time >= ?
                """,
                (settings.chess_username, since),
            ).fetchall()
        )
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not _kept(row):
            continue
        current = best.get(row["game_id"])
        if current is None or (row.get("cpl") or 0) > (current.get("cpl") or 0):
            best[row["game_id"]] = row
    return [_position_payload(row) for row in best.values()]


def _recommend_lines() -> dict[str, list[dict[str, Any]]]:
    report = get_opening_report(OPENING_DAYS)
    lines: dict[str, list[dict[str, Any]]] = {"white": [], "black": []}
    for color in report["colors"]:
        lines[color["color"]] = color["recommend"]
    return lines


def _mastered() -> set[tuple[str, int]]:
    with db.connect() as conn:
        rows = conn.execute("SELECT game_id, ply FROM position_mastered").fetchall()
    return {(row["game_id"], row["ply"]) for row in rows}


def _trained_names() -> set[tuple[str, str]]:
    with db.connect() as conn:
        rows = conn.execute("SELECT color, name FROM opening_trained").fetchall()
    return {(row["color"], row["name"]) for row in rows}


def _attempts() -> dict[tuple[str, int], dict[str, Any]]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT game_id, ply, correct, attempted_at FROM quiz_attempts"
        ).fetchall()
    return {(row["game_id"], row["ply"]): dict(row) for row in rows}


def _last_closed(conn: Any) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT week_start, verdict_json FROM training_weeks
        WHERE closed_at IS NOT NULL
        ORDER BY week_start DESC
        LIMIT 1
        """
    ).fetchone()
    return dict(row) if row else None


def _pins_from_verdict(conn: Any) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    closed = _last_closed(conn)
    if not closed or not closed.get("verdict_json"):
        return [], {}
    verdict = json.loads(closed["verdict_json"])
    keys = {
        item["key"]
        for item in verdict.get("items", [])
        if item.get("verdict") == "repeat"
    }
    if not keys:
        return [], {}
    rows = conn.execute(
        "SELECT item_key, kind, payload_json FROM week_items WHERE week_start = ?",
        (closed["week_start"],),
    ).fetchall()
    positions: list[dict[str, Any]] = []
    openings: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["item_key"] not in keys:
            continue
        payload = json.loads(row["payload_json"])
        if row["kind"] == "position":
            positions.append(payload)
        elif row["kind"] == "opening":
            openings[payload["color"]] = payload
    return positions, openings


def _insert_week(monday: date, positions: list[dict[str, Any]], openings: list[dict[str, Any]]) -> None:
    week_start = monday.isoformat()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO training_weeks (week_start, created_at)
            VALUES (?, ?)
            """,
            (week_start, _utcnow()),
        )
        existing = conn.execute(
            "SELECT COUNT(*) AS c FROM week_items WHERE week_start = ?",
            (week_start,),
        ).fetchone()["c"]
        if existing:
            return
        order = 0
        for opening in openings:
            payload = _opening_payload(opening)
            conn.execute(
                """
                INSERT INTO week_items (week_start, item_key, kind, sort_order, payload_json)
                VALUES (?, ?, 'opening', ?, ?)
                """,
                (
                    week_start,
                    f"opening:{payload['color']}:{payload['name']}",
                    order,
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            order += 1
        for index, position in enumerate(positions):
            payload = _position_payload(position)
            conn.execute(
                """
                INSERT INTO week_items (week_start, item_key, kind, sort_order, payload_json)
                VALUES (?, ?, 'position', ?, ?)
                """,
                (
                    week_start,
                    f"position:{payload['game_id']}:{payload['ply']}",
                    index,
                    json.dumps(payload, ensure_ascii=False),
                ),
            )


def _create_week(monday: date) -> None:
    since = int(_start(monday - timedelta(days=OPENING_DAYS)).timestamp())
    with db.connect() as conn:
        repeats, pinned = _pins_from_verdict(conn)
    positions = assign_positions(_fresh_positions(since), repeats, _mastered())
    openings = assign_openings(_recommend_lines(), pinned)
    _insert_week(monday, positions, openings)


def _reviews(monday: date) -> list[dict[str, Any]]:
    settings = get_settings()
    start = int(_start(monday).timestamp())
    end = int(_start(monday + timedelta(days=7)).timestamp())
    with db.connect() as conn:
        games = rows_to_dicts(
            conn.execute(
                """
                SELECT id, user_color, user_result, white_username, black_username, opening_name
                FROM games
                WHERE username = ? AND analyzed = 1 AND end_time >= ? AND end_time < ?
                ORDER BY end_time DESC
                """,
                (settings.chess_username, start, end),
            ).fetchall()
        )
        if not games:
            return []
        ids = [game["id"] for game in games]
        marks = ",".join("?" * len(ids))
        issues = rows_to_dicts(
            conn.execute(
                f"""
                SELECT game_id, ply, move_san, best_move_san, severity, cpl
                FROM move_issues
                WHERE game_id IN ({marks}) AND severity IN ('mistake', 'blunder')
                """,
                ids,
            ).fetchall()
        )
    by_game: dict[str, list[dict[str, Any]]] = {}
    for issue in issues:
        by_game.setdefault(issue["game_id"], []).append(issue)
    reviews = []
    for game in games:
        serious = by_game.get(game["id"], [])
        issue = max(serious, key=lambda item: item.get("cpl") or 0) if serious else None
        opponent = _opponent(game.get("user_color"), game.get("white_username"), game.get("black_username"))
        result = RESULT_WORDS.get(game.get("user_result") or "", "Partie")
        if issue is None:
            text = f"{result} gegen {opponent}. Kein einzelner schwerer Fehler."
            ply = None
        else:
            played = issue.get("move_san") or "dein Zug"
            best = issue.get("best_move_san") or "der andere Zug"
            text = f"{result} gegen {opponent}. Zug {((issue['ply'] + 1) // 2)}: {played} statt {best}."
            ply = issue["ply"]
        reviews.append(
            {
                "game_id": game["id"],
                "ply": ply,
                "text": text,
                "opening_name": game.get("opening_name"),
            }
        )
    return reviews


def _item_rows(conn: Any, week_start: str) -> list[dict[str, Any]]:
    rows = rows_to_dicts(
        conn.execute(
            """
            SELECT item_key, kind, sort_order, payload_json
            FROM week_items
            WHERE week_start = ?
            ORDER BY kind DESC, sort_order
            """,
            (week_start,),
        ).fetchall()
    )
    for row in rows:
        row["payload"] = json.loads(row.pop("payload_json"))
    return rows


def _decorate(
    rows: list[dict[str, Any]],
    monday: date,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    trained = _trained_names()
    attempts = _attempts()
    openings: list[dict[str, Any]] = []
    positions: list[dict[str, Any]] = []
    for row in rows:
        payload = row["payload"]
        if row["kind"] == "opening":
            known = (payload["color"], payload["name"]) in trained
            verdict, label, reason = opening_verdict(known)
            openings.append(
                {
                    "key": row["item_key"],
                    **payload,
                    "trained": known,
                    "verdict": verdict,
                    "verdict_label": label,
                    "reason": reason,
                    "title": f"{payload['color_label']} · {payload['name']}",
                }
            )
            continue
        attempt = attempts.get((payload["game_id"], int(payload["ply"])))
        solved = bool(
            attempt and attempt["correct"] and in_week(attempt.get("attempted_at"), monday)
        )
        verdict, label, reason = position_verdict(solved)
        day = WEEKDAYS[row["sort_order"]] if row["sort_order"] < 5 else ""
        positions.append(
            {
                "key": row["item_key"],
                "day": day,
                **payload,
                "solved": solved,
                "verdict": verdict,
                "verdict_label": label,
                "reason": reason,
                "title": f"{day} · Zug {((int(payload['ply']) + 1) // 2)} gegen {payload.get('opponent') or 'Gegner'}",
            }
        )
    return openings, positions


def _check_summary(openings: list[dict[str, Any]], positions: list[dict[str, Any]]) -> str:
    rows = openings + positions
    if not rows:
        return "Noch keine Aufgabe für diese Woche."
    repeated = [row["title"] for row in rows if row["verdict"] == "repeat"]
    advanced = [row["title"] for row in rows if row["verdict"] == "advance"]
    parts: list[str] = []
    if repeated:
        parts.append(f"{len(repeated)} bleiben: " + "; ".join(repeated) + ".")
    if advanced:
        parts.append(f"{len(advanced)} werden neu: " + "; ".join(advanced) + ".")
    return " ".join(parts)


def _last_check(before: str) -> dict[str, Any] | None:
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT week_start, verdict_json FROM training_weeks
            WHERE closed_at IS NOT NULL AND week_start < ?
            ORDER BY week_start DESC
            LIMIT 1
            """,
            (before,),
        ).fetchone()
    if row is None or not row["verdict_json"]:
        return None
    verdict = json.loads(row["verdict_json"])
    monday = date.fromisoformat(row["week_start"])
    return {
        "week_label": week_label(monday),
        "summary": verdict.get("summary") or "",
    }


def _render(monday: date, today: date, *, closed: bool) -> dict[str, Any]:
    week_start = monday.isoformat()
    with db.connect() as conn:
        rows = _item_rows(conn, week_start)
        closed_at = conn.execute(
            "SELECT closed_at, verdict_json FROM training_weeks WHERE week_start = ?",
            (week_start,),
        ).fetchone()
    openings, positions = _decorate(rows, monday)
    weekday = today.weekday()
    today_position = None
    if weekday < len(positions) and weekday < 5:
        today_position = positions[weekday]
    elif positions:
        today_position = next((item for item in positions if not item["solved"]), positions[0])
    if weekday < 5:
        headline = f"{WEEKDAYS[weekday]}: beide Linien auf Chessly, dazu eine Stellung."
    else:
        headline = "Wochenende: der Check entscheidet, was nächste Woche dran ist."
    stored = _loads(closed_at["verdict_json"] if closed_at else None)
    if stored.get("items"):
        saved = {item["key"]: item["verdict"] for item in stored["items"]}
        for row in openings + positions:
            verdict = saved.get(row["key"])
            if verdict is None:
                continue
            row["verdict"] = verdict
            if row["key"].startswith("opening:"):
                row["verdict_label"] = "Nächste Variante" if verdict == "advance" else "Dieselbe Linie"
            else:
                row["verdict_label"] = "Neue Stellung" if verdict == "advance" else "Dieselbe Stellung"
    next_rows: list[dict[str, Any]] = []
    if closed:
        with db.connect() as conn:
            next_rows = _item_rows(conn, (monday + timedelta(days=7)).isoformat())
    if closed:
        headline = "Check erledigt. Die nächsten Aufgaben gelten ab Montag."
    return {
        "week_start": week_start,
        "week_label": week_label(monday),
        "today_label": WEEKDAYS[weekday],
        "headline": headline,
        "pending_check": today > monday + timedelta(days=6) and not closed,
        "can_close": today >= monday + timedelta(days=6) and not closed,
        "check_first": closed or weekday >= 6 or today > monday + timedelta(days=6),
        "closed": closed,
        "rule": RULE,
        "openings": openings,
        "positions": positions,
        "today_position_key": None if closed else (today_position["key"] if today_position else None),
        "reviews": _reviews(monday),
        "check_summary": stored.get("summary") or _check_summary(openings, positions),
        "last_check": _last_check(week_start),
        "next_week": _next_preview(monday + timedelta(days=7), next_rows) if closed else None,
    }


def _next_preview(monday: date, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    openings = []
    positions = []
    for row in rows:
        payload = row["payload"]
        if row["kind"] == "opening":
            openings.append(
                {
                    "color_label": payload.get("color_label"),
                    "name": payload.get("name"),
                    "moves": payload.get("moves"),
                }
            )
        else:
            day = WEEKDAYS[row["sort_order"]] if row["sort_order"] < 5 else ""
            ply = int(payload.get("ply") or 0)
            positions.append(
                {
                    "day": day,
                    "opponent": payload.get("opponent"),
                    "ply": ply,
                    "move": (ply + 1) // 2,
                }
            )
    return {"week_label": week_label(monday), "openings": openings, "positions": positions}


def get_current_week(today: date | None = None) -> dict[str, Any]:
    today = today or berlin_today()
    monday = monday_of(today)
    with db.connect() as conn:
        past = conn.execute(
            """
            SELECT week_start FROM training_weeks
            WHERE closed_at IS NULL AND week_start < ?
            ORDER BY week_start DESC
            LIMIT 1
            """,
            (monday.isoformat(),),
        ).fetchone()
        current = conn.execute(
            "SELECT week_start, closed_at FROM training_weeks WHERE week_start = ?",
            (monday.isoformat(),),
        ).fetchone()
    if past:
        return _render(date.fromisoformat(past["week_start"]), today, closed=False)
    if current is None:
        _create_week(monday)
        return _render(monday, today, closed=False)
    return _render(monday, today, closed=current["closed_at"] is not None)


def close_current_week(today: date | None = None) -> dict[str, Any]:
    today = today or berlin_today()
    view = get_current_week(today)
    if view["closed"]:
        return view
    if not view["can_close"]:
        raise ValueError("Der Check schließt die Woche am Sonntag.")
    monday = date.fromisoformat(view["week_start"])
    items = []
    for opening in view["openings"]:
        items.append({"key": opening["key"], "verdict": opening["verdict"], "title": opening["title"]})
    for position in view["positions"]:
        items.append(
            {"key": position["key"], "verdict": position["verdict"], "title": position["title"]}
        )
    summary = _check_summary(view["openings"], view["positions"])
    with db.connect() as conn:
        for position in view["positions"]:
            if position["verdict"] != "advance":
                continue
            conn.execute(
                """
                INSERT OR IGNORE INTO position_mastered (game_id, ply, mastered_at)
                VALUES (?, ?, ?)
                """,
                (position["game_id"], position["ply"], _utcnow()),
            )
        conn.execute(
            """
            UPDATE training_weeks
            SET closed_at = ?, verdict_json = ?
            WHERE week_start = ?
            """,
            (_utcnow(), json.dumps({"items": items, "summary": summary}, ensure_ascii=False), monday.isoformat()),
        )
    _create_week(monday + timedelta(days=7))
    return get_current_week(today)
