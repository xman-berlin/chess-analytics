from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import chess
import chess.engine
import chess.pgn
from io import StringIO

from .config import get_settings
from .db import db


# Centipawn loss thresholds (from player's perspective)
INACCURACY_CP = 50
MISTAKE_CP = 100
BLUNDER_CP = 200


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _score_to_cp(score: chess.engine.PovScore, pov: chess.Color) -> float:
    s = score.pov(pov)
    if s.is_mate():
        mate = s.mate()
        if mate is None:
            return 0.0
        # Large CP proxy for mate
        return 100000.0 if mate > 0 else -100000.0
    cp = s.score(mate_score=100000)
    return float(cp or 0)


def _phase(board: chess.Board, ply: int) -> str:
    if ply < 20:
        return "opening"
    # Rough phase by piece count (excluding kings)
    non_king = len(board.piece_map()) - 2
    if non_king <= 6:
        return "endgame"
    return "middlegame"


def _classify_motif(board_before: chess.Board, move: chess.Move, cpl: float) -> str | None:
    if cpl < MISTAKE_CP:
        return None
    # Hanging piece heuristic: moved piece can be captured for free or lost material
    try:
        board = board_before.copy(stack=False)
        if move.to_square in board_before.piece_map():
            # capture that might be bad
            pass
        board.push(move)
        # If opponent can capture the moved piece and we don't recapture equally
        attackers = board.attackers(not board_before.turn, move.to_square)
        if attackers and board.piece_at(move.to_square):
            defenders = board.attackers(board_before.turn, move.to_square)
            piece = board.piece_at(move.to_square)
            if piece and piece.piece_type != chess.PAWN and len(defenders) == 0:
                return "hanging_piece"
    except Exception:
        pass

    # Back rank mate threat ignored often — cheap check
    if board_before.is_check() is False:
        pass

    if cpl >= BLUNDER_CP:
        return "missed_tactic"
    return None


def analyze_game(game_id: str, pgn_text: str, user_color: str, depth: int | None = None) -> dict[str, Any]:
    settings = get_settings()
    depth = depth or settings.analysis_depth
    pov = chess.WHITE if user_color == "white" else chess.BLACK

    game = chess.pgn.read_game(StringIO(pgn_text))
    if game is None:
        raise ValueError(f"Ungültige PGN für {game_id}")

    board = game.board()
    engine = chess.engine.SimpleEngine.popen_uci(settings.stockfish_path)

    issues: list[dict[str, Any]] = []
    cpl_by_phase: dict[str, list[float]] = {
        "opening": [],
        "middlegame": [],
        "endgame": [],
    }
    all_cpl: list[float] = []
    counts = {"blunder": 0, "mistake": 0, "inaccuracy": 0}

    try:
        ply = 0
        node = game
        while node.variations:
            next_node = node.variation(0)
            move = next_node.move
            ply += 1
            is_user_move = board.turn == pov

            if is_user_move:
                info_before = engine.analyse(board, chess.engine.Limit(depth=depth))
                best = info_before.get("pv", [None])[0]
                eval_before = _score_to_cp(info_before["score"], pov)

                board_before = board.copy(stack=False)
                san = board.san(move)
                best_san = board.san(best) if best else None
                board.push(move)

                info_after = engine.analyse(board, chess.engine.Limit(depth=depth))
                eval_after = _score_to_cp(info_after["score"], pov)

                # Loss from player's POV: drop in evaluation
                cpl = max(0.0, eval_before - eval_after)
                # Cap extreme mate swings for ACPL
                cpl_capped = min(cpl, 1000.0)
                phase = _phase(board_before, ply)
                all_cpl.append(cpl_capped)
                cpl_by_phase[phase].append(cpl_capped)

                severity = None
                if cpl >= BLUNDER_CP:
                    severity = "blunder"
                elif cpl >= MISTAKE_CP:
                    severity = "mistake"
                elif cpl >= INACCURACY_CP:
                    severity = "inaccuracy"

                if severity:
                    counts[severity] = counts.get(severity, 0) + 1
                    issues.append(
                        {
                            "ply": ply,
                            "move_san": san,
                            "severity": severity,
                            "phase": phase,
                            "cpl": round(cpl_capped, 1),
                            "eval_before": round(eval_before, 1),
                            "eval_after": round(eval_after, 1),
                            "best_move_san": best_san,
                            "motif": _classify_motif(board_before, move, cpl),
                            "fen_before": board_before.fen(),
                        }
                    )
            else:
                board.push(move)

            node = next_node
    finally:
        engine.quit()

    def avg(xs: list[float]) -> float | None:
        return round(sum(xs) / len(xs), 1) if xs else None

    return {
        "acpl": avg(all_cpl),
        "blunders": counts["blunder"],
        "mistakes": counts["mistake"],
        "inaccuracies": counts["inaccuracy"],
        "opening_acpl": avg(cpl_by_phase["opening"]),
        "middlegame_acpl": avg(cpl_by_phase["middlegame"]),
        "endgame_acpl": avg(cpl_by_phase["endgame"]),
        "engine_depth": depth,
        "issues": issues,
    }


def analyze_pending(limit: int | None = None) -> dict[str, Any]:
    settings = get_settings()
    limit = limit or settings.analysis_limit

    with db.connect() as conn:
        conn.execute(
            "UPDATE sync_state SET status = ?, message = ? WHERE id = 1",
            ("analyzing", "Partien werden mit Stockfish analysiert…"),
        )
        # Prefer newest unanalyzed games, limited to analysis_limit total analyzed window
        analyzed_count = conn.execute(
            "SELECT COUNT(*) AS c FROM games WHERE analyzed = 1"
        ).fetchone()["c"]

        if analyzed_count == 0:
            # First run: only newest `limit` games
            rows = conn.execute(
                """
                SELECT id, pgn, user_color FROM games
                WHERE analyzed = 0 AND user_color IS NOT NULL
                ORDER BY end_time DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        else:
            # Incremental: analyze new games, but also allow filling up to limit
            rows = conn.execute(
                """
                SELECT id, pgn, user_color FROM games
                WHERE analyzed = 0 AND user_color IS NOT NULL
                ORDER BY end_time DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    done = 0
    errors: list[str] = []

    for row in rows:
        try:
            result = analyze_game(row["id"], row["pgn"], row["user_color"])
            with db.connect() as conn:
                conn.execute("DELETE FROM move_issues WHERE game_id = ?", (row["id"],))
                conn.execute(
                    """
                    INSERT OR REPLACE INTO analyses (
                        game_id, acpl, blunders, mistakes, inaccuracies,
                        opening_acpl, middlegame_acpl, endgame_acpl,
                        analyzed_at, engine_depth
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["id"],
                        result["acpl"],
                        result["blunders"],
                        result["mistakes"],
                        result["inaccuracies"],
                        result["opening_acpl"],
                        result["middlegame_acpl"],
                        result["endgame_acpl"],
                        _utcnow(),
                        result["engine_depth"],
                    ),
                )
                for issue in result["issues"]:
                    conn.execute(
                        """
                        INSERT INTO move_issues (
                            game_id, ply, move_san, severity, phase, cpl,
                            eval_before, eval_after, best_move_san, motif, fen_before
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row["id"],
                            issue["ply"],
                            issue["move_san"],
                            issue["severity"],
                            issue["phase"],
                            issue["cpl"],
                            issue["eval_before"],
                            issue["eval_after"],
                            issue["best_move_san"],
                            issue["motif"],
                            issue["fen_before"],
                        ),
                    )
                conn.execute(
                    "UPDATE games SET analyzed = 1 WHERE id = ?", (row["id"],)
                )
            done += 1
        except Exception as exc:
            errors.append(f"{row['id']}: {exc}")

    with db.connect() as conn:
        total_analyzed = conn.execute(
            "SELECT COUNT(*) AS c FROM games WHERE analyzed = 1"
        ).fetchone()["c"]
        msg = f"Analyse fertig: {done} Partien"
        if errors:
            msg += f" ({len(errors)} Fehler)"
        conn.execute(
            """
            UPDATE sync_state
            SET last_analysis_at = ?, games_analyzed = ?, status = ?, message = ?
            WHERE id = 1
            """,
            (_utcnow(), total_analyzed, "idle", msg),
        )

    return {"analyzed": done, "errors": errors, "total_analyzed": total_analyzed}
