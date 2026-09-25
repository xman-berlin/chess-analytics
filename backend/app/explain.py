from __future__ import annotations

import chess
import chess.engine

from .config import get_settings

_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}

_ACCUSATIVE = {
    chess.PAWN: "den Bauern",
    chess.KNIGHT: "den Springer",
    chess.BISHOP: "den Läufer",
    chess.ROOK: "den Turm",
    chess.QUEEN: "die Dame",
    chess.KING: "den König",
}


def _material(board: chess.Board, color: chess.Color) -> int:
    total = 0
    for piece in board.piece_map().values():
        value = _VALUES.get(piece.piece_type, 0)
        total += value if piece.color == color else -value
    return total


def _captured(board: chess.Board, move: chess.Move) -> chess.Piece | None:
    if board.is_en_passant(move):
        return chess.Piece(chess.PAWN, not board.turn)
    return board.piece_at(move.to_square)


def _clause(board: chess.Board, move: chess.Move) -> str:
    san = board.san(move)
    captured = _captured(board, move)
    check = board.gives_check(move)
    if captured and check:
        return f"{san} schlägt {_ACCUSATIVE[captured.piece_type]} und gibt Schach"
    if captured:
        return f"{san} schlägt {_ACCUSATIVE[captured.piece_type]}"
    if check:
        return f"{san} gibt Schach"
    if move.promotion:
        return f"{san} wandelt um"
    return san


def describe_line(board: chess.Board, moves: list[chess.Move], player: chess.Color) -> str:
    """Describe the forcing captures and checks, plus the material result for ``player``."""
    if not moves:
        return ""
    start = _material(board, player)
    tmp = board.copy(stack=False)
    clauses: list[str] = []
    for index, move in enumerate(moves[:6]):
        if move not in tmp.legal_moves:
            break
        tactical = bool(_captured(tmp, move) or tmp.gives_check(move) or move.promotion)
        if index > 0 and not tactical:
            break
        clauses.append(_clause(tmp, move))
        tmp.push(move)
        if sum("schlägt" in clause or "Schach" in clause for clause in clauses) >= 4:
            break
    if not clauses:
        return ""
    if len(clauses) == 1 and "schlägt" not in clauses[0] and "Schach" not in clauses[0]:
        return ""
    sentence = clauses[0]
    if len(clauses) > 1:
        sentence += ", danach " + clauses[1]
    if len(clauses) > 2:
        sentence += ", dann " + ", ".join(clauses[2:])
    delta = _material(tmp, player) - start
    if tmp.is_checkmate():
        sentence += ". Das ist Matt"
    elif delta <= -1:
        sentence += f". Das kostet {_loss_phrase(-delta)}"
    elif delta >= 1:
        sentence += f". Das gewinnt {_loss_phrase(delta)}"
    return sentence


def _loss_phrase(points: int) -> str:
    if points == 1:
        return "einen Bauern"
    if points == 2:
        return "zwei Bauern"
    if points == 3:
        return "eine Leichtfigur"
    if points == 5:
        return "einen Turm"
    if points == 6:
        return "zwei Leichtfiguren"
    if points >= 9:
        return "die Dame"
    return f"etwa {points} Bauern"


def _fmt_eval(cp: float | None) -> str | None:
    if cp is None:
        return None
    if abs(cp) >= 90000:
        return "Matt" if cp > 0 else "−Matt"
    pawns = cp / 100
    text = f"{pawns:+.1f}"
    return text.replace("+", "").replace("-", "−") if pawns < 0 else text


def _pv_after(engine: chess.engine.SimpleEngine, board: chess.Board) -> list[chess.Move]:
    info = engine.analyse(board, chess.engine.Limit(depth=12, time=0.6))
    return list(info.get("pv") or [])


def explain_position(
    fen: str,
    played_san: str | None,
    best_san: str,
    eval_before: float | None = None,
    eval_after: float | None = None,
) -> str:
    board = chess.Board(fen)
    player = board.turn
    before = _fmt_eval(eval_before)
    after = _fmt_eval(eval_after)
    eval_sentence = ""
    if eval_after is not None and eval_after <= -90000:
        eval_sentence = "Danach steht Matt."
    elif eval_before is not None and eval_before >= 90000 and after:
        eval_sentence = f"Statt Matt bleibt {after}."
    elif before and after:
        eval_sentence = f"Die Bewertung geht von {before} auf {after}."

    try:
        best_move = board.parse_san(best_san)
    except ValueError:
        return eval_sentence or f"{best_san} ist der Zug, der die Stellung hält."

    settings = get_settings()
    good = ""
    bad = ""
    best_is_tactical = bool(
        board.is_capture(best_move) or board.gives_check(best_move) or best_move.promotion
    )
    try:
        engine = chess.engine.SimpleEngine.popen_uci(settings.stockfish_path)
        try:
            if best_is_tactical:
                after_best = board.copy(stack=False)
                after_best.push(best_move)
                good_moves = [best_move, *_pv_after(engine, after_best)]
                good = describe_line(board, good_moves, player)
            if played_san and played_san != best_san:
                try:
                    played_move = board.parse_san(played_san)
                except ValueError:
                    played_move = None
                if played_move is not None:
                    after_played = board.copy(stack=False)
                    after_played.push(played_move)
                    bad = describe_line(after_played, _pv_after(engine, after_played), player)
        finally:
            engine.quit()
    except (chess.engine.EngineError, FileNotFoundError, OSError):
        good = ""
        bad = ""

    parts: list[str] = []
    if good:
        parts.append(good + ".")
    elif before:
        parts.append(f"{best_san} hält die Stellung bei {before}.")
    if played_san and played_san != best_san and bad:
        parts.append(f"{played_san} lässt zu: {bad}.")
    elif played_san and played_san != best_san and after:
        parts.append(f"{played_san} verschlechtert die Stellung auf {after}.")
    if eval_sentence and eval_sentence not in " ".join(parts):
        parts.append(eval_sentence)
    if not parts:
        return f"{best_san} ist der Zug, der die Stellung hält."
    return " ".join(parts)
