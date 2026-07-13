from __future__ import annotations

import time

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Button

from hoophigher.domain.enums import GameMode
from hoophigher.tui.widgets import FooterHints, HeaderBand, ModeCard, StatusStrip, hints

_START_GAME_WORKER_GROUP = "start-game"
_LOADING_STATUS_INTERVAL_SECONDS = 1
_SPINNER_FRAMES = "⣾⣽⣻⢿⡿⣟⣯⣷"

_IDLE_HINTS = hints(
    ("↑/↓", "move"),
    ("enter", "start"),
    ("1·2·3", "jump"),
    ("esc", "back"),
    ("Q", "quit"),
)
_CANCEL_HINTS = "[bold $warning]esc CANCEL[/][$dim] · modes locked until data lands[/]"


class ModeSelectScreen(Screen[None]):
    DEFAULT_CSS = """
    ModeSelectScreen #mode-content {
        width: 100%;
        height: 1fr;
        padding: 1 2;
    }
    """

    BINDINGS = [
        ("up", "focus_previous_button", "Prev"),
        ("down", "focus_next_button", "Next"),
        ("enter", "start_focused_mode", "Start"),
        ("1", "select_endless", "Endless"),
        ("2", "select_arcade", "Arcade"),
        ("3", "select_historical", "Historical"),
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._loading_mode: GameMode | None = None
        self._loading_started_at = 0.0
        self._loading_status_timer: Timer | None = None
        self._spinner_frame = 0

    def compose(self) -> ComposeResult:
        yield HeaderBand("CHOOSE YOUR MODE", id="mode-header")
        with Vertical(id="mode-content"):
            yield ModeCard(GameMode.ENDLESS, "1", id="mode-endless")
            yield ModeCard(GameMode.ARCADE, "2", id="mode-arcade")
            yield ModeCard(GameMode.HISTORICAL, "3", id="mode-historical")
            yield StatusStrip(id="mode-loading-status")
        footer = FooterHints(id="mode-footer")
        footer.set_hints(_IDLE_HINTS)
        yield footer

    def on_mount(self) -> None:
        self.query_one("#mode-endless", Button).focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if isinstance(event.button, ModeCard):
            self._begin_start_game(event.button.mode)

    def action_select_endless(self) -> None:
        self._begin_start_game(GameMode.ENDLESS)

    def action_select_arcade(self) -> None:
        self._begin_start_game(GameMode.ARCADE)

    def action_select_historical(self) -> None:
        self._begin_start_game(GameMode.HISTORICAL)

    def action_start_focused_mode(self) -> None:
        focused = self.focused
        if isinstance(focused, ModeCard):
            self._begin_start_game(focused.mode)

    def action_back(self) -> None:
        if self._loading_mode is not None:
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
        if self._loading_mode is not None:
            return
        self._set_loading(mode)
        self._start_game_worker(mode)

    @work(exclusive=True, group=_START_GAME_WORKER_GROUP)
    async def _start_game_worker(self, mode: GameMode) -> None:
        try:
            await self.app.start_game(mode)
        except Exception as exc:  # noqa: BLE001
            self.app.notify(str(exc), title="✗ Unable to start game", severity="error")
        finally:
            self._reset_loading()

    def _mode_cards(self) -> list[ModeCard]:
        return list(self.query(ModeCard))

    def _set_loading(self, mode: GameMode) -> None:
        self._loading_mode = mode
        self._loading_started_at = time.monotonic()
        self._spinner_frame = 0
        self._loading_status_timer = self.set_interval(
            _LOADING_STATUS_INTERVAL_SECONDS, self._refresh_loading_status
        )
        for card in self._mode_cards():
            if card.mode is mode:
                card.set_loading(True)
            else:
                card.disabled = True
        self.query_one("#mode-footer", FooterHints).set_hints(_CANCEL_HINTS)
        self._refresh_loading_status()

    def _reset_loading(self) -> None:
        if self._loading_mode is None:
            return
        self._loading_mode = None
        if self._loading_status_timer is not None:
            self._loading_status_timer.stop()
            self._loading_status_timer = None
        try:
            for card in self._mode_cards():
                card.set_loading(False)
                card.disabled = False
            self.query_one("#mode-footer", FooterHints).set_hints(_IDLE_HINTS)
            self.query_one("#mode-loading-status", StatusStrip).hide()
        except NoMatches:
            # The worker can be cancelled during app shutdown, after this
            # screen's widgets are gone.
            pass

    def _cancel_start_game(self) -> None:
        self.workers.cancel_group(self, _START_GAME_WORKER_GROUP)
        self._reset_loading()

    def _refresh_loading_status(self) -> None:
        strip = self.query_one("#mode-loading-status", StatusStrip)
        mode = self._loading_mode
        if mode is None:
            strip.hide()
            return

        elapsed_seconds = max(0, int(time.monotonic() - self._loading_started_at))
        if elapsed_seconds < 5:
            message = f"Loading {mode.value} game data..."
        elif elapsed_seconds < 15:
            message = f"Still fetching NBA games ({elapsed_seconds}s)..."
        else:
            message = f"stats.nba.com is slow; press Esc to cancel ({elapsed_seconds}s)."
        spinner = _SPINNER_FRAMES[self._spinner_frame % len(_SPINNER_FRAMES)]
        self._spinner_frame += 1
        strip.show("-loading", f"[$warning]{spinner}[/] {message}")
