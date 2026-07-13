from __future__ import annotations

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.theme import Theme
from textual.widgets import DataTable, Static

from hoophigher.services import LeaderboardResult
from hoophigher.tui.widgets import FooterHints, HeaderBand, hints

_ACCURACY_SUCCESS_THRESHOLD = 0.75


class LeaderboardScreen(Screen[None]):
    DEFAULT_CSS = """
    LeaderboardScreen #leaderboard-content {
        width: 100%;
        height: 1fr;
        padding: 1 2;
    }

    LeaderboardScreen #leaderboard-table {
        width: 100%;
        height: auto;
        background: transparent;
    }

    LeaderboardScreen #leaderboard-table > .datatable--header {
        background: transparent;
        color: $dim;
        text-style: none;
    }

    LeaderboardScreen #leaderboard-table > .datatable--odd-row {
        background: $zebra-fill;
    }

    LeaderboardScreen #leaderboard-table > .datatable--even-row {
        background: transparent;
    }

    LeaderboardScreen #leaderboard-empty {
        width: 100%;
        color: $muted;
        margin-top: 1;
        display: none;
    }

    LeaderboardScreen #leaderboard-empty.-visible {
        display: block;
    }
    """

    BINDINGS = [
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._result: LeaderboardResult | None = None

    def compose(self) -> ComposeResult:
        yield HeaderBand("LEADERBOARD", "top 10 · this machine", id="leaderboard-header")
        with Vertical(id="leaderboard-content"):
            yield DataTable(id="leaderboard-table", cursor_type="none", zebra_stripes=True)
            yield Static("No runs recorded yet. The board's waiting.", id="leaderboard-empty")
        footer = FooterHints(id="leaderboard-footer")
        footer.set_hints(hints(("esc", "back"), ("Q", "quit")))
        yield footer

    def on_mount(self) -> None:
        table = self.query_one("#leaderboard-table", DataTable)
        table.add_column(Text("#", justify="right"), key="rank")
        table.add_column("mode", key="mode")
        table.add_column(Text("score", justify="right"), key="score")
        table.add_column(Text("streak", justify="right"), key="streak")
        table.add_column(Text("acc", justify="right"), key="acc")
        table.add_column("date", key="date")
        self.app.theme_changed_signal.subscribe(self, self._on_theme_changed)

    def on_screen_resume(self, _: events.ScreenResume) -> None:
        """Reload rows whenever this screen becomes active.

        Textual sends ScreenResume both on the initial push and every time
        this installed screen is pushed again, so newly saved Runs always
        appear without restarting the app.
        """
        result = self.app.leaderboard_service.get_leaderboard()
        self._result = result
        self._populate(result)

    def _on_theme_changed(self, _theme: Theme) -> None:
        if self._result is not None:
            self._populate(self._result)

    def _populate(self, result: LeaderboardResult) -> None:
        table = self.query_one("#leaderboard-table", DataTable)
        table.clear()
        table.display = not result.is_empty
        self.query_one("#leaderboard-empty", Static).set_class(result.is_empty, "-visible")
        if result.is_empty:
            return

        # DataTable cells take Rich renderables, not TCSS variables, so the
        # role colors are resolved from the active theme at build time.
        theme_variables = self.app.theme_variables
        accent = theme_variables.get("accent", "")
        highlight = theme_variables.get("warning", "")
        success = theme_variables.get("success", "")
        muted = theme_variables.get("muted", "")

        for row in result.rows:
            is_top = row.rank == 1
            accuracy = row.accuracy_rate
            accuracy_style = success if accuracy >= _ACCURACY_SUCCESS_THRESHOLD else muted
            date_label = "--" if row.source_date is None else f"{row.source_date:%b %d}"
            table.add_row(
                Text(str(row.rank), style=f"bold {accent}" if is_top else "", justify="right"),
                Text(row.mode.value, style=f"bold {highlight}" if is_top else ""),
                Text(f"{row.score:,}", style="bold" if is_top else "", justify="right"),
                Text(str(row.best_streak), justify="right"),
                Text(f"{accuracy * 100:.1f}%", style=accuracy_style, justify="right"),
                Text(date_label, style=muted),
            )

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_quit(self) -> None:
        self.app.exit()
