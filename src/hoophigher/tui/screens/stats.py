from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label

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
        yield Header(show_clock=False)
        with DialogShell(id="stats-panel"):
            yield Label("LOCAL STATS", id="stats-title")
            yield Label("Your saved performance on this machine.", id="stats-subtitle")
            yield Label("Runs played: 0", id="stats-total-runs", classes="stats-row")
            yield Label(
                "Questions answered: 0",
                id="stats-total-questions",
                classes="stats-row",
            )
            yield Label(
                "Correct answers: 0",
                id="stats-total-correct",
                classes="stats-row",
            )
            yield Label("Accuracy rate: 0.0%", id="stats-accuracy", classes="stats-row")
            yield Label("Best score: 0", id="stats-best-score", classes="stats-row")
            yield Label("Best streak: 0", id="stats-best-streak", classes="stats-row")
            yield Label("Runs by mode", id="stats-modes-title")
            yield Vertical(Label("No runs recorded yet.", classes="stats-row"), id="stats-modes")
            yield Button("←  Back  [Esc]", id="stats-back", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        self.call_after_refresh(self._refresh_stats_view)
        self.query_one("#stats-back", Button).focus()

    def on_show(self, _: events.Show) -> None:
        self.call_after_refresh(self._refresh_stats_view)

    def on_screen_resume(self, _: events.ScreenResume) -> None:
        self.call_after_refresh(self._refresh_stats_view)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "stats-back":
            self.app.pop_screen()

    def action_back(self) -> None:
        self.app.pop_screen()

    async def _refresh_stats_view(self) -> None:
        result = self.app.stats_service.get_stats()
        self.query_one("#stats-total-runs", Label).update(f"Runs played: {result.total_runs}")
        self.query_one("#stats-total-questions", Label).update(
            f"Questions answered: {result.total_answered_questions}"
        )
        self.query_one("#stats-total-correct", Label).update(
            f"Correct answers: {result.total_correct_answers}"
        )
        self.query_one("#stats-accuracy", Label).update(
            f"Accuracy rate: {_format_rate(result.accuracy_rate)}"
        )
        self.query_one("#stats-best-score", Label).update(f"Best score: {result.best_score}")
        self.query_one("#stats-best-streak", Label).update(f"Best streak: {result.best_streak}")

        modes_container = self.query_one("#stats-modes", Vertical)
        await modes_container.remove_children()
        if result.mode_distribution:
            await modes_container.mount(
                *[
                    Label(f"{row.mode_label:<12} {row.count:>3}", classes="stats-row")
                    for row in result.mode_distribution
                ]
            )
        else:
            await modes_container.mount(Label("No runs recorded yet.", classes="stats-row"))

        self.query_one("#stats-back", Button).focus()
