from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label

from hoophigher.services import LeaderboardResult, LeaderboardRow
from hoophigher.tui.widgets import DialogShell


def _format_mode_label(row: LeaderboardRow) -> str:
    return row.mode.value.replace("_", " ").title()


def _render_rows(result: LeaderboardResult) -> str:
    if result.is_empty:
        return "No runs recorded yet."
    lines = ["RK  MODE         SCORE  STRK  CORR  DATE"]
    lines.extend(
        f"{row.rank:>2}  {_format_mode_label(row):<12} "
        f"{row.score:>5}  {row.best_streak:>4}  "
        f"{row.correct_answers:>4}  {row.source_date_label}"
        for row in result.rows
    )
    return "\n\n".join(lines)


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

    LeaderboardScreen #leaderboard-rows {
        width: 100%;
        margin-bottom: 1;
    }

    LeaderboardScreen #leaderboard-rows.-empty {
        text-align: center;
        color: #8b949e;
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
        yield Header(show_clock=False)
        with DialogShell(id="leaderboard-panel"):
            yield Label("LOCAL LEADERBOARD", id="leaderboard-title")
            yield Label("Top 10 runs saved on this machine.", id="leaderboard-subtitle")
            yield Label("", id="leaderboard-rows")
            yield Button("←  Back  [Esc]", id="leaderboard-back", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#leaderboard-back", Button).focus()

    def on_screen_resume(self, _: events.ScreenResume) -> None:
        """Reload rows whenever this screen becomes active.

        Textual sends ScreenResume both on the initial push and every time
        this installed screen is pushed again, so newly saved Runs always
        appear without restarting the app.
        """
        result = self.app.leaderboard_service.get_leaderboard()
        rows = self.query_one("#leaderboard-rows", Label)
        rows.set_class(result.is_empty, "-empty")
        rows.update(_render_rows(result))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "leaderboard-back":
            self.app.pop_screen()

    def action_back(self) -> None:
        self.app.pop_screen()
