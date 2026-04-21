from __future__ import annotations

import asyncio
import time

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label

from hoophigher.domain.enums import GameMode
from hoophigher.tui.widgets import DialogShell


class ModeSelectScreen(Screen[None]):
    DEFAULT_CSS = """
    ModeSelectScreen {
        align: center middle;
    }

    ModeSelectScreen #mode-panel {
        width: 60;
        border: heavy #f0883e;
    }

    ModeSelectScreen #mode-title {
        text-align: center;
        text-style: bold;
        color: #f0883e;
        width: 100%;
        margin-bottom: 2;
    }

    ModeSelectScreen .mode-btn {
        width: 100%;
        margin-bottom: 1;
    }

    ModeSelectScreen .mode-description {
        text-align: center;
        color: #8b949e;
        width: 100%;
        margin-bottom: 2;
    }

    ModeSelectScreen #mode-loading-status {
        display: none;
        text-align: center;
        color: #e6edf3;
        width: 100%;
        margin-bottom: 2;
    }

    ModeSelectScreen #mode-loading-status.-visible {
        display: block;
    }
    """

    BINDINGS = [
        ("up", "focus_previous_button", "Prev"),
        ("down", "focus_next_button", "Next"),
        ("1", "select_endless", "Endless"),
        ("2", "select_arcade", "Arcade"),
        ("3", "select_historical", "Historical"),
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._is_loading = False
        self._loading_mode: GameMode | None = None
        self._loading_started_at = 0.0
        self._start_game_task: asyncio.Task[None] | None = None
        self._loading_status_task: asyncio.Task[None] | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with DialogShell(id="mode-panel"):
            yield Label("SELECT MODE", id="mode-title")
            yield Label(
                "Endless: errors lose points, run continues\n"
                "Arcade:  one miss and you're out\n"
                "Historical: random date, real NBA feel",
                classes="mode-description",
            )
            yield Label("", id="mode-loading-status")
            yield Button("♾  Endless  [1]", id="mode-endless", variant="primary", classes="mode-btn")
            yield Button("🕹  Arcade  [2]", id="mode-arcade", variant="warning", classes="mode-btn")
            yield Button("📅  Historical  [3]", id="mode-historical", variant="default", classes="mode-btn")
            yield Button("←  Back  [Esc]", id="mode-back", variant="default", classes="mode-btn")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#mode-endless", Button).focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "mode-back":
            self.action_back()
            return
        mode_map = {
            "mode-endless": GameMode.ENDLESS,
            "mode-arcade": GameMode.ARCADE,
            "mode-historical": GameMode.HISTORICAL,
        }
        mode = mode_map.get(button_id)
        if mode is not None:
            self._begin_start_game(mode)

    def action_select_endless(self) -> None:
        self._begin_start_game(GameMode.ENDLESS)

    def action_select_arcade(self) -> None:
        self._begin_start_game(GameMode.ARCADE)

    def action_select_historical(self) -> None:
        self._begin_start_game(GameMode.HISTORICAL)

    def action_back(self) -> None:
        if self._is_loading:
            self._cancel_start_game()
            return
        self.app.pop_screen()

    def action_focus_previous_button(self) -> None:
        self.focus_previous(Button)

    def action_focus_next_button(self) -> None:
        self.focus_next(Button)

    def action_quit(self) -> None:
        self._cancel_start_game()
        self.app.exit()

    def _begin_start_game(self, mode: GameMode) -> None:
        if self._is_loading:
            return
        self._set_loading(mode)
        self._start_game_task = asyncio.create_task(self._start_game(mode))

    async def _start_game(self, mode: GameMode) -> None:
        try:
            await self.app.start_game(mode)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            self.app.notify(str(exc), title="Unable to start game", severity="error")
        finally:
            self._reset_loading()

    def _set_loading(self, mode: GameMode) -> None:
        self._is_loading = True
        self._loading_mode = mode
        self._loading_started_at = time.monotonic()
        self._set_mode_buttons_disabled(True)
        self.query_one("#mode-back", Button).label = "Cancel  [Esc]"
        self._refresh_loading_status()
        self._loading_status_task = asyncio.create_task(self._pulse_loading_status())

    def _reset_loading(self) -> None:
        self._is_loading = False
        self._loading_mode = None
        self._start_game_task = None
        if self._loading_status_task is not None:
            self._loading_status_task.cancel()
            self._loading_status_task = None
        self._set_mode_buttons_disabled(False)
        self.query_one("#mode-back", Button).label = "←  Back  [Esc]"
        status = self.query_one("#mode-loading-status", Label)
        status.update("")
        status.remove_class("-visible")

    def _cancel_start_game(self) -> None:
        if self._start_game_task is not None and not self._start_game_task.done():
            self._start_game_task.cancel()
        self._reset_loading()

    async def _pulse_loading_status(self) -> None:
        try:
            while True:
                await asyncio.sleep(1)
                self._refresh_loading_status()
        except asyncio.CancelledError:
            raise

    def _refresh_loading_status(self) -> None:
        status = self.query_one("#mode-loading-status", Label)
        mode = self._loading_mode
        if mode is None:
            status.update("")
            status.remove_class("-visible")
            return

        elapsed_seconds = max(0, int(time.monotonic() - self._loading_started_at))
        if elapsed_seconds < 5:
            message = f"Loading {mode.value} game data..."
        elif elapsed_seconds < 15:
            message = f"Still fetching NBA boxscores ({elapsed_seconds}s)..."
        else:
            message = f"stats.nba.com is slow; press Esc to cancel ({elapsed_seconds}s)."
        status.update(message)
        status.add_class("-visible")

    def _set_mode_buttons_disabled(self, disabled: bool) -> None:
        for button_id in ("#mode-endless", "#mode-arcade", "#mode-historical"):
            self.query_one(button_id, Button).disabled = disabled
