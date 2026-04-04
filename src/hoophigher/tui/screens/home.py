from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label


class HomeScreen(Screen[None]):
    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="home-panel"):
            yield Label("Hoop Higher", id="home-title")
            yield Label("Mock gameplay base pronta para validar o loop completo.", id="home-subtitle")
            yield Button("Start", id="start-game", variant="success")
            yield Button("Quit", id="quit-game", variant="error")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-game":
            self.app.push_screen("mode-select")
        elif event.button.id == "quit-game":
            self.app.exit()
