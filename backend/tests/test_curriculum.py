import unittest

from app.curriculum import build_curriculum
from app.leaks import LOST_EARLY, THROWN_DRAW, THROWN_WIN


class CurriculumTests(unittest.TestCase):
    def test_thrown_draw_weights_tactics_not_openings(self) -> None:
        plan = build_curriculum(THROWN_DRAW, rating=1415, practice_available=9)
        by_id = {area["id"]: area for area in plan["areas"]}
        self.assertTrue(by_id["tactics"]["emphasis"])
        self.assertTrue(by_id["calculation"]["emphasis"])
        self.assertFalse(by_id["openings"]["emphasis"])
        self.assertEqual(len(plan["week"]), 7)
        self.assertIn("9", by_id["tactics"]["sessions"][0]["text"])
        self.assertIn("Remis verspielt", plan["intro"])

    def test_lost_early_weights_openings(self) -> None:
        plan = build_curriculum(LOST_EARLY, rating=1415, practice_available=4)
        by_id = {area["id"]: area for area in plan["areas"]}
        self.assertTrue(by_id["openings"]["emphasis"])
        self.assertFalse(by_id["tactics"]["emphasis"])

    def test_thrown_win_includes_endgames(self) -> None:
        plan = build_curriculum(THROWN_WIN, rating=1415)
        by_id = {area["id"]: area for area in plan["areas"]}
        self.assertTrue(by_id["tactics"]["emphasis"])
        self.assertTrue(by_id["endgames"]["emphasis"])


if __name__ == "__main__":
    unittest.main()
