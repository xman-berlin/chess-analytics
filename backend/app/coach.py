from __future__ import annotations

from typing import Any

from .chesscom_client import ChessComClient
from .config import get_settings
from .curriculum import build_curriculum
from .db import db, rows_to_dicts
from .leaks import (
    LABELS,
    LOST_EARLY,
    OTHER,
    TARGET_RATING,
    THROWN_DRAW,
    THROWN_WIN,
    classify_game,
    get_leak_report,
    get_quiz,
)

RESULT_WORDS = {
    "win": "Sieg",
    "loss": "Niederlage",
    "draw": "Remis",
}


def level_for(rating: int | None) -> dict[str, str]:
    if rating is None:
        return {
            "label": "Daily",
            "principle": "Der Plan richtet sich nach den letzten Partien, sobald ein Rating vorliegt.",
        }
    if rating < 1200:
        return {
            "label": "unter 1200 Daily",
            "principle": "Hier entscheiden hängende Figuren und einzügige Taktik. Eine Fehlerart, keine Eröffnungstheorie.",
        }
    if rating < 1600:
        return {
            "label": "1400er Daily",
            "principle": (
                "In diesem Bereich kosten einzelne Züge aus ausgeglichener oder schon gewonnener Stellung die Punkte. "
                "Ein neues Eröffnungsrepertoire verschiebt das Rating kaum."
            ),
        }
    if rating < 2000:
        return {
            "label": "1600er Daily",
            "principle": "Hier zählt, ob ein Vorteil technisch umgewandelt wird und ob das Endspiel sitzt.",
        }
    return {
        "label": "2000er Daily",
        "principle": "Kleine Ungenauigkeiten und die Pläne in gleichen Stellungen entscheiden.",
    }


def _count_line(bucket: dict[str, int]) -> str:
    return (
        f"{bucket['thrown_draws']}× Remis verspielt, "
        f"{bucket['thrown_wins']}× Gewinn verschenkt, "
        f"{bucket['lost_early']}× schon früh verloren"
    )


def diagnosis(report: dict[str, Any]) -> str:
    recent = report["recent"]
    if recent["games"] == 0 or not report.get("focus"):
        return "Es liegen noch zu wenige ausgewertete Partien vor, um eine Hausaufgabe festzulegen."
    label = LABELS[report["focus"]]
    return (
        f"In den letzten {recent['games']} Daily-Partien: {_count_line(recent)}. "
        f"Diese Woche trainierst du nur „{label}“."
    )


def progress_note(report: dict[str, Any]) -> str | None:
    focus = report.get("focus")
    prior = report["prior"]
    recent = report["recent"]
    if not focus or prior["games"] == 0:
        return None
    key = {
        THROWN_WIN: "thrown_wins",
        THROWN_DRAW: "thrown_draws",
        LOST_EARLY: "lost_early",
    }[focus]
    now = recent[key]
    then = prior[key]
    label = LABELS[focus]
    wins_now = recent["thrown_wins"]
    wins_then = prior["thrown_wins"]
    if wins_now < wins_then:
        goal = f"Verschenkte Gewinnstellungen sind von {wins_then} auf {wins_now} gefallen."
    elif wins_now > wins_then:
        goal = f"Verschenkte Gewinnstellungen sind von {wins_then} auf {wins_now} gestiegen."
    else:
        goal = f"Verschenkte Gewinnstellungen liegen bei {wins_now} von {recent['games']}."
    if now < then:
        move = f"„{label}“ ist von {then} auf {now} zurückgegangen."
    elif now > then:
        move = f"„{label}“ ist von {then} auf {now} gestiegen."
    else:
        move = f"„{label}“ liegt bei {now}, unverändert zu den Partien davor."
    if focus == THROWN_WIN:
        return move
    return f"{move} {goal}"


def tasks_for(focus: str | None, available: int, solved: int) -> list[dict[str, str]]:
    if not focus:
        return []
    if available == 0 and solved > 0:
        practice = "Die Stellungen dieser Runde sind gelöst. Die nächste Hausaufgabe kommt aus der nächsten ausgewerteten Partie."
    elif available == 0:
        practice = "Sobald weitere Partien analysiert sind, liegen die Stellungen unter Üben."
    else:
        practice = f"Löse die {available} Stellungen unter Üben. Den Zug selbst finden, nicht den Partiezug nachspielen."

    if focus == THROWN_WIN:
        during = (
            "Sobald du klar besser stehst: vor dem Zug Schach, Schlagfälle und hängende Figuren prüfen, "
            "bevor du die Stellung „verbesserst“."
        )
    elif focus == LOST_EARLY:
        during = (
            "Nur die Eröffnung aus diesen Partien: den ersten klaren Fehler verstehen. "
            "Keine Variante auswendig lernen."
        )
    else:
        during = (
            "Vor jedem Zug in der Daily: Ist die Stellung noch ausgeglichen, "
            "und was kann der Gegner im nächsten Zug schlagen oder mit Schach erzwingen?"
        )
    return [
        {"kind": "practice", "text": practice},
        {"kind": "game", "text": during},
        {
            "kind": "review",
            "text": "Am Tag, an dem die Partie endet: sie hier öffnen und nur die markierte Stelle ansehen. Ein Satz, was du übersehen hast.",
        },
    ]


def withheld_for(focus: str | None, rating: int | None) -> list[str]:
    if not focus:
        return []
    items: list[str] = []
    if focus != LOST_EARLY:
        items.append("Keine neuen Eröffnungen. Die Partien kippen nicht dort.")
    if rating is not None and rating < 1600:
        items.append("Kein zweites Thema parallel. Ein Leck, bis die Zahl fällt.")
    return items


def review_game(issues: list[dict[str, Any]], game: dict[str, Any]) -> dict[str, Any]:
    classified = classify_game(issues)
    category = classified["category"]
    issue = classified["issue"]
    color = game.get("user_color")
    opponent = game.get("black_username") if color == "white" else game.get("white_username")
    result = RESULT_WORDS.get(game.get("user_result") or "", "Partie")
    base = {
        "category": category,
        "label": LABELS.get(category),
        "opponent": opponent,
        "result": game.get("user_result"),
        "result_word": result,
        "ply": issue["ply"] if issue else None,
        "move_san": issue.get("move_san") if issue else None,
        "best_move_san": issue.get("best_move_san") if issue else None,
        "opening_name": game.get("opening_name"),
    }
    if category == OTHER or issue is None:
        base["headline"] = f"{result} gegen {opponent or 'den Gegner'}."
        base["detail"] = "Kein einzelner Fehler hat die Partie entschieden."
        return base
    played = issue.get("move_san") or "dein Zug"
    best = issue.get("best_move_san") or "der Enginezug"
    who = opponent or "den Gegner"
    user_result = game.get("user_result")
    ply = issue["ply"]
    if category == THROWN_DRAW and user_result == "win":
        headline = (
            f"Sieg gegen {who}. In Zug {ply} hast du die ausgeglichene Stellung abgegeben "
            "und sie danach noch gewonnen."
        )
    elif category == THROWN_WIN and user_result != "loss":
        headline = f"{result} gegen {who}. In Zug {ply} hast du einen klaren Vorteil abgegeben."
    elif category == LOST_EARLY and user_result == "win":
        headline = f"Sieg gegen {who}. Die Partie war früh schlecht, in Zug {ply}, und du hast sie noch gedreht."
    else:
        headline = f"{result} gegen {who}. {LABELS[category]} in Zug {ply}."
    base["headline"] = headline
    base["detail"] = f"Gespielt {played}. Besser war {best}."
    return base


def compose_coach(
    *,
    rating: int | None,
    best_rating: int | None,
    report: dict[str, Any],
    practice_available: int,
    practice_solved: int,
    latest: dict[str, Any] | None,
) -> dict[str, Any]:
    level = level_for(rating)
    focus = report.get("focus")
    return {
        "target_rating": TARGET_RATING,
        "rating": rating,
        "best_rating": best_rating,
        "level_label": level["label"],
        "level_principle": level["principle"],
        "diagnosis": diagnosis(report),
        "progress": progress_note(report),
        "focus": focus,
        "focus_label": LABELS.get(focus) if focus else None,
        "assignment_title": f"Diese Woche nur: {LABELS[focus]}" if focus else "Noch keine Hausaufgabe",
        "tasks": tasks_for(focus, practice_available, practice_solved),
        "withheld": withheld_for(focus, rating),
        "practice": {
            "available": practice_available,
            "solved": practice_solved,
        },
        "latest_game": latest,
        "recent": report["recent"],
        "prior": report["prior"],
        "curriculum": build_curriculum(focus, rating, practice_available),
    }


def _ratings() -> tuple[int | None, int | None]:
    settings = get_settings()
    try:
        stats = ChessComClient(settings.chess_username).get_stats()
    except Exception:
        return None, None
    daily = (stats or {}).get("chess_daily") or {}
    current = (daily.get("last") or {}).get("rating")
    best = (daily.get("best") or {}).get("rating")
    return current, best


def _latest_review() -> dict[str, Any] | None:
    settings = get_settings()
    with db.connect() as conn:
        game = conn.execute(
            """
            SELECT g.id, g.url, g.user_color, g.user_result, g.white_username, g.black_username,
                   g.opening_name
            FROM games g
            JOIN analyses a ON a.game_id = g.id
            WHERE g.username = ?
            ORDER BY g.end_time DESC
            LIMIT 1
            """,
            (settings.chess_username,),
        ).fetchone()
        if game is None:
            return None
        game = dict(game)
        issues = rows_to_dicts(
            conn.execute(
                "SELECT * FROM move_issues WHERE game_id = ?",
                (game["id"],),
            ).fetchall()
        )
    review = review_game(issues, game)
    review["game_id"] = game["id"]
    review["url"] = game.get("url")
    return review


def get_coach() -> dict[str, Any]:
    report = get_leak_report()
    quiz = get_quiz()
    rating, best = _ratings()
    return compose_coach(
        rating=rating,
        best_rating=best,
        report=report,
        practice_available=quiz["available"] - quiz["solved"],
        practice_solved=quiz["solved"],
        latest=_latest_review(),
    )
