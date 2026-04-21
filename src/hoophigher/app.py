from __future__ import annotations

import asyncio
from datetime import date, timedelta

from sqlalchemy.engine import Engine
from textual.app import App

from hoophigher.config import Settings
from hoophigher.data import create_sqlite_engine, init_db
from hoophigher.data.api import MockProvider, NBAApiProvider, StatsProvider
from hoophigher.domain.enums import GameMode
from hoophigher.services import (
    GameplayService,
    LeaderboardService,
    StatsService,
)
from hoophigher.tui.screens import (
    GameScreen,
    HomeScreen,
    LeaderboardScreen,
    ModeSelectScreen,
    StatsScreen,
)

MOCK_CANDIDATE_DATES = (
    date(2025, 1, 12),
    date(2025, 1, 13),
)
RECENT_CANDIDATE_DAYS = 3
GAME_START_TIMEOUT_SECONDS = 45.0


def create_stats_provider(
    provider_name: str,
    *,
    timeout_seconds: int = 20,
    max_retries: int = 1,
    retry_delay_seconds: float = 1.0,
    engine: Engine | None = None,
) -> StatsProvider:
    if provider_name == "mock":
        return MockProvider()
    if provider_name == "nba_api":
        return NBAApiProvider(
            engine=engine,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
        )
    raise ValueError(
        f"Unknown stats provider '{provider_name}'. Expected one of: 'mock', 'nba_api'."
    )


def recent_candidate_dates(
    *,
    today: date | None = None,
    days: int = RECENT_CANDIDATE_DAYS,
) -> tuple[date, ...]:
    if days < 1:
        raise ValueError("days must be at least 1.")
    current_date = today or date.today()
    return tuple(current_date - timedelta(days=offset) for offset in range(days))


class HoopHigherApp(App[None]):
    CSS_PATH = "tui/styles.tcss"
    TITLE = "Hoop Higher"
    SUB_TITLE = "Local gameplay"
    HORIZONTAL_BREAKPOINTS = [
        (0, "-w-xs"),
        (72, "-w-sm"),
        (96, "-w-md"),
        (128, "-w-lg"),
    ]
    VERTICAL_BREAKPOINTS = [
        (0, "-h-xs"),
        (24, "-h-sm"),
        (32, "-h-md"),
        (40, "-h-lg"),
    ]

    def __init__(self, *, database_url: str | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._database_url = database_url
        self._session_historical_date: date | None = None
        self._session_recent_date: date | None = None
        self._game_start_timeout_seconds = GAME_START_TIMEOUT_SECONDS

    def on_mount(self) -> None:
        settings = Settings()
        engine = create_sqlite_engine(
            self._database_url or settings.database_url,
            sqlite_journal_mode=settings.sqlite_journal_mode,
            sqlite_synchronous=settings.sqlite_synchronous,
            sqlite_busy_timeout_ms=settings.sqlite_busy_timeout_ms,
        )
        init_db(engine)
        provider = create_stats_provider(
            settings.stats_provider,
            timeout_seconds=settings.nba_api_timeout_seconds,
            max_retries=settings.nba_api_max_retries,
            retry_delay_seconds=settings.nba_api_retry_delay_seconds,
            engine=engine,
        )
        self._uses_mock_provider = isinstance(provider, MockProvider)
        self._recent_candidate_dates = recent_candidate_dates()
        self._game_start_timeout_seconds = settings.game_start_timeout_seconds
        gameplay_service_kwargs: dict[str, object] = {
            "engine": engine,
            "provider": provider,
            "historical_start_year": settings.historical_start_year,
            "historical_end_year": settings.historical_end_year,
            "historical_rounds": settings.historical_rounds,
            "historical_max_date_probes": settings.historical_max_date_probes,
            "playable_game_fetch_concurrency": settings.nba_api_fetch_concurrency,
        }
        if not self._uses_mock_provider:
            gameplay_service_kwargs["non_historical_startup_games"] = (
                settings.nba_api_startup_games
            )
        self.gameplay_service = GameplayService(**gameplay_service_kwargs)
        self.leaderboard_service = LeaderboardService(engine=engine)
        self.stats_service = StatsService(engine=engine)
        self.install_screen(HomeScreen(), name="home")
        self.install_screen(LeaderboardScreen(), name="leaderboard")
        self.install_screen(StatsScreen(), name="stats")
        self.install_screen(ModeSelectScreen(), name="mode-select")
        self.push_screen("home")

    async def start_game(self, mode: GameMode) -> bool:
        start_run_kwargs: dict[str, object] = {"total_questions": 5}
        if self._uses_mock_provider:
            start_run_kwargs["candidate_dates"] = MOCK_CANDIDATE_DATES
        elif mode is GameMode.HISTORICAL and self._session_historical_date is not None:
            start_run_kwargs["source_date"] = self._session_historical_date
        elif mode is not GameMode.HISTORICAL and self._session_recent_date is not None:
            start_run_kwargs["source_date"] = self._session_recent_date
        elif mode is not GameMode.HISTORICAL:
            start_run_kwargs["candidate_dates"] = self._recent_candidate_dates
        try:
            snapshot = await asyncio.wait_for(
                self.gameplay_service.start_run(mode, **start_run_kwargs),
                timeout=self._game_start_timeout_seconds,
            )
        except TimeoutError:
            self.notify(
                (
                    "NBA data is taking too long to respond. Try again, use cached data, "
                    "or lower HOOPHIGHER_NBA_API_TIMEOUT_SECONDS for faster failures."
                ),
                title="Unable to start game",
                severity="error",
            )
            return False
        except (LookupError, ValueError) as exc:
            self.notify(str(exc), title="Unable to start game", severity="error")
            return False
        if not self._uses_mock_provider:
            self.clear_notifications()
            if mode is GameMode.HISTORICAL:
                self._session_historical_date = snapshot.source_date
            else:
                self._session_recent_date = snapshot.source_date
        self.push_screen(GameScreen(snapshot))
        return True
