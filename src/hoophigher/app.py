from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from contextlib import suppress
from datetime import date, timedelta

from sqlalchemy.engine import Engine
from textual.app import App

from hoophigher.config import Settings
from hoophigher.data import (
    HistoricalIndexRepository,
    create_sqlite_engine,
    init_db,
    session_scope,
)
from hoophigher.data.api import MockProvider, NBAApiProvider, StatsProvider
from hoophigher.domain.enums import GameMode
from hoophigher.services import (
    GameplayService,
    HistoricalDateService,
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
LOADING_NOTICE_DELAY_SECONDS = 0.35
HistoricalEligibleDatesFetcher = Callable[[int, int, int], Awaitable[Sequence[date]]]


def create_stats_provider(
    provider_name: str,
    *,
    timeout_seconds: int = 20,
    retry_delay_seconds: float = 1.0,
    engine: Engine | None = None,
) -> StatsProvider:
    if provider_name == "mock":
        return MockProvider()
    if provider_name == "nba_api":
        return NBAApiProvider(
            engine=engine,
            timeout_seconds=timeout_seconds,
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
            retry_delay_seconds=settings.nba_api_retry_delay_seconds,
            engine=engine,
        )
        self._uses_mock_provider = isinstance(provider, MockProvider)
        self._recent_candidate_dates = recent_candidate_dates()
        historical_eligible_dates_fetcher: HistoricalEligibleDatesFetcher | None = None
        if not self._uses_mock_provider:
            historical_eligible_dates_fetcher = self._create_historical_eligible_dates_fetcher(
                engine=engine,
                timeout_seconds=settings.nba_api_timeout_seconds,
            )
        self.gameplay_service = GameplayService(
            engine=engine,
            provider=provider,
            historical_start_year=settings.historical_start_year,
            historical_end_year=settings.historical_end_year,
            historical_rounds=settings.historical_rounds,
            historical_max_date_probes=settings.historical_max_date_probes,
            playable_game_fetch_concurrency=settings.nba_api_fetch_concurrency,
            historical_eligible_dates_fetcher=historical_eligible_dates_fetcher,
        )
        self.leaderboard_service = LeaderboardService(engine=engine)
        self.stats_service = StatsService(engine=engine)
        self.install_screen(HomeScreen(), name="home")
        self.install_screen(LeaderboardScreen(), name="leaderboard")
        self.install_screen(StatsScreen(), name="stats")
        self.install_screen(ModeSelectScreen(), name="mode-select")
        self.push_screen("home")

    def _create_historical_eligible_dates_fetcher(
        self,
        *,
        engine: Engine,
        timeout_seconds: int,
    ) -> HistoricalEligibleDatesFetcher:
        async def fetch_eligible_dates(
            start_year: int,
            end_year: int,
            min_games: int,
        ) -> tuple[date, ...]:
            with session_scope(engine) as session:
                historical_date_service = HistoricalDateService(
                    index_repository=HistoricalIndexRepository(session),
                    timeout_seconds=timeout_seconds,
                )
                return await historical_date_service.get_or_build_eligible_dates(
                    start_year=start_year,
                    end_year=end_year,
                    min_games=min_games,
                )

        return fetch_eligible_dates

    async def start_game(self, mode: GameMode) -> None:
        loading_notice_task: asyncio.Task[None] | None = None
        if not self._uses_mock_provider:
            loading_notice_task = asyncio.create_task(self._notify_loading_if_slow())
        start_run_kwargs: dict[str, object] = {"total_questions": 5}
        if self._uses_mock_provider:
            start_run_kwargs["candidate_dates"] = MOCK_CANDIDATE_DATES
        elif mode is not GameMode.HISTORICAL:
            start_run_kwargs["candidate_dates"] = self._recent_candidate_dates
        try:
            snapshot = await self.gameplay_service.start_run(mode, **start_run_kwargs)
        except (LookupError, ValueError) as exc:
            await self._cancel_loading_notice(loading_notice_task)
            if not self._uses_mock_provider:
                self.clear_notifications()
            self.notify(str(exc), title="Unable to start game", severity="error")
            return
        await self._cancel_loading_notice(loading_notice_task)
        if not self._uses_mock_provider:
            self.clear_notifications()
        self.push_screen(GameScreen(snapshot))

    async def _notify_loading_if_slow(self) -> None:
        await asyncio.sleep(LOADING_NOTICE_DELAY_SECONDS)
        self.notify("Loading game data…", title="Please wait", timeout=10)

    async def _cancel_loading_notice(self, task: asyncio.Task[None] | None) -> None:
        if task is None:
            return
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
