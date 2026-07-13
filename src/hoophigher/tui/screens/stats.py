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

    def __init__(self, label: str, *, value_id: str, tone: str = "", **kwargs: object) -> None:
        classes = f"-value-{tone}" if tone else ""
        super().__init__(classes=classes, **kwargs)
        self._label = label
        self._value_id = value_id

    def compose(self) -> ComposeResult:
        yield Static(self._label, classes="stat-label")
        yield Static("0", id=self._value_id, classes="stat-value")


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

    def compose(self) -> ComposeResult:
        yield HeaderBand("STATS", "every run you've saved", id="stats-header")
        with Vertical(id="stats-content"):
            with Horizontal(id="stats-cards"):
                yield StatCard("RUNS", value_id="stat-runs-value")
                yield StatCard("QUESTIONS", value_id="stat-questions-value")
                yield StatCard("CORRECT", value_id="stat-correct-value", tone="success")
                yield StatCard("ACCURACY", value_id="stat-accuracy-value", tone="success")
            with Horizontal(id="stats-best"):
                yield StatCard("BEST SCORE", value_id="stat-best-score-value", tone="highlight")
                yield StatCard("BEST STREAK", value_id="stat-best-streak-value", tone="highlight")
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
        values_by_id = {
            "stat-runs-value": str(result.total_runs),
            "stat-questions-value": str(result.total_answered_questions),
            "stat-correct-value": str(result.total_correct_answers),
            "stat-accuracy-value": _format_rate(result.accuracy_rate),
            "stat-best-score-value": f"{result.best_score:,}",
            "stat-best-streak-value": str(result.best_streak),
        }
        for value_id, value in values_by_id.items():
            self.query_one(f"#{value_id}", Static).update(value)

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
