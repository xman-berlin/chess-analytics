import unittest
from datetime import date, datetime, timedelta, timezone

import chess

from app.week import (
    assign_openings,
    assign_positions,
    in_week,
    is_quiet,
    monday_of,
    opening_verdict,
    position_verdict,
    week_label,
)


class WeekTests(unittest.TestCase):
    def test_monday_and_label(self) -> None:
        friday = date(2026, 9, 25)
        self.assertEqual(monday_of(friday), date(2026, 9, 21))
        self.assertEqual(week_label(date(2026, 9, 21)), "21.–27. September")

    def test_quiet_move_is_not_a_capture_or_check(self) -> None:
        board = chess.Board()
        self.assertTrue(is_quiet(board.fen(), "e4"))
        board.push_san("e4")
        board.push_san("d5")
        self.assertFalse(is_quiet(board.fen(), "exd5"))
        start = chess.Board()
        start.push_san("f3")
        start.push_san("e5")
        start.push_san("g4")
        self.assertFalse(is_quiet(start.fen(), "Qh4"))

    def test_attempt_counts_only_inside_the_berlin_week(self) -> None:
        monday = date(2026, 9, 21)
        late_sunday = datetime(2026, 9, 27, 21, 30, tzinfo=timezone.utc).isoformat()
        next_monday = datetime(2026, 9, 27, 22, 30, tzinfo=timezone.utc).isoformat()
        self.assertTrue(in_week(late_sunday, monday))
        self.assertFalse(in_week(next_monday, monday))
        self.assertFalse(in_week(None, monday))

    def test_repeats_come_before_new_positions(self) -> None:
        repeat = {"game_id": "old", "ply": 30, "cpl": 10}
        fresh = [
            {"game_id": "new", "ply": 40, "cpl": 500},
            {"game_id": "old", "ply": 30, "cpl": 10},
        ]
        chosen = assign_positions(fresh, [repeat], mastered={("gone", 1)}, limit=2)
        self.assertEqual([item["game_id"] for item in chosen], ["old", "new"])

    def test_untrained_line_stays_pinned(self) -> None:
        lines = {
            "white": [{"name": "Vienna", "moves": "1. e4 e5", "trained": False}],
            "black": [{"name": "Modern", "moves": "1. e4 g6", "trained": False}],
        }
        pinned = {"white": {"color": "white", "name": "Caro", "moves": "1. e4 c6", "trained": False}}
        chosen = assign_openings(lines, pinned)
        self.assertEqual(chosen[0]["name"], "Caro")
        self.assertEqual(chosen[1]["name"], "Modern")

    def test_trained_pin_gives_way_to_the_next_line(self) -> None:
        lines = {"white": [{"name": "Vienna", "moves": "1. e4 e5", "trained": False}], "black": []}
        pinned = {"white": {"color": "white", "name": "Caro", "trained": True}}
        chosen = assign_openings(lines, pinned)
        self.assertEqual([item["name"] for item in chosen], ["Vienna"])

    def test_verdicts(self) -> None:
        self.assertEqual(position_verdict(True)[0], "advance")
        self.assertEqual(position_verdict(False)[0], "repeat")
        self.assertEqual(opening_verdict(True)[1], "Nächste Variante")
        self.assertEqual(opening_verdict(False)[1], "Dieselbe Linie")
        self.assertEqual(monday_of(date(2026, 9, 21)) + timedelta(days=6), date(2026, 9, 27))


if __name__ == "__main__":
    unittest.main()
