from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label

from hoophigher.domain.enums import GameMode


class ModeSelectScreen(Screen[None]):
    BINDINGS = [("escape", "back", "Back"), ("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="mode-panel"):
            yield Label("Select Mode", id="mode-title")
            yield Button("Endless", id="mode-endless", variant="primary")
            yield Button("Arcade", id="mode-arcade", variant="warning")
            yield Button("Historical", id="mode-historical")
            yield Button("Back", id="mode-back")
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        app = self.app
        button_id = event.button.id
        if button_id == "mode-back":
            app.pop_screen()
            return
        if button_id == "mode-endless":
            await app.start_game(GameMode.ENDLESS)
            return
        if button_id == "mode-arcade":
            await app.start_game(GameMode.ARCADE)
            return
        if button_id == "mode-historical":
            await app.start_game(GameMode.HISTORICAL)

    def action_back(self) -> None:
        self.app.pop_screen()
