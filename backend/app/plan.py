from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .db import db, row_to_dict
from .insights import get_insights


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


MOTIF_LABELS = {
    "hanging_piece": "hängende Figuren / ungedeckte Figuren",
    "missed_tactic": "verpasste Taktiken",
    "positional": "positionelle Ungenauigkeiten",
}

# Chess.com deep-links (themes are selected on the learning/custom page)
CHESSCOM = {
    "puzzle_themes": {
        "label": "Themen-Puzzles auf chess.com",
        "url": "https://www.chess.com/puzzles/learning",
        "hint": "Dort Themes wie Hanging Pieces / Fork / Double Attack anhaken",
    },
    "puzzles_rated": {
        "label": "Rated Puzzles",
        "url": "https://www.chess.com/puzzles/rated",
    },
    "endgames": {
        "label": "Endspiele üben",
        "url": "https://www.chess.com/endgames",
    },
    "lessons_endgame": {
        "label": "Endspiel-Lessons",
        "url": "https://www.chess.com/lessons?search=endgame",
    },
    "openings_explorer": {
        "label": "Eröffnungen auf chess.com",
        "url": "https://www.chess.com/openings",
    },
}

MOTIF_LINKS = {
    "hanging_piece": [
        {
            "label": "Hanging Pieces üben",
            "url": "https://www.chess.com/puzzles/learning",
            "hint": "Theme „Hanging Pieces“ auswählen",
        },
    ],
    "missed_tactic": [
        {
            "label": "Fork / Double Attack üben",
            "url": "https://www.chess.com/puzzles/learning",
            "hint": "Themes „Fork“ und „Double Attack“ auswählen",
        },
    ],
}


def _task(text: str, links: list[dict[str, str]] | None = None) -> dict[str, Any]:
    task: dict[str, Any] = {"text": text}
    if links:
        task["links"] = links
    return task


def generate_training_plan(window: int = 40) -> dict[str, Any]:
    insights = get_insights(window)
    items: list[dict[str, Any]] = []
    priority = 1

    for weakness in insights.get("top_weaknesses", []):
        wid = weakness["id"]
        item: dict[str, Any] = {
            "id": wid,
            "priority": priority,
            "title": weakness["title"],
            "why": weakness["why"],
            "metric": weakness["metric"],
            "severity": weakness["severity"],
            "tasks": [],
            "completed": False,
        }

        if wid == "blunder_check":
            crit = insights.get("critical_positions", [])[:3]
            item["tasks"] = [
                _task(
                    "Vor jedem Zug in Daily: 10 Sekunden Blunder-Check (hängende Figuren, Checks, Fänge)."
                ),
                _task(
                    "15 Puzzles mit Fokus auf „Hanging Pieces“ / „Fork“ — langsam lösen, nicht rushen.",
                    [
                        CHESSCOM["puzzle_themes"],
                    ],
                ),
                _task(
                    "3 eigene kritische Stellungen nachspielen (siehe unten) und den besten Zug finden, bevor du die Lösung siehst."
                ),
            ]
            item["critical_refs"] = [
                {
                    "game_id": c["game_id"],
                    "ply": c["ply"],
                    "fen": c["fen_before"],
                    "url": c["game_url"],
                }
                for c in crit
            ]
        elif wid == "endgames":
            item["tasks"] = [
                _task(
                    "Täglich 10 Minuten: Lucena/Philidor, grundlegende Turmendspiele, Opposition bei Bauernendspielen.",
                    [CHESSCOM["endgames"], CHESSCOM["lessons_endgame"]],
                ),
                _task(
                    "In jeder Daily-Partie ab Zug 30 bewusst Material und Königaktivität prüfen."
                ),
                _task(
                    "2 verlorene Partien mit Endspiel-Fehlern annotieren: Wo war die technische Gewinnstellung?"
                ),
            ]
        elif wid == "openings":
            weak = [
                o
                for o in insights.get("openings", [])
                if o["games"] >= 2 and o["score"] <= 0.45
            ][:3]
            names = [o["name"] for o in weak] or ["deine häufigsten Verlierer-Eröffnungen"]
            item["tasks"] = [
                _task(
                    f"Nur diese Eröffnungen reviewen: {', '.join(names)}.",
                    [CHESSCOM["openings_explorer"]],
                ),
                _task(
                    "Pro Eröffnung: 5 Verluste öffnen, den ersten klaren Fehler markieren — Idee verstehen, nicht Züge pauken."
                ),
                _task(
                    "Eine „Standard-Antwort“ auf die 3 häufigsten Gegnerzüge notieren."
                ),
            ]
            item["openings"] = weak
        elif wid == "motifs":
            motifs = insights.get("motifs", [])
            top_motif = motifs[0]["motif"] if motifs else "missed_tactic"
            label = MOTIF_LABELS.get(top_motif, top_motif)
            links = MOTIF_LINKS.get(top_motif, [CHESSCOM["puzzle_themes"]])
            item["tasks"] = [
                _task(
                    f"Puzzle-Theme diese Woche: {label} (20 Aufgaben, mit Erklärung lesen).",
                    links,
                ),
                _task(
                    "In der Partie-Liste nach Motiven filtern und 5 Beispiele bewusst nachspielen."
                ),
            ]
        elif wid == "review_ritual":
            item["tasks"] = [
                _task(
                    "Nach jeder abgeschlossenen Daily-Partie: innerhalb 24h in dieser App öffnen und kritische Züge ansehen."
                ),
                _task(
                    "Einen Satz notieren: „Mein Fehler war …, nächstes Mal prüfe ich …“."
                ),
                _task(
                    "Wöchentlich: Plan aktualisieren lassen, wenn neue Analysen da sind."
                ),
            ]
        else:
            item["tasks"] = [_task(weakness["why"])]

        items.append(item)
        priority += 1

    items = items[:5]

    with db.connect() as conn:
        progress_rows = conn.execute(
            "SELECT item_id, completed FROM plan_progress"
        ).fetchall()
        progress = {r["item_id"]: bool(r["completed"]) for r in progress_rows}
        for item in items:
            item["completed"] = progress.get(item["id"], False)

        payload = {
            "generated_at": _utcnow(),
            "window_size": window,
            "items": items,
            "insights_summary": {
                "games_count": insights.get("games_count"),
                "avg_acpl": insights.get("avg_acpl"),
                "record": insights.get("record"),
                "avg_blunders_per_game": insights.get("avg_blunders_per_game"),
            },
        }
        conn.execute(
            """
            INSERT OR REPLACE INTO training_plans (id, generated_at, window_size, items_json, insights_json)
            VALUES (1, ?, ?, ?, ?)
            """,
            (
                payload["generated_at"],
                window,
                json.dumps(items, ensure_ascii=False),
                json.dumps(payload["insights_summary"], ensure_ascii=False),
            ),
        )

    return payload


def get_training_plan() -> dict[str, Any] | None:
    with db.connect() as conn:
        row = row_to_dict(
            conn.execute("SELECT * FROM training_plans WHERE id = 1").fetchone()
        )
        if not row:
            return None
        items = json.loads(row["items_json"])
        progress_rows = conn.execute(
            "SELECT item_id, completed FROM plan_progress"
        ).fetchall()
        progress = {r["item_id"]: bool(r["completed"]) for r in progress_rows}
        for item in items:
            item["completed"] = progress.get(item["id"], False)
            # Normalize legacy string tasks
            normalized = []
            for task in item.get("tasks", []):
                if isinstance(task, str):
                    normalized.append({"text": task})
                else:
                    normalized.append(task)
            item["tasks"] = normalized
        return {
            "generated_at": row["generated_at"],
            "window_size": row["window_size"],
            "items": items,
            "insights_summary": json.loads(row["insights_json"]),
        }


def set_plan_item_completed(item_id: str, completed: bool) -> None:
    with db.connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO plan_progress (item_id, completed, updated_at)
            VALUES (?, ?, ?)
            """,
            (item_id, 1 if completed else 0, _utcnow()),
        )
