import unittest

from app.chesscom_client import is_coach_game, public_game_url


class PublicGameUrlTests(unittest.TestCase):
    def test_coach_game_uses_uuid_because_the_daily_id_is_someone_elses(self) -> None:
        url = public_game_url(
            "https://www.chess.com/game/daily/231299526",
            '[Event "Play vs Coach"]\n',
            "0995bfa6-a9c7-11f1-a08d-3ffc6bed9bb3",
        )
        self.assertEqual(
            url,
            "https://www.chess.com/game/daily/0995bfa6-a9c7-11f1-a08d-3ffc6bed9bb3",
        )

    def test_coach_games_are_recognized(self) -> None:
        self.assertTrue(is_coach_game('[Event "Play vs Coach"]\n', "Coach-David", "TorstenGeise"))
        self.assertTrue(is_coach_game("", "TorstenGeise", "Coach-Mae"))
        self.assertFalse(is_coach_game('[Event "Let\'s Play!"]\n', "TorstenGeise", "Someone"))

    def test_regular_daily_game_keeps_its_url(self) -> None:
        original = "https://www.chess.com/game/daily/1021965386"
        self.assertEqual(
            public_game_url(original, '[Event "Let\'s Play!"]\n', "some-uuid"),
            original,
        )
