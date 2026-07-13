from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Rule, Static

from hoophigher.tui.widgets import ActionRow, FooterHints, hints


class HomeScreen(Screen[None]):
    DEFAULT_CSS = """
    HomeScreen #home-content {
        width: 100%;
        height: 1fr;
        padding: 1 2;
    }

    HomeScreen #home-title {
        color: $accent;
        text-style: bold;
        width: 100%;
    }

    HomeScreen #home-rule {
        color: $border;
        margin: 0;
    }

    HomeScreen #home-tagline {
        color: $muted;
        width: 100%;
    }

    HomeScreen #home-hype {
        color: $warning;
        width: 100%;
        margin-bottom: 1;
    }

    HomeScreen.-h-xs #home-tagline,
    HomeScreen.-h-xs #home-hype {
        display: none;
    }
    """

    BINDINGS = [
        ("up", "focus_previous_button", "Prev"),
        ("down", "focus_next_button", "Next"),
        ("enter", "press_focused_button", "Select"),
        ("l", "open_leaderboard", "Leaderboard"),
        ("s", "open_stats", "Stats"),
        ("h", "open_run_history", "History"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="home-content"):
            yield Static("HOOP HIGHER", id="home-title")
            yield Rule(id="home-rule")
            yield Static("higher / lower · guess who scored more", id="home-tagline")
            yield Static("Two players, one hidden number. Back yourself.", id="home-hype")
            yield ActionRow("Play", "enter", id="start-game")
            yield ActionRow("Leaderboard", "[L]", id="open-leaderboard")
            yield ActionRow("Stats", "[S]", id="open-stats")
            yield ActionRow("Run History", "[H]", id="open-run-history")
            yield ActionRow("Quit", "[Q]", id="quit-game")
        footer = FooterHints(id="home-footer")
        footer.set_hints(
            hints(("↑/↓", "move"), ("enter", "select"), ("T", "theme"), ("", "letter = shortcut"))
            + " [$accent blink]▍[/]"
        )
        yield footer

    def on_mount(self) -> None:
        self.query_one("#start-game", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-game":
            self.app.push_screen("mode-select")
        elif event.button.id == "open-leaderboard":
            self.app.push_screen("leaderboard")
        elif event.button.id == "open-stats":
            self.app.push_screen("stats")
        elif event.button.id == "open-run-history":
            self.app.push_screen("run-history")
        elif event.button.id == "quit-game":
            self.app.exit()

    def action_press_focused_button(self) -> None:
        focused = self.focused
        if isinstance(focused, Button):
            focused.press()
        else:
            self.query_one("#start-game", Button).press()

    def action_open_leaderboard(self) -> None:
        self.app.push_screen("leaderboard")

    def action_open_stats(self) -> None:
        self.app.push_screen("stats")

    def action_open_run_history(self) -> None:
        self.app.push_screen("run-history")

    def action_quit(self) -> None:
        self.app.exit()

    def action_focus_previous_button(self) -> None:
        self.focus_previous(Button)

    def action_focus_next_button(self) -> None:
        self.focus_next(Button)
