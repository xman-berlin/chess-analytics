from __future__ import annotations

import re
from typing import Any

import httpx

USER_AGENT = "ChessAnalytics/1.0 (local training app; contact: local)"


class ChessComClient:
    BASE = "https://api.chess.com/pub"

    def __init__(self, username: str, timeout: float = 30.0) -> None:
        self.username = username.lower()
        self.timeout = timeout
        self._headers = {"User-Agent": USER_AGENT}

    def _get(self, url: str) -> Any:
        with httpx.Client(timeout=self.timeout, headers=self._headers) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()

    def get_player(self) -> dict[str, Any]:
        return self._get(f"{self.BASE}/player/{self.username}")

    def get_stats(self) -> dict[str, Any]:
        return self._get(f"{self.BASE}/player/{self.username}/stats")

    def get_archives(self) -> list[str]:
        data = self._get(f"{self.BASE}/player/{self.username}/games/archives")
        return list(data.get("archives", []))

    def get_games_for_archive(self, archive_url: str) -> list[dict[str, Any]]:
        data = self._get(archive_url)
        return list(data.get("games", []))


def parse_pgn_headers(pgn: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for match in re.finditer(r'^\[(\w+)\s+"([^"]*)"\]', pgn, re.MULTILINE):
        headers[match.group(1)] = match.group(2)
    return headers


def extract_opening(pgn: str) -> tuple[str | None, str | None]:
    headers = parse_pgn_headers(pgn)
    eco = headers.get("ECO")
    name = headers.get("Opening") or headers.get("ECOUrl")
    if name and "chess.com/openings/" in name:
        # ECOUrl often looks like https://www.chess.com/openings/Sicilian-Defense-...
        slug = name.rstrip("/").split("/")[-1]
        name = slug.replace("-", " ")
    return eco, name


def is_coach_game(pgn: str, white: str | None = None, black: str | None = None) -> bool:
    if '[Event "Play vs Coach"]' in (pgn or ""):
        return True
    for name in (white, black):
        if name and name.lower().startswith("coach-"):
            return True
    return False


def public_game_url(url: str, pgn: str, uuid: str | None) -> str:
    """Coach games reuse a daily id that belongs to someone else's game.

    Chess.com's numeric /game/daily/{id} link then opens the wrong game.
    The same id as a UUID opens the coach game.
    """
    if uuid and '[Event "Play vs Coach"]' in (pgn or ""):
        return f"https://www.chess.com/game/daily/{uuid}"
    return url


def game_id_from_url(url: str) -> str:
    # https://www.chess.com/game/daily/123 -> daily-123
    parts = url.rstrip("/").split("/")
    if len(parts) >= 2:
        return f"{parts[-2]}-{parts[-1]}"
    return url
