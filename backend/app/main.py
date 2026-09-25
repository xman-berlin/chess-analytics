from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .chesscom_client import ChessComClient
from .coach import get_coach, review_game
from .config import get_settings
from .db import db, row_to_dict, rows_to_dicts
from .insights import get_insights
from .leaks import get_leak_report, get_quiz, record_quiz_attempt, reset_quiz
from .plan import generate_training_plan, get_training_plan, set_plan_item_completed
from .scheduler import (
    analyze_pipeline,
    full_pipeline,
    is_job_running,
    start_scheduler,
    stop_scheduler,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    db.init()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Chess Analytics", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PlanItemUpdate(BaseModel):
    completed: bool


class QuizAttempt(BaseModel):
    game_id: str
    ply: int
    uci: str


class SettingsUpdate(BaseModel):
    chess_username: str | None = None
    time_classes: str | None = None
    sync_interval_hours: int | None = None


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/status")
def status() -> dict[str, Any]:
    with db.connect() as conn:
        sync = row_to_dict(conn.execute("SELECT * FROM sync_state WHERE id = 1").fetchone())
        total_games = conn.execute("SELECT COUNT(*) AS c FROM games").fetchone()["c"]
        analyzed = conn.execute(
            "SELECT COUNT(*) AS c FROM games WHERE analyzed = 1"
        ).fetchone()["c"]
    player = None
    stats = None
    try:
        client = ChessComClient(settings.chess_username)
        player = client.get_player()
        stats = client.get_stats()
    except Exception:
        pass

    daily = (stats or {}).get("chess_daily") or {}
    return {
        "username": settings.chess_username,
        "time_classes": settings.time_class_list,
        "sync": sync,
        "job_running": is_job_running(),
        "totals": {"games": total_games, "analyzed": analyzed},
        "player": {
            "avatar": (player or {}).get("avatar"),
            "name": (player or {}).get("name"),
            "url": (player or {}).get("url"),
        },
        "rating": {
            "daily": (daily.get("last") or {}).get("rating"),
            "daily_best": (daily.get("best") or {}).get("rating"),
            "record": daily.get("record"),
        },
        "tactics": (stats or {}).get("tactics"),
    }


@app.post("/api/sync")
def trigger_sync(full: bool = False, background: bool = True) -> dict[str, Any]:
    if is_job_running():
        raise HTTPException(409, "Ein Sync/Analyse-Job läuft bereits")

    if background:
        def run() -> None:
            try:
                full_pipeline(force_sync_full=full)
            except Exception:
                pass

        threading.Thread(target=run, daemon=True).start()
        return {"status": "started", "message": "Sync und Analyse gestartet"}

    return full_pipeline(force_sync_full=full)


@app.post("/api/analyze")
def trigger_analyze(limit: int | None = None, background: bool = True) -> dict[str, Any]:
    if is_job_running():
        raise HTTPException(409, "Ein Job läuft bereits")

    if background:
        def run() -> None:
            try:
                analyze_pipeline(limit=limit)
            except Exception:
                pass

        threading.Thread(target=run, daemon=True).start()
        return {"status": "started"}

    return analyze_pipeline(limit=limit)


@app.get("/api/games")
def list_games(
    analyzed_only: bool = False,
    result: str | None = Query(None, pattern="^(win|loss|draw)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    clauses = ["username = ?"]
    params: list[Any] = [settings.chess_username]
    if analyzed_only:
        clauses.append("analyzed = 1")
    if result:
        clauses.append("user_result = ?")
        params.append(result)

    where = " AND ".join(clauses)
    with db.connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM games WHERE {where}", params
        ).fetchone()["c"]
        rows = rows_to_dicts(
            conn.execute(
                f"""
                SELECT g.id, g.url, g.time_class, g.white_username, g.black_username,
                       g.white_rating, g.black_rating, g.user_color, g.user_result,
                       g.opening_eco, g.opening_name, g.end_time, g.analyzed,
                       a.acpl, a.blunders, a.mistakes, a.inaccuracies
                FROM games g
                LEFT JOIN analyses a ON a.game_id = g.id
                WHERE {where}
                ORDER BY g.end_time DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        )
    return {"total": total, "items": rows}


@app.get("/api/games/{game_id}")
def get_game(game_id: str) -> dict[str, Any]:
    with db.connect() as conn:
        game = row_to_dict(
            conn.execute(
                """
                SELECT g.*, a.acpl, a.blunders, a.mistakes, a.inaccuracies,
                       a.opening_acpl, a.middlegame_acpl, a.endgame_acpl,
                       a.analyzed_at, a.engine_depth
                FROM games g
                LEFT JOIN analyses a ON a.game_id = g.id
                WHERE g.id = ?
                """,
                (game_id,),
            ).fetchone()
        )
        if not game:
            raise HTTPException(404, "Partie nicht gefunden")
        # Don't dump huge pgn twice in list views — keep for detail
        issues = rows_to_dicts(
            conn.execute(
                "SELECT * FROM move_issues WHERE game_id = ? ORDER BY ply",
                (game_id,),
            ).fetchall()
        )
    return {"game": game, "issues": issues, "review": review_game(issues, game)}


@app.get("/api/insights")
def insights(window: int = Query(40, ge=5, le=100)) -> dict[str, Any]:
    return get_insights(window)


@app.get("/api/leaks")
def leaks(window: int = Query(20, ge=5, le=40)) -> dict[str, Any]:
    return get_leak_report(window)


@app.get("/api/coach")
def coach() -> dict[str, Any]:
    return get_coach()


@app.get("/api/quiz")
def quiz(window: int = Query(20, ge=5, le=40)) -> dict[str, Any]:
    return get_quiz(window)


@app.post("/api/quiz/attempts")
def quiz_attempt(body: QuizAttempt) -> dict[str, Any]:
    result = record_quiz_attempt(body.game_id, body.ply, body.uci.strip())
    if result.get("error") == "not_found":
        raise HTTPException(404, "Stellung nicht gefunden")
    if result.get("error") == "illegal":
        raise HTTPException(400, "Zug ist in dieser Stellung nicht legal")
    if result.get("error"):
        raise HTTPException(400, "Stellung kann nicht geübt werden")
    return result


@app.post("/api/quiz/reset")
def quiz_reset() -> dict[str, str]:
    reset_quiz()
    return {"status": "reset"}


@app.get("/api/plan")
def plan() -> dict[str, Any]:
    existing = get_training_plan()
    if existing:
        return existing
    # Generate if we have analyses
    with db.connect() as conn:
        n = conn.execute(
            "SELECT COUNT(*) AS c FROM games WHERE analyzed = 1"
        ).fetchone()["c"]
    if n == 0:
        return {"generated_at": None, "items": [], "message": "Noch keine Analysen — bitte syncen."}
    return generate_training_plan()


@app.post("/api/plan/refresh")
def refresh_plan() -> dict[str, Any]:
    return generate_training_plan()


@app.patch("/api/plan/items/{item_id}")
def update_plan_item(item_id: str, body: PlanItemUpdate) -> dict[str, Any]:
    set_plan_item_completed(item_id, body.completed)
    return {"id": item_id, "completed": body.completed}


@app.get("/api/settings")
def get_app_settings() -> dict[str, Any]:
    return {
        "chess_username": settings.chess_username,
        "time_classes": settings.time_classes,
        "time_class_list": settings.time_class_list,
        "sync_interval_hours": settings.sync_interval_hours,
        "analysis_depth": settings.analysis_depth,
        "analysis_limit": settings.analysis_limit,
        "stockfish_path": settings.stockfish_path,
    }
