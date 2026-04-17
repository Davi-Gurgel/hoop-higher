from __future__ import annotations

from datetime import date

from textual.app import App

from hoophigher.config import settings
from hoophigher.data import create_sqlite_engine, init_db
from hoophigher.data.api import MockProvider
from hoophigher.domain.enums import GameMode
from hoophigher.services import GameplayService, StatsService
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


class HoopHigherApp(App[None]):
    CSS_PATH = "tui/styles.tcss"
    TITLE = "Hoop Higher"
    SUB_TITLE = "Mock gameplay"
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
        self._database_url = database_url or settings.database_url

    def on_mount(self) -> None:
        engine = create_sqlite_engine(
            self._database_url,
            sqlite_journal_mode=settings.sqlite_journal_mode,
            sqlite_synchronous=settings.sqlite_synchronous,
            sqlite_busy_timeout_ms=settings.sqlite_busy_timeout_ms,
        )
        init_db(engine)
        self.gameplay_service = GameplayService(
            engine=engine,
            provider=MockProvider(),
        )
        self.stats_service = StatsService(engine=engine)
        self.install_screen(HomeScreen(), name="home")
        self.install_screen(ModeSelectScreen(), name="mode-select")
        self.install_screen(LeaderboardScreen(), name="leaderboard")
        self.install_screen(StatsScreen(), name="stats")
        self.push_screen("home")

    async def start_game(self, mode: GameMode) -> None:
        snapshot = await self.gameplay_service.start_run(
            mode,
            candidate_dates=MOCK_CANDIDATE_DATES,
            total_questions=5,
        )
        self.push_screen(GameScreen(snapshot))
