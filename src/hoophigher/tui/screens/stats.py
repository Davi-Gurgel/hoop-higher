from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Static

from hoophigher.services import StatsResult
from hoophigher.tui.widgets import FooterHints, HeaderBand, hints

_MODE_BAR_WIDTH = 24


def _format_rate(value: float) -> str:
    return f"{value * 100:.1f}%"


class StatCard(Vertical):
    """Bordered card: dim uppercase label over a bold value."""

    DEFAULT_CSS = """
    StatCard {
        width: 1fr;
        height: auto;
        padding: 1 2;
        border: round $border;
        background: $card-fill;
        margin-right: 1;
    }

    StatCard .stat-label {
        width: 100%;
        color: $dim;
    }

    StatCard .stat-value {
        width: 100%;
        text-style: bold;
    }

    StatCard.-value-success .stat-value {
        color: $success;
    }

    StatCard.-value-highlight .stat-value {
        color: $warning;
    }
    """

    def __init__(self, label: str, *, tone: str = "", **kwargs: object) -> None:
        classes = f"-value-{tone}" if tone else ""
        super().__init__(classes=classes, **kwargs)
        self._label = label

    def compose(self) -> ComposeResult:
        yield Static(self._label, classes="stat-label")
        yield Static("0", classes="stat-value")

    def set_value(self, value: str) -> None:
        self.query_one(".stat-value", Static).update(value)


class StatsScreen(Screen[None]):
    DEFAULT_CSS = """
    StatsScreen #stats-content {
        width: 100%;
        height: 1fr;
        padding: 1 2;
    }

    StatsScreen #stats-cards,
    StatsScreen #stats-best {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    StatsScreen #stats-modes-title {
        width: 100%;
        color: $dim;
        margin-bottom: 1;
    }

    StatsScreen #stats-modes {
        width: 100%;
        height: auto;
    }

    StatsScreen .mode-row {
        width: 100%;
        height: 1;
    }

    StatsScreen .mode-row .mode-label {
        width: 12;
        color: $muted;
    }

    StatsScreen .mode-row .mode-bar {
        width: auto;
    }

    StatsScreen .mode-row .mode-count {
        width: auto;
        margin-left: 2;
        text-style: bold;
    }

    StatsScreen #stats-modes-empty {
        width: 100%;
        color: $muted;
    }
    """

    BINDINGS = [
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._runs_card = StatCard("RUNS", id="stat-runs")
        self._questions_card = StatCard("QUESTIONS", id="stat-questions")
        self._correct_card = StatCard("CORRECT", tone="success", id="stat-correct")
        self._accuracy_card = StatCard("ACCURACY", tone="success", id="stat-accuracy")
        self._best_score_card = StatCard("BEST SCORE", tone="highlight", id="stat-best-score")
        self._best_streak_card = StatCard("BEST STREAK", tone="highlight", id="stat-best-streak")

    def compose(self) -> ComposeResult:
        yield HeaderBand("STATS", "every run you've saved", id="stats-header")
        with Vertical(id="stats-content"):
            with Horizontal(id="stats-cards"):
                yield self._runs_card
                yield self._questions_card
                yield self._correct_card
                yield self._accuracy_card
            with Horizontal(id="stats-best"):
                yield self._best_score_card
                yield self._best_streak_card
            yield Static("BY MODE", id="stats-modes-title")
            yield Vertical(id="stats-modes")
        footer = FooterHints(id="stats-footer")
        footer.set_hints(hints(("esc", "back"), ("Q", "quit")))
        yield footer

    def on_mount(self) -> None:
        self.call_after_refresh(self._refresh_stats_view)

    def on_show(self, _: events.Show) -> None:
        self.call_after_refresh(self._refresh_stats_view)

    def on_screen_resume(self, _: events.ScreenResume) -> None:
        self.call_after_refresh(self._refresh_stats_view)

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_quit(self) -> None:
        self.app.exit()

    async def _refresh_stats_view(self) -> None:
        result: StatsResult = self.app.stats_service.get_stats()
        self._runs_card.set_value(str(result.total_runs))
        self._questions_card.set_value(str(result.total_answered_questions))
        self._correct_card.set_value(str(result.total_correct_answers))
        self._accuracy_card.set_value(_format_rate(result.accuracy_rate))
        self._best_score_card.set_value(f"{result.best_score:,}")
        self._best_streak_card.set_value(str(result.best_streak))

        modes_container = self.query_one("#stats-modes", Vertical)
        await modes_container.remove_children()
        if result.mode_distribution:
            rows = []
            for row in result.mode_distribution:
                share = row.count / result.total_runs if result.total_runs else 0.0
                filled = round(_MODE_BAR_WIDTH * share)
                bar = f"[$accent]{'█' * filled}[/][$surface]{'░' * (_MODE_BAR_WIDTH - filled)}[/]"
                rows.append(
                    Horizontal(
                        Static(row.mode.value, classes="mode-label"),
                        Static(bar, classes="mode-bar"),
                        Static(str(row.count), classes="mode-count"),
                        classes="mode-row",
                    )
                )
            await modes_container.mount(*rows)
        else:
            await modes_container.mount(
                Static(
                    "No runs yet — go make some regrettable guesses.",
                    id="stats-modes-empty",
                )
            )
