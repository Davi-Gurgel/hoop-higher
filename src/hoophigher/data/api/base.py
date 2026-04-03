from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from hoophigher.domain.models import GameBoxScore


@runtime_checkable
class StatsProvider(Protocol):
    async def get_games_by_date(self, game_date: date) -> list[GameBoxScore]:
        """Return all games available for a given date."""

    async def get_game_boxscore(self, game_id: str) -> GameBoxScore:
        """Return a single game box score by id."""
