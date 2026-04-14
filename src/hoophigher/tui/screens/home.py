from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label

from hoophigher.tui.widgets import DialogShell


class HomeScreen(Screen[None]):
    DEFAULT_CSS = """
    HomeScreen {
        align: center middle;
    }

    HomeScreen #home-panel {
        width: 60;
        border: heavy #f0883e;
    }

    HomeScreen #home-logo {
        text-align: center;
        text-style: bold;
        color: #f0883e;
        width: 100%;
        margin-bottom: 1;
    }

    HomeScreen #home-subtitle {
        text-align: center;
        color: #8b949e;
        width: 100%;
        margin-bottom: 2;
    }

    HomeScreen .home-btn {
        width: 100%;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        ("up", "focus_previous_button", "Prev"),
        ("down", "focus_next_button", "Next"),
        ("enter", "start", "Start"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with DialogShell(id="home-panel"):
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
