from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label

from hoophigher.domain.enums import GameMode


class ModeSelectScreen(Screen[None]):
    BINDINGS = [
        ("up", "focus_previous_button", "Prev"),
        ("down", "focus_next_button", "Next"),
        ("1", "select_endless", "Endless"),
        ("2", "select_arcade", "Arcade"),
        ("3", "select_historical", "Historical"),
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="mode-panel"):
            yield Label("SELECT MODE", id="mode-title")
            yield Label(
                "Endless: errors lose points, run continues\n"
                "Arcade:  one miss and you're out\n"
                "Historical: random date, real NBA feel",
                classes="mode-description",
            )
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
            self.app.pop_screen()
            return
        mode_map = {
            "mode-endless": GameMode.ENDLESS,
            "mode-arcade": GameMode.ARCADE,
            "mode-historical": GameMode.HISTORICAL,
        }
        mode = mode_map.get(button_id)
        if mode is not None:
            await self.app.start_game(mode)

    async def action_select_endless(self) -> None:
        await self.app.start_game(GameMode.ENDLESS)

    async def action_select_arcade(self) -> None:
        await self.app.start_game(GameMode.ARCADE)

    async def action_select_historical(self) -> None:
        await self.app.start_game(GameMode.HISTORICAL)

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_focus_previous_button(self) -> None:
        self.focus_previous(Button)

    def action_focus_next_button(self) -> None:
        self.focus_next(Button)
