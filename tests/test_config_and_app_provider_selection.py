from __future__ import annotations

import asyncio
import importlib
from datetime import date

import pytest
from pydantic import ValidationError

import hoophigher.app as app_module
import hoophigher.config as config_module
from hoophigher.data import (
    CacheRepository,
    create_sqlite_engine,
    session_scope,
)
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
    monkeypatch.setenv("HOOPHIGHER_NBA_API_MAX_RETRIES", "3")
    monkeypatch.setenv("HOOPHIGHER_NBA_API_STARTUP_GAMES", "2")
    monkeypatch.setenv("HOOPHIGHER_GAME_START_TIMEOUT_SECONDS", "35.5")

    values = config_module.Settings()

    assert values.stats_provider == "mock"
    assert values.historical_start_year == 2012
    assert values.historical_end_year == 2019
    assert values.historical_rounds == 7
    assert values.nba_api_timeout_seconds == 25
    assert values.nba_api_max_retries == 3
    assert values.nba_api_startup_games == 2
    assert values.game_start_timeout_seconds == 35.5


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


def test_settings_rejects_nba_api_max_retries_below_zero(monkeypatch) -> None:
    monkeypatch.setenv("HOOPHIGHER_NBA_API_MAX_RETRIES", "-1")

    with pytest.raises(ValidationError, match="nba_api_max_retries"):
        config_module.Settings()


def test_settings_rejects_nba_api_startup_games_below_one(monkeypatch) -> None:
    monkeypatch.setenv("HOOPHIGHER_NBA_API_STARTUP_GAMES", "0")

    with pytest.raises(ValidationError, match="nba_api_startup_games"):
        config_module.Settings()


def test_settings_rejects_game_start_timeout_below_one(monkeypatch) -> None:
    monkeypatch.setenv("HOOPHIGHER_GAME_START_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValidationError, match="game_start_timeout_seconds"):
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


def test_app_selects_nba_api_provider_when_env_is_set(monkeypatch) -> None:
    monkeypatch.setenv("HOOPHIGHER_STATS_PROVIDER", "nba_api")
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
    monkeypatch.setenv("HOOPHIGHER_NBA_API_MAX_RETRIES", "4")
    monkeypatch.setenv("HOOPHIGHER_NBA_API_STARTUP_GAMES", "3")
    monkeypatch.setenv("HOOPHIGHER_GAME_START_TIMEOUT_SECONDS", "55")
    _reload_app_module()

    async def scenario() -> None:
        app = app_module.HoopHigherApp(database_url="sqlite://")
        async with app.run_test():
            provider = app.gameplay_service._provider
            assert isinstance(provider, NBAApiProvider)
            assert provider._timeout_seconds == 37
            assert provider._max_retries == 4
            assert app.gameplay_service._non_historical_startup_games == 3
            assert app._game_start_timeout_seconds == 55

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


def test_app_uses_bounded_historical_probes_for_nba_api_provider(monkeypatch) -> None:
    monkeypatch.setenv("HOOPHIGHER_STATS_PROVIDER", "nba_api")
    _reload_app_module()

    async def scenario() -> None:
        app = app_module.HoopHigherApp(database_url="sqlite://")
        async with app.run_test():
            assert app.gameplay_service._historical_eligible_dates_fetcher is None

    asyncio.run(scenario())


def test_app_keeps_mock_provider_startup_game_count_for_snapshots(monkeypatch) -> None:
    monkeypatch.setenv("HOOPHIGHER_STATS_PROVIDER", "mock")
    monkeypatch.setenv("HOOPHIGHER_NBA_API_STARTUP_GAMES", "1")
    _reload_app_module()

    async def scenario() -> None:
        app = app_module.HoopHigherApp(database_url="sqlite://")
        async with app.run_test():
            assert app.gameplay_service._non_historical_startup_games == 5

    asyncio.run(scenario())


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


def test_start_game_omits_recent_candidate_dates_for_real_historical_provider(
    monkeypatch,
) -> None:
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


def test_start_game_reuses_successful_real_date_for_other_non_historical_modes(
    monkeypatch,
) -> None:
    app = app_module.HoopHigherApp(database_url="sqlite://")
    app._uses_mock_provider = False
    app._recent_candidate_dates = (date(2025, 2, 10), date(2025, 2, 9))
    pushed_screens: list[object] = []

    class FakeGameplayService:
        def __init__(self) -> None:
            self.calls: list[tuple[GameMode, dict[str, object]]] = []

        async def start_run(self, mode: GameMode, **kwargs: object) -> GameplaySnapshot:
            self.calls.append((mode, kwargs))
            return _make_snapshot(mode, source_date=date(2025, 2, 9))

    fake_service = FakeGameplayService()
    app.gameplay_service = fake_service
    monkeypatch.setattr(app, "push_screen", lambda screen: pushed_screens.append(screen))

    asyncio.run(app.start_game(GameMode.ENDLESS))
    asyncio.run(app.start_game(GameMode.ARCADE))

    assert fake_service.calls == [
        (
            GameMode.ENDLESS,
            {
                "total_questions": 5,
                "candidate_dates": (date(2025, 2, 10), date(2025, 2, 9)),
            },
        ),
        (
            GameMode.ARCADE,
            {
                "total_questions": 5,
                "source_date": date(2025, 2, 9),
            },
        ),
    ]
    assert len(pushed_screens) == 2


def test_start_game_reuses_successful_real_historical_date_for_session(
    monkeypatch,
) -> None:
    app = app_module.HoopHigherApp(database_url="sqlite://")
    app._uses_mock_provider = False
    app._recent_candidate_dates = (date(2025, 2, 10),)
    pushed_screens: list[object] = []

    class FakeGameplayService:
        def __init__(self) -> None:
            self.calls: list[tuple[GameMode, dict[str, object]]] = []

        async def start_run(self, mode: GameMode, **kwargs: object) -> GameplaySnapshot:
            self.calls.append((mode, kwargs))
            return _make_snapshot(mode, source_date=date(2016, 2, 10))

    fake_service = FakeGameplayService()
    app.gameplay_service = fake_service
    monkeypatch.setattr(app, "push_screen", lambda screen: pushed_screens.append(screen))

    asyncio.run(app.start_game(GameMode.HISTORICAL))
    asyncio.run(app.start_game(GameMode.HISTORICAL))

    assert fake_service.calls == [
        (GameMode.HISTORICAL, {"total_questions": 5}),
        (
            GameMode.HISTORICAL,
            {
                "total_questions": 5,
                "source_date": date(2016, 2, 10),
            },
        ),
    ]
    assert len(pushed_screens) == 2


def test_start_game_does_not_show_loading_notice_during_slow_success(monkeypatch) -> None:
    app = app_module.HoopHigherApp(database_url="sqlite://")
    app._uses_mock_provider = False
    app._recent_candidate_dates = (date(2025, 2, 10),)
    app._game_start_timeout_seconds = 1
    pushed_screens: list[object] = []
    notifications: list[tuple[str, dict[str, object]]] = []
    clear_count = 0

    class FakeGameplayService:
        async def start_run(self, mode: GameMode, **kwargs: object) -> GameplaySnapshot:
            await asyncio.sleep(0.4)
            return _make_snapshot(mode)

    def clear_notifications() -> None:
        nonlocal clear_count
        clear_count += 1

    app.gameplay_service = FakeGameplayService()
    monkeypatch.setattr(app, "push_screen", lambda screen: pushed_screens.append(screen))
    monkeypatch.setattr(
        app,
        "notify",
        lambda message, **kwargs: notifications.append((message, kwargs)),
    )
    monkeypatch.setattr(app, "clear_notifications", clear_notifications)

    asyncio.run(app.start_game(GameMode.ENDLESS))

    assert pushed_screens
    assert notifications == []
    assert clear_count == 1


def test_start_game_times_out_slow_real_data_provider(monkeypatch) -> None:
    app = app_module.HoopHigherApp(database_url="sqlite://")
    app._uses_mock_provider = False
    app._recent_candidate_dates = (date(2025, 2, 10),)
    app._game_start_timeout_seconds = 0.01
    pushed_screens: list[object] = []
    notifications: list[tuple[str, dict[str, object]]] = []
    clear_count = 0

    class FakeGameplayService:
        async def start_run(self, mode: GameMode, **kwargs: object) -> GameplaySnapshot:
            await asyncio.sleep(1)
            return _make_snapshot(mode)

    def clear_notifications() -> None:
        nonlocal clear_count
        clear_count += 1

    app.gameplay_service = FakeGameplayService()
    monkeypatch.setattr(app, "push_screen", lambda screen: pushed_screens.append(screen))
    monkeypatch.setattr(
        app,
        "notify",
        lambda message, **kwargs: notifications.append((message, kwargs)),
    )
    monkeypatch.setattr(app, "clear_notifications", clear_notifications)

    result = asyncio.run(app.start_game(GameMode.ENDLESS))

    assert result is False
    assert pushed_screens == []
    assert clear_count == 0
    assert notifications == [
        (
            (
                "NBA data is taking too long to respond. Try again, use cached data, "
                "or lower HOOPHIGHER_NBA_API_TIMEOUT_SECONDS for faster failures."
            ),
            {"title": "Unable to start game", "severity": "error"},
        )
    ]


def test_start_game_notifies_when_real_data_cannot_start(monkeypatch) -> None:
    app = app_module.HoopHigherApp(database_url="sqlite://")
    app._uses_mock_provider = False
    app._recent_candidate_dates = (date(2025, 2, 10),)
    pushed_screens: list[object] = []
    notifications: list[tuple[str, dict[str, object]]] = []

    class FakeGameplayService:
        async def start_run(self, mode: GameMode, **kwargs: object) -> GameplaySnapshot:
            raise LookupError("No playable games found for provided candidate dates.")

    app.gameplay_service = FakeGameplayService()
    monkeypatch.setattr(app, "push_screen", lambda screen: pushed_screens.append(screen))
    monkeypatch.setattr(
        app,
        "notify",
        lambda message, **kwargs: notifications.append((message, kwargs)),
    )

    asyncio.run(app.start_game(GameMode.ENDLESS))

    assert pushed_screens == []
    assert notifications == [
        (
            "No playable games found for provided candidate dates.",
            {"title": "Unable to start game", "severity": "error"},
        )
    ]


def _make_snapshot(
    mode: GameMode,
    *,
    source_date: date = date(2025, 2, 10),
) -> GameplaySnapshot:
    game = GameBoxScore(
        game_id="0022500999",
        game_date=source_date,
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
        source_date=source_date,
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
