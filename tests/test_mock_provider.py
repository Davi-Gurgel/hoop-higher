import asyncio
from datetime import date

import pytest

from hoophigher.data.api import MockProvider, StatsProvider
from hoophigher.domain.models import GameBoxScore


def test_mock_provider_satisfies_provider_protocol() -> None:
    provider = MockProvider()

    assert isinstance(provider, StatsProvider)


def test_mock_provider_returns_games_by_date() -> None:
    provider = MockProvider()

    games = asyncio.run(provider.get_games_by_date(date(2025, 1, 12)))

    assert len(games) == 5
    assert all(isinstance(game, GameBoxScore) for game in games)
    assert [game.game_id for game in games] == sorted(game.game_id for game in games)


def test_mock_provider_returns_game_boxscore_by_id() -> None:
    provider = MockProvider()

    game = asyncio.run(provider.get_game_boxscore("2025-01-12-lal-bos"))

    assert game.game_id == "2025-01-12-lal-bos"
    assert game.game_date == date(2025, 1, 12)
    assert len(game.player_lines) == 6
    assert game.home_team.abbreviation == "LAL"
    assert game.away_team.abbreviation == "BOS"


def test_mock_provider_raises_for_unknown_game_id() -> None:
    provider = MockProvider()

    with pytest.raises(LookupError, match="Mock game not found"):
        asyncio.run(provider.get_game_boxscore("missing-game"))
