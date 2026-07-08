from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from hoophigher.domain.models import NBAGame


@runtime_checkable
class StatsSource(Protocol):
    async def get_games_by_date(self, source_date: date) -> list[NBAGame]:
        """Return all games available for a given source date."""

    async def get_nba_game(
        self,
        game_id: str,
        *,
        source_date_fallback: date | None = None,
    ) -> NBAGame:
        """Return a single NBA game by id."""
