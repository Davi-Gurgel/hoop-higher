from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label

from hoophigher.tui.widgets import DialogShell


class StatsScreen(Screen[None]):
    DEFAULT_CSS = """
    StatsScreen {
        align: center middle;
    }

    StatsScreen #stats-panel {
        width: 100%;
        max-width: 62;
        max-height: 1fr;
        overflow-y: auto;
        border: heavy #f0883e;
    }

    StatsScreen #stats-title {
        text-align: center;
        text-style: bold;
        color: #f0883e;
        width: 100%;
        margin-bottom: 1;
    }

    StatsScreen .stats-row {
        width: 100%;
        margin-bottom: 1;
    }

    StatsScreen #stats-back {
        width: 100%;
        margin-top: 1;
    }
    """

    BINDINGS = [("escape", "back", "Back"), ("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        summary = self.app.stats_service.get_summary()
        yield Header(show_clock=False)
        with DialogShell(id="stats-panel"):
            yield Label("LOCAL STATS", id="stats-title")
            yield Label(f"Runs: {summary.total_runs}", classes="stats-row")
            yield Label(f"Questions answered: {summary.total_answered}", classes="stats-row")
            yield Label(f"Correct answers: {summary.total_correct}", classes="stats-row")
            yield Label(f"Accuracy: {summary.accuracy_percent:.2f}%", classes="stats-row")
            yield Label(f"Best score: {summary.best_score}", classes="stats-row")
            yield Label(f"Best streak: {summary.best_streak}", classes="stats-row")
            if summary.mode_distribution:
                mode_parts = [f"{mode}:{count}" for mode, count in sorted(summary.mode_distribution.items())]
                yield Label(f"Modes: {', '.join(mode_parts)}", classes="stats-row")
            else:
                yield Label("Modes: no runs yet", classes="stats-row")
            yield Button("← Back  [Esc]", id="stats-back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "stats-back":
            self.action_back()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_quit(self) -> None:
        self.app.exit()
