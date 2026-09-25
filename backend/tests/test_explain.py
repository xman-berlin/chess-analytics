import unittest

import chess

from app.explain import describe_line, explain_position


class DescribeLineTests(unittest.TestCase):
    def test_bad_bishop_move_loses_a_piece(self) -> None:
        fen = "r1bq1rk1/2p1bpp1/p1np1n1p/1p2pP2/2B1P2B/2NP3P/PPP3P1/R2QK1NR w KQ - 0 10"
        board = chess.Board(fen)
        board.push_san("Bd5")
        moves = []
        cursor = board.copy(stack=False)
        for san in ("Nxd5", "Bxe7", "Ndxe7"):
            move = cursor.parse_san(san)
            moves.append(move)
            cursor.push(move)
        text = describe_line(board, moves, chess.WHITE)
        self.assertIn("Nxd5 schlägt den Läufer", text)
        self.assertIn("eine Leichtfigur", text)

    def test_trade_on_f6_does_not_claim_a_free_piece(self) -> None:
        fen = "r1bq1rk1/2p1bpp1/p1np1n1p/1p2pP2/2B1P2B/2NP3P/PPP3P1/R2QK1NR w KQ - 0 10"
        board = chess.Board(fen)
        first = board.parse_san("Bxf6")
        after = board.copy(stack=False)
        after.push(first)
        recapture = after.parse_san("Bxf6")
        text = describe_line(board, [first, recapture], chess.WHITE)
        self.assertIn("Bxf6 schlägt den Springer", text)
        self.assertNotIn("kostet", text)
        self.assertNotIn("gewinnt", text)


class ExplainPositionTests(unittest.TestCase):
    def test_sample_blunder_names_the_tactic_and_the_eval(self) -> None:
        fen = "r1bq1rk1/2p1bpp1/p1np1n1p/1p2pP2/2B1P2B/2NP3P/PPP3P1/R2QK1NR w KQ - 0 10"
        text = explain_position(fen, "Bd5", "Bxf6", eval_before=-29, eval_after=-702)
        self.assertIn("Bxf6", text)
        self.assertIn("Springer", text)
        self.assertIn("Bd5", text)
        self.assertIn("−0.3", text)
        self.assertIn("−7.0", text)


if __name__ == "__main__":
    unittest.main()
