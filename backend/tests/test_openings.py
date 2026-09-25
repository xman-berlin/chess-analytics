import unittest

from app.openings import (
    build_opening_report,
    format_moves,
    majority_moves,
    move_number,
    split_opening,
    worth_chessly,
)


def _game(
    game_id: str,
    name: str,
    color: str = "white",
    result: str = "loss",
    url: str | None = None,
    moves: list[str] | None = None,
) -> dict:
    return {
        "id": game_id,
        "opening_name": name,
        "user_color": color,
        "user_result": result,
        "url": url,
        "moves": moves or [],
    }


def _issue(game_id: str, ply: int, san: str, best: str, severity: str = "blunder") -> dict:
    return {
        "game_id": game_id,
        "ply": ply,
        "move_san": san,
        "best_move_san": best,
        "severity": severity,
        "phase": "opening",
    }


class OpeningReportTests(unittest.TestCase):
    def test_split_keeps_variation_and_strips_move_order(self) -> None:
        family, variation = split_opening("Vienna Game Falkbeer Vienna Gambit 3...d6 4.Nf3")
        self.assertEqual(family, "Vienna Game Falkbeer Vienna Gambit")
        self.assertEqual(variation, "3...d6 4.Nf3")
        self.assertEqual(split_opening("French Defense")[1], None)
        self.assertEqual(move_number(13), 7)
        self.assertEqual(
            format_moves(majority_moves([["e4", "e5", "Nc3", "Nf6", "f4", "exf4"], ["e4", "e5", "Nc3", "Nf6", "f4", "Nc6"]])),
            "1. e4 e5 2. Nc3 Nf6 3. f4",
        )
        transposed = [
            ["e4", "e6", "d4", "d5", "e5", "c5"],
            ["e4", "e6", "d4", "d5", "e5", "c5"],
            ["d4", "e6", "e4", "d5", "e5", "c5"],
        ]
        self.assertEqual(format_moves(majority_moves(transposed)), "1. e4 e6 2. d4 d5 3. e5 c5")

    def test_groups_branches_and_names_the_move(self) -> None:
        games = [
            _game("a", "Vienna Game Falkbeer Vienna Gambit", result="win"),
            _game("b", "Vienna Game Falkbeer Vienna Gambit 3...d6 4.Nf3"),
            _game("c", "French Defense Normal Variation 2...d5", color="black"),
            _game("d", "Italian Game"),
        ]
        issues = [
            _issue("b", 13, "Bb3", "Nxb5"),
            _issue("c", 16, "Be7", "Qa5+", severity="mistake"),
            _issue("a", 9, "a3", "Nf3", severity="inaccuracy"),
        ]
        report = build_opening_report(games, issues)
        self.assertIn("Zug 7", report["summary"])
        white = report["colors"][0]
        self.assertEqual(white["label"], "Weiß")
        vienna = white["lines"][0]
        self.assertEqual(vienna["name"], "Vienna Game Falkbeer Vienna Gambit")
        self.assertEqual(vienna["games"], 2)
        self.assertEqual(vienna["serious"], 1)
        self.assertEqual(vienna["inaccuracies"], 1)
        self.assertEqual(vienna["faults"][0]["slips"][0]["move_number"], 7)
        self.assertIn("Zug 7", vienna["when"])
        black = report["colors"][1]
        self.assertEqual(black["lines"][0]["faults"][0]["slips"][0]["move_san"], "Be7")
        names = [line["name"] for line in white["lines"]]
        self.assertNotIn("Italian Game", names)

    def test_keeps_a_single_game_when_it_has_a_blunder(self) -> None:
        report = build_opening_report(
            [_game("a", "Caro Kann Defense Advance Tal Variation")],
            [_issue("a", 19, "Bd5", "Bxf6")],
        )
        line = report["colors"][0]["lines"][0]
        self.assertEqual(line["games"], 1)
        self.assertEqual(line["faults"][0]["slips"][0]["move_number"], 10)
        self.assertIn("Zug 10", report["summary"])

    def test_slips_from_one_game_stay_together(self) -> None:
        report = build_opening_report(
            [_game("a", "Vienna Game", url="https://www.chess.com/game/daily/1")],
            [
                _issue("a", 9, "d4", "Nf3", severity="mistake"),
                _issue("a", 15, "Bb3", "O-O"),
            ],
        )
        faults = report["colors"][0]["lines"][0]["faults"]
        self.assertEqual(len(faults), 1)
        self.assertEqual([slip["move_number"] for slip in faults[0]["slips"]], [5, 8])
        self.assertEqual(faults[0]["url"], "https://www.chess.com/game/daily/1")
        self.assertEqual(faults[0]["ply"], 9)

    def test_chessly_skips_a_trained_line_and_a_short_one(self) -> None:
        self.assertFalse(worth_chessly(3, "1. e4 e6"))
        self.assertTrue(worth_chessly(3, "1. e4 e5 2. Nc3 Nf6"))
        long = ["e4", "e5", "Nc3", "Nf6", "f4"]
        short = ["e4", "e6"]
        games = [
            _game("a", "Vienna Game", moves=long),
            _game("b", "Vienna Game", moves=long),
            _game("c", "French Defense", moves=short),
            _game("d", "French Defense", moves=short),
            _game("e", "Modern Defense", moves=["e4", "g6", "d4", "Bg7", "c3", "d6"]),
            _game("f", "Modern Defense", moves=["e4", "g6", "d4", "Bg7", "c3", "d6"], color="black"),
        ]
        # Modern as white is one game; the black one is a different color bucket.
        report = build_opening_report(
            games,
            [_issue("a", 9, "d4", "Nf3", severity="mistake")],
            trained={("white", "Vienna Game")},
            days=90,
        )
        white = report["colors"][0]
        self.assertEqual(white["done"][0]["name"], "Vienna Game")
        self.assertEqual(white["recommend"], [])
        self.assertEqual(report["days"], 90)
