from __future__ import annotations

import asyncio
import importlib
from datetime import date

import pytest
from pydantic import ValidationError

import hoophigher.app as app_module
import hoophigher.config as config_module
from hoophigher.data import CacheRepository, create_sqlite_engine, session_scope
from hoophigher.data.api import MockProvider, NBAApiProvider
from hoophigher.domain.enums import GameMode
from hoophigher.domain.models import GameBoxScore, PlayerLine, TeamGameInfo
from hoophigher.services import GameplaySnapshot


def _reload_app_module() -> None:
    importlib.reload(config_module)
    importlib.reload(app_module)


def test_settings_defaults_to_nba_api_provider(monkeypatch) -> None:
    monkeypatch.delenv("HOOPHIGHER_STATS_PROVIDER", raising=False)

    values = config_module.Settings()

    assert values.stats_provider == "nba_api"


def test_settings_accepts_mock_provider_and_historical_env_values(monkeypatch) -> None:
    monkeypatch.setenv("HOOPHIGHER_STATS_PROVIDER", "mock")
    monkeypatch.setenv("HOOPHIGHER_HISTORICAL_START_YEAR", "2012")
    monkeypatch.setenv("HOOPHIGHER_HISTORICAL_END_YEAR", "2019")
    monkeypatch.setenv("HOOPHIGHER_HISTORICAL_ROUNDS", "7")
    monkeypatch.setenv("HOOPHIGHER_NBA_API_TIMEOUT_SECONDS", "25")

    values = config_module.Settings()

    assert values.stats_provider == "mock"
    assert values.historical_start_year == 2012
    assert values.historical_end_year == 2019
    assert values.historical_rounds == 7
    assert values.nba_api_timeout_seconds == 25


def test_settings_rejects_invalid_provider(monkeypatch) -> None:
    monkeypatch.setenv("HOOPHIGHER_STATS_PROVIDER", "invalid")

    with pytest.raises(ValidationError, match="stats_provider"):
        config_module.Settings()


def test_settings_rejects_historical_start_year_after_end_year(monkeypatch) -> None:
    monkeypatch.setenv("HOOPHIGHER_HISTORICAL_START_YEAR", "2021")
    monkeypatch.setenv("HOOPHIGHER_HISTORICAL_END_YEAR", "2019")

    with pytest.raises(ValidationError, match="historical_start_year"):
        config_module.Settings()


def test_settings_rejects_historical_rounds_below_one(monkeypatch) -> None:
    monkeypatch.setenv("HOOPHIGHER_HISTORICAL_ROUNDS", "0")

    with pytest.raises(ValidationError, match="historical_rounds"):
        config_module.Settings()


def test_settings_rejects_nba_api_timeout_below_one(monkeypatch) -> None:
    monkeypatch.setenv("HOOPHIGHER_NBA_API_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValidationError, match="nba_api_timeout_seconds"):
        config_module.Settings()


def test_create_stats_provider_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown stats provider"):
        app_module.create_stats_provider("invalid")


def test_recent_candidate_dates_returns_today_first() -> None:
    assert app_module.recent_candidate_dates(today=date(2025, 2, 10), days=3) == (
        date(2025, 2, 10),
        date(2025, 2, 9),
        date(2025, 2, 8),
    )


def test_app_selects_nba_api_provider_by_default(monkeypatch) -> None:
    monkeypatch.delenv("HOOPHIGHER_STATS_PROVIDER", raising=False)
    _reload_app_module()

    async def scenario() -> None:
        app = app_module.HoopHigherApp(database_url="sqlite://")
        async with app.run_test():
            assert isinstance(app.gameplay_service._provider, NBAApiProvider)

    asyncio.run(scenario())


def test_app_selects_mock_provider_when_env_is_set(monkeypatch) -> None:
    monkeypatch.setenv("HOOPHIGHER_STATS_PROVIDER", "mock")
    _reload_app_module()

    async def scenario() -> None:
        app = app_module.HoopHigherApp(database_url="sqlite://")
        async with app.run_test():
            assert isinstance(app.gameplay_service._provider, MockProvider)

    asyncio.run(scenario())


def test_app_wires_nba_api_timeout_from_settings(monkeypatch) -> None:
    monkeypatch.setenv("HOOPHIGHER_STATS_PROVIDER", "nba_api")
    monkeypatch.setenv("HOOPHIGHER_NBA_API_TIMEOUT_SECONDS", "37")
    _reload_app_module()

    async def scenario() -> None:
        app = app_module.HoopHigherApp(database_url="sqlite://")
        async with app.run_test():
            provider = app.gameplay_service._provider
            assert isinstance(provider, NBAApiProvider)
            assert provider._timeout_seconds == 37

    asyncio.run(scenario())


def test_app_wires_nba_api_cache_to_configured_database(monkeypatch, tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'app-cache.db'}"
    monkeypatch.setenv("HOOPHIGHER_STATS_PROVIDER", "nba_api")
    _reload_app_module()

    cached_game = GameBoxScore(
        game_id="0022500999",
        game_date=date(2025, 2, 10),
        home_team=TeamGameInfo(team_id="1610612737", name="Hawks", abbreviation="ATL", score=110),
        away_team=TeamGameInfo(team_id="1610612738", name="Celtics", abbreviation="BOS", score=108),
        player_lines=(
            PlayerLine(
                player_id="1",
                player_name="Player One",
                team_id="1610612737",
                team_abbreviation="ATL",
                points=20,
                minutes=30,
            ),
        ),
    )

    async def scenario() -> None:
        app = app_module.HoopHigherApp(database_url=database_url)
        async with app.run_test():
            provider = app.gameplay_service._provider
            assert isinstance(provider, NBAApiProvider)
            with provider._cache_repository_factory() as cache_repository:
                cache_repository.set_game_boxscore(cached_game)

    asyncio.run(scenario())

    engine = create_sqlite_engine(database_url)
    with session_scope(engine) as session:
        assert CacheRepository(session).get_game_boxscore("0022500999") == cached_game


def test_start_game_passes_recent_candidate_dates_for_real_non_historical_provider(monkeypatch) -> None:
    app = app_module.HoopHigherApp(database_url="sqlite://")
    app._uses_mock_provider = False
    app._recent_candidate_dates = (date(2025, 2, 10), date(2025, 2, 9))
    pushed_screens: list[object] = []

    class FakeGameplayService:
        def __init__(self) -> None:
            self.calls: list[tuple[GameMode, dict[str, object]]] = []

        async def start_run(self, mode: GameMode, **kwargs: object) -> GameplaySnapshot:
            self.calls.append((mode, kwargs))
            return _make_snapshot(mode)

    fake_service = FakeGameplayService()
    app.gameplay_service = fake_service
    monkeypatch.setattr(app, "push_screen", lambda screen: pushed_screens.append(screen))

    asyncio.run(app.start_game(GameMode.ENDLESS))

    assert fake_service.calls == [
        (
            GameMode.ENDLESS,
            {
                "total_questions": 5,
                "candidate_dates": (date(2025, 2, 10), date(2025, 2, 9)),
            },
        )
    ]
    assert pushed_screens


def test_start_game_uses_indexed_historical_path_for_real_provider(monkeypatch) -> None:
    app = app_module.HoopHigherApp(database_url="sqlite://")
    app._uses_mock_provider = False
    app._recent_candidate_dates = (date(2025, 2, 10),)
    pushed_screens: list[object] = []

    class FakeGameplayService:
        def __init__(self) -> None:
            self.calls: list[tuple[GameMode, dict[str, object]]] = []

        async def start_run(self, mode: GameMode, **kwargs: object) -> GameplaySnapshot:
            self.calls.append((mode, kwargs))
            return _make_snapshot(mode)

    fake_service = FakeGameplayService()
    app.gameplay_service = fake_service
    monkeypatch.setattr(app, "push_screen", lambda screen: pushed_screens.append(screen))

    asyncio.run(app.start_game(GameMode.HISTORICAL))

    assert fake_service.calls == [(GameMode.HISTORICAL, {"total_questions": 5})]
    assert pushed_screens


def _make_snapshot(mode: GameMode) -> GameplaySnapshot:
    game = GameBoxScore(
        game_id="0022500999",
        game_date=date(2025, 2, 10),
        home_team=TeamGameInfo(team_id="1610612737", name="Hawks", abbreviation="ATL", score=110),
        away_team=TeamGameInfo(team_id="1610612738", name="Celtics", abbreviation="BOS", score=108),
        player_lines=(
            PlayerLine(
                player_id="1",
                player_name="Player One",
                team_id="1610612737",
                team_abbreviation="ATL",
                points=20,
                minutes=30,
            ),
        ),
    )
    return GameplaySnapshot(
        run_id=1,
        round_id=1,
        mode=mode,
        source_date=game.game_date,
        score=0,
        current_streak=0,
        best_streak=0,
        correct_answers=0,
        wrong_answers=0,
        end_reason=None,
        game_id=game.game_id,
        current_game=game,
        games_today=(game,),
        round_index=0,
        question_index=0,
        total_questions=5,
        current_question=None,
    )
