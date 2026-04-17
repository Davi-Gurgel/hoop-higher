from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label

from hoophigher.services import LeaderboardRow
from hoophigher.tui.widgets import DialogShell


def _format_mode_label(row: LeaderboardRow) -> str:
    return row.mode.value.replace("_", " ").title()


class LeaderboardScreen(Screen[None]):
    DEFAULT_CSS = """
    LeaderboardScreen {
        align: center middle;
    }

    LeaderboardScreen #leaderboard-panel {
        width: 76;
        border: heavy #f0883e;
    }

    LeaderboardScreen #leaderboard-title {
        text-align: center;
        text-style: bold;
        color: #f0883e;
        width: 100%;
        margin-bottom: 1;
    }

    LeaderboardScreen #leaderboard-subtitle {
        text-align: center;
        color: #8b949e;
        width: 100%;
        margin-bottom: 2;
    }

    LeaderboardScreen .leaderboard-row {
        width: 100%;
        margin-bottom: 1;
    }

    LeaderboardScreen #leaderboard-empty {
        text-align: center;
        color: #8b949e;
        width: 100%;
        margin-bottom: 2;
    }

    LeaderboardScreen #leaderboard-back {
        width: 100%;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        result = self.app.leaderboard_service.get_leaderboard()

        yield Header(show_clock=False)
        with DialogShell(id="leaderboard-panel"):
            yield Label("LOCAL LEADERBOARD", id="leaderboard-title")
            yield Label("Top 10 runs saved on this machine.", id="leaderboard-subtitle")
            if result.is_empty:
                yield Label("No runs recorded yet.", id="leaderboard-empty")
            else:
                yield Label("RK  MODE         SCORE  STRK  CORR  DATE", classes="leaderboard-row")
                for row in result.rows:
                    yield Label(
                        f"{row.rank:>2}  {_format_mode_label(row):<12} "
                        f"{row.score:>5}  {row.best_streak:>4}  "
                        f"{row.correct_answers:>4}  {row.source_date_label}",
                        classes="leaderboard-row",
                    )
            yield Button("←  Back  [Esc]", id="leaderboard-back", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#leaderboard-back", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "leaderboard-back":
            self.app.pop_screen()

    def action_back(self) -> None:
        self.app.pop_screen()
