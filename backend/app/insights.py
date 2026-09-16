from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .config import get_settings
from .db import db, rows_to_dicts


WINDOW = 40


def get_insights(window: int = WINDOW) -> dict[str, Any]:
    settings = get_settings()
    with db.connect() as conn:
        games = rows_to_dicts(
            conn.execute(
                """
                SELECT g.*, a.acpl, a.blunders, a.mistakes, a.inaccuracies,
                       a.opening_acpl, a.middlegame_acpl, a.endgame_acpl
                FROM games g
                JOIN analyses a ON a.game_id = g.id
                WHERE g.username = ?
                ORDER BY g.end_time DESC
                LIMIT ?
                """,
                (settings.chess_username, window),
            ).fetchall()
        )

        if not games:
            return {
                "window": window,
                "games_count": 0,
                "top_weaknesses": [],
                "by_phase": {},
                "openings": [],
                "motifs": [],
                "record": {"win": 0, "loss": 0, "draw": 0},
                "avg_acpl": None,
                "critical_positions": [],
            }

        game_ids = [g["id"] for g in games]
        placeholders = ",".join("?" * len(game_ids))
        issues = rows_to_dicts(
            conn.execute(
                f"""
                SELECT * FROM move_issues
                WHERE game_id IN ({placeholders})
                ORDER BY cpl DESC
                """,
                game_ids,
            ).fetchall()
        )

    record = Counter(g["user_result"] for g in games if g.get("user_result"))
    acpls = [g["acpl"] for g in games if g.get("acpl") is not None]
    avg_acpl = round(sum(acpls) / len(acpls), 1) if acpls else None

    phase_stats: dict[str, dict[str, Any]] = {}
    for phase in ("opening", "middlegame", "endgame"):
        key = f"{phase}_acpl"
        vals = [g[key] for g in games if g.get(key) is not None]
        phase_issues = [i for i in issues if i["phase"] == phase]
        phase_stats[phase] = {
            "avg_acpl": round(sum(vals) / len(vals), 1) if vals else None,
            "blunders": sum(1 for i in phase_issues if i["severity"] == "blunder"),
            "mistakes": sum(1 for i in phase_issues if i["severity"] == "mistake"),
            "inaccuracies": sum(1 for i in phase_issues if i["severity"] == "inaccuracy"),
            "issue_count": len(phase_issues),
        }

    # Openings performance
    opening_map: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"games": 0, "wins": 0, "losses": 0, "draws": 0, "acpl_sum": 0.0, "acpl_n": 0, "eco": None}
    )
    for g in games:
        name = g.get("opening_name") or g.get("opening_eco") or "Unbekannt"
        o = opening_map[name]
        o["games"] += 1
        o["eco"] = g.get("opening_eco")
        if g.get("user_result") == "win":
            o["wins"] += 1
        elif g.get("user_result") == "loss":
            o["losses"] += 1
        elif g.get("user_result") == "draw":
            o["draws"] += 1
        if g.get("acpl") is not None:
            o["acpl_sum"] += g["acpl"]
            o["acpl_n"] += 1

    openings = []
    for name, o in opening_map.items():
        score = (o["wins"] + 0.5 * o["draws"]) / o["games"] if o["games"] else 0
        openings.append(
            {
                "name": name,
                "eco": o["eco"],
                "games": o["games"],
                "wins": o["wins"],
                "losses": o["losses"],
                "draws": o["draws"],
                "score": round(score, 3),
                "avg_acpl": round(o["acpl_sum"] / o["acpl_n"], 1) if o["acpl_n"] else None,
            }
        )
    openings.sort(key=lambda x: (x["score"], -(x["avg_acpl"] or 0)))

    motif_counts = Counter(
        i["motif"] for i in issues if i.get("motif") and i["motif"] != "positional"
    )
    motifs = [{"motif": m, "count": c} for m, c in motif_counts.most_common(8)]

    # Top weaknesses ranking
    weaknesses: list[dict[str, Any]] = []
    total_blunders = sum(g.get("blunders") or 0 for g in games)
    avg_blunders = total_blunders / len(games) if games else 0

    if avg_blunders >= 0.8 or phase_stats["middlegame"]["blunders"] >= 3:
        weaknesses.append(
            {
                "id": "blunder_check",
                "title": "Blunder-Check / Berechnung in Partien",
                "severity": "high" if avg_blunders >= 1.2 else "medium",
                "metric": f"{avg_blunders:.1f} Blunder/Partie, Mittelspiel-Blunder: {phase_stats['middlegame']['blunders']}",
                "why": "Taktik-Puzzles allein reichen nicht — in echten Partien fehlen oft der Blunder-Check und die Umrechnung.",
            }
        )

    end_acpl = phase_stats["endgame"]["avg_acpl"]
    if end_acpl is not None and end_acpl >= 40:
        weaknesses.append(
            {
                "id": "endgames",
                "title": "Endspiele",
                "severity": "high" if end_acpl >= 70 else "medium",
                "metric": f"Endspiel-ACPL {end_acpl}, Fehler: {phase_stats['endgame']['issue_count']}",
                "why": "Viele Punkte gehen verloren, wenn die Partie schon „gewonnen“ oder ausgeglichen wirkt.",
            }
        )

    weak_openings = [o for o in openings if o["games"] >= 2 and o["score"] <= 0.45][:3]
    if weak_openings:
        names = ", ".join(o["name"][:40] for o in weak_openings)
        weaknesses.append(
            {
                "id": "openings",
                "title": "Eröffnungsverständnis (nicht Auswendiglernen)",
                "severity": "medium",
                "metric": f"Schwach: {names}",
                "why": "Fokus auf die 2–3 Eröffnungen mit schlechtester Score/ACPL aus deinen eigenen Partien.",
            }
        )

    if motifs:
        top = motifs[0]
        label = {
            "hanging_piece": "hängende Figuren",
            "missed_tactic": "verpasste Taktiken",
            "positional": "positionelle Fehler",
        }.get(top["motif"], top["motif"])
        weaknesses.append(
            {
                "id": "motifs",
                "title": f"Wiederkehrendes Motiv: {label}",
                "severity": "medium",
                "metric": f"{top['count']}× in den letzten {len(games)} Partien",
                "why": "Dieselben Fehlerquellen tauchen in mehreren Partien wieder auf.",
            }
        )

    # Always include review ritual as lower priority if room
    weaknesses.append(
        {
            "id": "review_ritual",
            "title": "Partie-Review-Ritual",
            "severity": "low",
            "metric": f"{len(games)} analysierte Partien im Fenster",
            "why": "Jede abgeschlossene Daily-Partie innerhalb von 24h reviewen — das bringt mehr als neue Eröffnungstheorie.",
        }
    )

    severity_order = {"high": 0, "medium": 1, "low": 2}
    weaknesses.sort(key=lambda w: severity_order.get(w["severity"], 9))
    top_weaknesses = weaknesses[:5]

    # Critical positions from own blunders
    critical = []
    for i in issues:
        if i["severity"] != "blunder":
            continue
        g = next((x for x in games if x["id"] == i["game_id"]), None)
        critical.append(
            {
                "game_id": i["game_id"],
                "game_url": g["url"] if g else None,
                "ply": i["ply"],
                "move_san": i["move_san"],
                "best_move_san": i["best_move_san"],
                "cpl": i["cpl"],
                "phase": i["phase"],
                "motif": i["motif"],
                "fen_before": i["fen_before"],
                "opening_name": g.get("opening_name") if g else None,
            }
        )
        if len(critical) >= 8:
            break

    return {
        "window": window,
        "games_count": len(games),
        "top_weaknesses": top_weaknesses,
        "by_phase": phase_stats,
        "openings": openings[:10],
        "motifs": motifs,
        "record": {
            "win": record.get("win", 0),
            "loss": record.get("loss", 0),
            "draw": record.get("draw", 0),
        },
        "avg_acpl": avg_acpl,
        "critical_positions": critical,
        "avg_blunders_per_game": round(avg_blunders, 2),
    }
