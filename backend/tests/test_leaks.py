import unittest

import chess

from app.leaks import (
    LOST_EARLY,
    OTHER,
    THROWN_DRAW,
    THROWN_WIN,
    classify_game,
    san_to_uci,
)


def _issue(**kwargs):
    base = {
        "ply": 30,
        "severity": "blunder",
        "phase": "middlegame",
        "eval_before": 0,
        "eval_after": 0,
        "cpl": 200,
        "fen_before": None,
        "best_move_san": None,
        "move_san": "a3",
    }
    base.update(kwargs)
    return base


class ClassifyGameTests(unittest.TestCase):
    def test_thrown_win_when_clear_advantage_is_given_back(self) -> None:
        result = classify_game([_issue(eval_before=320, eval_after=-40, cpl=360)])
        self.assertEqual(result["category"], THROWN_WIN)
        self.assertEqual(result["issue"]["cpl"], 360)

    def test_mate_score_counts_as_thrown_win(self) -> None:
        result = classify_game([_issue(eval_before=100000, eval_after=-10)])
        self.assertEqual(result["category"], THROWN_WIN)

    def test_kept_advantage_is_not_a_thrown_win(self) -> None:
        result = classify_game([_issue(eval_before=400, eval_after=220, severity="mistake")])
        self.assertEqual(result["category"], OTHER)

    def test_thrown_win_beats_a_later_equal_slip(self) -> None:
        result = classify_game(
            [
                _issue(ply=24, eval_before=20, eval_after=-220),
                _issue(ply=40, eval_before=260, eval_after=10),
            ]
        )
        self.assertEqual(result["category"], THROWN_WIN)
        self.assertEqual(result["issue"]["ply"], 40)

    def test_thrown_draw_from_equal_position(self) -> None:
        result = classify_game([_issue(eval_before=15, eval_after=-240, cpl=255)])
        self.assertEqual(result["category"], THROWN_DRAW)

    def test_lost_early_when_never_equal(self) -> None:
        result = classify_game(
            [
                _issue(ply=12, phase="opening", eval_before=-180, eval_after=-420),
                _issue(ply=36, eval_before=-300, eval_after=-500),
            ]
        )
        self.assertEqual(result["category"], LOST_EARLY)
        self.assertEqual(result["issue"]["ply"], 12)

    def test_inaccuracies_alone_are_ignored(self) -> None:
        result = classify_game([_issue(severity="inaccuracy", eval_before=300, eval_after=-100)])
        self.assertEqual(result["category"], OTHER)
        self.assertIsNone(result["issue"])


class SanUciTests(unittest.TestCase):
    def test_black_pawn_push(self) -> None:
        fen = "1rbq1rk1/p2n1pb1/2pp1npp/4p3/2P1P3/2NBBN1P/PPQ2PP1/R3K2R b KQ - 3 12"
        board = chess.Board(fen)
        self.assertEqual(san_to_uci(fen, "d5"), board.parse_san("d5").uci())
        self.assertEqual(san_to_uci(fen, "d5"), "d6d5")


if __name__ == "__main__":
    unittest.main()
