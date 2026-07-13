from __future__ import annotations

import asyncio
from datetime import date, timedelta

from sqlalchemy.engine import Engine
from textual.app import App
from textual.binding import Binding
from textual.theme import Theme

from hoophigher.config import Settings
from hoophigher.data import create_sqlite_engine, init_db
from hoophigher.data.stats_sources import MockStatsSource, NBAApiStatsSource, StatsSource
from hoophigher.domain.enums import GameMode
from hoophigher.services import (
    GameplayService,
    LeaderboardService,
    RunHistoryService,
    StatsService,
)
from hoophigher.tui.responsive import FULL_MIN_WIDTH, SM_MIN_HEIGHT, SM_MIN_WIDTH
from hoophigher.tui.screens import (
    GameScreen,
    HomeScreen,
    LeaderboardScreen,
    ModeSelectScreen,
    RunHistoryScreen,
    StatsScreen,
)
from hoophigher.tui.theme import (
    DARK_THEME_NAME,
    DEFAULT_THEME_NAME,
    LIGHT_THEME_NAME,
    HOOP_HIGHER_THEMES,
    THEME_VARIABLE_DEFAULTS,
    load_saved_theme_name,
    save_theme_name,
)

MOCK_CANDIDATE_DATES = (
    date(2025, 1, 12),
    date(2025, 1, 13),
)
RECENT_CANDIDATE_DAYS = 3


def create_stats_source(
    source_kind: str,
    *,
    timeout_seconds: int,
    max_retries: int,
    retry_delay_seconds: float,
    engine: Engine | None = None,
) -> StatsSource:
    if source_kind == "mock":
        return MockStatsSource()
    if source_kind == "nba_api":
        return NBAApiStatsSource(
            engine=engine,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
        )
    raise ValueError(f"Unknown stats source '{source_kind}'. Expected one of: 'mock', 'nba_api'.")


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
    BINDINGS = [Binding("t", "toggle_theme", "Theme", priority=True, show=False)]
    HORIZONTAL_BREAKPOINTS = [
        (0, "-w-xs"),
        (SM_MIN_WIDTH, "-w-sm"),
        (FULL_MIN_WIDTH, "-w-md"),
        (128, "-w-lg"),
    ]
    VERTICAL_BREAKPOINTS = [
        (0, "-h-xs"),
        (SM_MIN_HEIGHT, "-h-sm"),
        (32, "-h-md"),
        (40, "-h-lg"),
    ]

    def __init__(
        self,
        *,
        database_url: str | None = None,
        settings: Settings | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._settings = settings or Settings()
        self._database_url = database_url
        self._session_historical_date: date | None = None
        self._session_recent_date: date | None = None
        self._game_start_timeout_seconds = self._settings.game_start_timeout_seconds

    def get_theme_variable_defaults(self) -> dict[str, str]:
        return THEME_VARIABLE_DEFAULTS

    def _restore_theme(self) -> None:
        for theme in HOOP_HIGHER_THEMES:
            self.register_theme(theme)
        saved_theme_name = None if self.is_headless else load_saved_theme_name()
        if saved_theme_name in self.available_themes:
            self.theme = saved_theme_name
        else:
            self.theme = DEFAULT_THEME_NAME
        self.theme_changed_signal.subscribe(self, self._persist_theme_choice)

    def _persist_theme_choice(self, theme: Theme) -> None:
        if not self.is_headless:
            save_theme_name(theme.name)

    def action_toggle_theme(self) -> None:
        going_light = self.current_theme.dark
        self.theme = LIGHT_THEME_NAME if going_light else DARK_THEME_NAME
        self.notify(f"Theme: {'light' if going_light else 'dark'}", timeout=2)

    def on_mount(self) -> None:
        self._restore_theme()
        engine = create_sqlite_engine(
            self._database_url or self._settings.database_url,
            sqlite_journal_mode=self._settings.sqlite_journal_mode,
            sqlite_synchronous=self._settings.sqlite_synchronous,
            sqlite_busy_timeout_ms=self._settings.sqlite_busy_timeout_ms,
        )
        init_db(engine)
        stats_source = create_stats_source(
            self._settings.stats_provider,
            timeout_seconds=self._settings.nba_api_timeout_seconds,
            max_retries=self._settings.nba_api_max_retries,
            retry_delay_seconds=self._settings.nba_api_retry_delay_seconds,
            engine=engine,
        )
        self._uses_mock_stats_source = isinstance(stats_source, MockStatsSource)
        self._recent_candidate_dates = recent_candidate_dates()
        gameplay_service_kwargs: dict[str, object] = {
            "engine": engine,
            "stats_source": stats_source,
            "historical_start_year": self._settings.historical_start_year,
            "historical_end_year": self._settings.historical_end_year,
            "historical_rounds": self._settings.historical_rounds,
            "historical_max_date_probes": self._settings.historical_max_date_probes,
            "playable_game_fetch_concurrency": self._settings.nba_api_fetch_concurrency,
            "non_historical_startup_games": self._settings.nba_api_startup_games,
        }
        self.gameplay_service = GameplayService(**gameplay_service_kwargs)
        self.leaderboard_service = LeaderboardService(engine=engine)
        self.stats_service = StatsService(engine=engine)
        self.run_history_service = RunHistoryService(engine=engine)
        self.install_screen(HomeScreen(), name="home")
        self.install_screen(LeaderboardScreen(), name="leaderboard")
        self.install_screen(StatsScreen(), name="stats")
        self.install_screen(RunHistoryScreen(), name="run-history")
        self.install_screen(ModeSelectScreen(), name="mode-select")
        self.push_screen("home")

    async def start_game(self, mode: GameMode) -> bool:
        start_run_kwargs: dict[str, object] = {"total_questions": 5}
        if self._uses_mock_stats_source:
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
                    "stats.nba.com timed out. Not on you this time — try again, use cached "
                    "data, or lower HOOPHIGHER_NBA_API_TIMEOUT_SECONDS for faster failures."
                ),
                title="✗ Unable to start game",
                severity="error",
            )
            return False
        except (LookupError, ValueError) as exc:
            self.notify(str(exc), title="✗ Unable to start game", severity="error")
            return False
        if not self._uses_mock_stats_source:
            self.clear_notifications()
            if mode is GameMode.HISTORICAL:
                self._session_historical_date = snapshot.source_date
            else:
                self._session_recent_date = snapshot.source_date
        self.push_screen(GameScreen(snapshot))
        return True
