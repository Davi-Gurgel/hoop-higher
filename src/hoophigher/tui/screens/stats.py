from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label

from hoophigher.services import StatsResult
from hoophigher.tui.widgets import DialogShell


def _format_rate(value: float) -> str:
    return f"{value * 100:.1f}%"


class StatsScreen(Screen[None]):
    DEFAULT_CSS = """
    StatsScreen {
        align: center middle;
    }

    StatsScreen #stats-panel {
        width: 76;
        border: heavy #f0883e;
    }

    StatsScreen #stats-title {
        text-align: center;
        text-style: bold;
        color: #f0883e;
        width: 100%;
        margin-bottom: 1;
    }

    StatsScreen #stats-subtitle {
        text-align: center;
        color: #8b949e;
        width: 100%;
        margin-bottom: 2;
    }

    StatsScreen .stats-row {
        width: 100%;
        margin-bottom: 1;
    }

    StatsScreen #stats-modes-title {
        text-style: bold;
        width: 100%;
        margin-top: 1;
    }

    StatsScreen #stats-back {
        width: 100%;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        result: StatsResult = self.app.stats_service.get_stats()

        yield Header(show_clock=False)
        with DialogShell(id="stats-panel"):
            yield Label("LOCAL STATS", id="stats-title")
            yield Label("Your saved performance on this machine.", id="stats-subtitle")
            yield Label(f"Runs played: {result.total_runs}", classes="stats-row")
            yield Label(
                f"Questions answered: {result.total_answered_questions}",
                classes="stats-row",
            )
            yield Label(
                f"Correct answers: {result.total_correct_answers}",
                classes="stats-row",
            )
            yield Label(
                f"Accuracy rate: {_format_rate(result.accuracy_rate)}",
                classes="stats-row",
            )
            yield Label(f"Best score: {result.best_score}", classes="stats-row")
            yield Label(f"Best streak: {result.best_streak}", classes="stats-row")
            yield Label("Runs by mode", id="stats-modes-title")
            if result.mode_distribution:
                for row in result.mode_distribution:
                    yield Label(
                        f"{row.mode_label:<12} {row.count:>3}",
                        classes="stats-row",
                    )
            else:
                yield Label("No runs recorded yet.", classes="stats-row")
            yield Button("←  Back  [Esc]", id="stats-back", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#stats-back", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "stats-back":
            self.app.pop_screen()

    def action_back(self) -> None:
        self.app.pop_screen()
