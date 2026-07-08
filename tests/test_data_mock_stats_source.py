import asyncio
from datetime import date

import pytest

from hoophigher.data.api import MockStatsSource
from hoophigher.domain.models import NBAGame


def test_mock_stats_source_returns_games_by_date() -> None:
    stats_source = MockStatsSource()

    games = asyncio.run(stats_source.get_games_by_date(date(2025, 1, 12)))

    assert len(games) == 5
    assert all(isinstance(game, NBAGame) for game in games)
    assert [game.game_id for game in games] == sorted(game.game_id for game in games)


def test_mock_stats_source_returns_nba_game_by_id() -> None:
    stats_source = MockStatsSource()

    game = asyncio.run(stats_source.get_nba_game("2025-01-12-lal-bos"))

    assert game.game_id == "2025-01-12-lal-bos"
    assert game.source_date == date(2025, 1, 12)
    assert len(game.player_lines) == 10
    assert game.home_team.abbreviation == "LAL"
    assert game.away_team.abbreviation == "BOS"


def test_mock_stats_source_raises_for_unknown_game_id() -> None:
    stats_source = MockStatsSource()

    with pytest.raises(LookupError, match="Mock game not found"):
        asyncio.run(stats_source.get_nba_game("missing-game"))
