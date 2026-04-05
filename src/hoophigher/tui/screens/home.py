from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label


class HomeScreen(Screen[None]):
    BINDINGS = [
        ("up", "focus_previous_button", "Prev"),
        ("down", "focus_next_button", "Next"),
        ("enter", "start", "Start"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="home-panel"):
            yield Label("🏀  HOOP HIGHER", id="home-logo")
            yield Label("Can you guess who scored more?", id="home-subtitle")
            yield Button("▶  Play  [Enter]", id="start-game", variant="success", classes="home-btn")
            yield Button("✕  Quit  [Q]", id="quit-game", variant="error", classes="home-btn")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#start-game", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-game":
            self.app.push_screen("mode-select")
        elif event.button.id == "quit-game":
            self.app.exit()

    def action_start(self) -> None:
        self.app.push_screen("mode-select")

    def action_focus_previous_button(self) -> None:
        self.focus_previous(Button)

    def action_focus_next_button(self) -> None:
        self.focus_next(Button)
