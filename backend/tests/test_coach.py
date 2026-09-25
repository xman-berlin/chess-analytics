import unittest

from app.coach import compose_coach, review_game
from app.leaks import LOST_EARLY, THROWN_DRAW


def _report(focus: str, recent: dict, prior: dict | None = None) -> dict:
    empty = {"games": 0, "thrown_wins": 0, "thrown_draws": 0, "lost_early": 0, "other": 0}
    return {"focus": focus, "recent": recent, "prior": prior or empty}


class CoachTests(unittest.TestCase):
    def test_1400_band_trains_one_leak_and_skips_openings(self) -> None:
        recent = {"games": 20, "thrown_wins": 5, "thrown_draws": 9, "lost_early": 1, "other": 5}
        prior = {"games": 20, "thrown_wins": 9, "thrown_draws": 4, "lost_early": 0, "other": 7}
        plan = compose_coach(
            rating=1415,
            best_rating=1496,
            report=_report(THROWN_DRAW, recent, prior),
            practice_available=9,
            practice_solved=0,
            latest=None,
        )
        self.assertEqual(plan["level_label"], "1400er Daily")
        self.assertEqual(plan["focus"], THROWN_DRAW)
        self.assertIn("nur „Remis verspielt“", plan["diagnosis"])
        self.assertIn("9 Stellungen", plan["tasks"][0]["text"])
        self.assertTrue(any("Eröffnungen" in item for item in plan["withheld"]))
        self.assertIn("von 9 auf 5", plan["progress"])

    def test_lost_early_keeps_opening_work(self) -> None:
        recent = {"games": 20, "thrown_wins": 1, "thrown_draws": 2, "lost_early": 8, "other": 9}
        plan = compose_coach(
            rating=1415,
            best_rating=1496,
            report=_report(LOST_EARLY, recent),
            practice_available=8,
            practice_solved=0,
            latest=None,
        )
        self.assertIn("Eröffnung", plan["tasks"][1]["text"])
        self.assertFalse(any("Eröffnungen" in item for item in plan["withheld"]))

    def test_review_names_the_move(self) -> None:
        review = review_game(
            [
                {
                    "ply": 19,
                    "severity": "blunder",
                    "phase": "opening",
                    "eval_before": -29,
                    "eval_after": -700,
                    "cpl": 673,
                    "move_san": "Bd5",
                    "best_move_san": "Bxf6",
                }
            ],
            {
                "user_color": "white",
                "user_result": "loss",
                "white_username": "TorstenGeise",
                "black_username": "Gegner",
                "opening_name": "Bishops Opening",
            },
        )
        self.assertEqual(review["category"], THROWN_DRAW)
        self.assertEqual(review["ply"], 19)
        self.assertIn("Bd5", review["detail"])
        self.assertIn("Bxf6", review["detail"])
        self.assertIn("Gegner", review["headline"])
        self.assertIn("Remis verspielt", review["headline"])

    def test_a_win_does_not_read_like_a_thrown_draw_result(self) -> None:
        review = review_game(
            [
                {
                    "ply": 25,
                    "severity": "blunder",
                    "phase": "middlegame",
                    "eval_before": 10,
                    "eval_after": -400,
                    "cpl": 410,
                    "move_san": "Bxh7+",
                    "best_move_san": "Re1",
                }
            ],
            {
                "user_color": "white",
                "user_result": "win",
                "white_username": "TorstenGeise",
                "black_username": "AJD28887",
            },
        )
        self.assertEqual(review["category"], THROWN_DRAW)
        self.assertNotIn("Remis verspielt", review["headline"])
        self.assertIn("Sieg", review["headline"])


if __name__ == "__main__":
    unittest.main()
