from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label

from hoophigher.tui.widgets import DialogShell


class LeaderboardScreen(Screen[None]):
    DEFAULT_CSS = """
    LeaderboardScreen {
        align: center middle;
    }

    LeaderboardScreen #leaderboard-panel {
        width: 100%;
        max-width: 74;
        max-height: 1fr;
        overflow-y: auto;
        border: heavy #f0883e;
    }

    LeaderboardScreen #leaderboard-title {
        text-align: center;
        text-style: bold;
        color: #f0883e;
        width: 100%;
        margin-bottom: 1;
    }

    LeaderboardScreen .leaderboard-row {
        width: 100%;
        margin-bottom: 1;
    }

    LeaderboardScreen #leaderboard-back {
        width: 100%;
        margin-top: 1;
    }
    """

    BINDINGS = [("escape", "back", "Back"), ("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        entries = self.app.stats_service.get_leaderboard(limit=10)
        yield Header(show_clock=False)
        with DialogShell(id="leaderboard-panel"):
            yield Label("LOCAL LEADERBOARD", id="leaderboard-title")
            if not entries:
                yield Label("No runs yet. Play a game to build the ranking.", classes="leaderboard-row")
            else:
                for entry in entries:
                    yield Label(
                        f"#{entry.rank:02d}  {entry.mode.upper():10s}  SCORE {entry.score:>5d}  "
                        f"✓ {entry.correct_answers:>2d}  ✕ {entry.wrong_answers:>2d}  STREAK {entry.best_streak:>2d}",
                        classes="leaderboard-row",
                    )
            yield Button("← Back  [Esc]", id="leaderboard-back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "leaderboard-back":
            self.action_back()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_quit(self) -> None:
        self.app.exit()
