from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Label

from hoophigher.domain.formatting import format_source_date
from hoophigher.services import QuestionHistory, RoundHistory, RunHistoryDetail, RunHistoryRow
from hoophigher.tui.widgets import ActionRow, FooterHints, HeaderBand, hints


class _RunRow(ActionRow):
    """A saved-Run entry; pressing it opens that Run's details."""

    def __init__(self, run: RunHistoryRow) -> None:
        super().__init__(_format_run_summary(run), "enter", classes="run-history-row")
        self.run_id = run.run_id


class _RunHistoryList(VerticalScroll):
    """Scrolling run list that yields up/down to button focus instead of pixel scrolling.

    VerticalScroll normally binds up/down to scroll_up/scroll_down, which would
    otherwise swallow arrow keys before they reach the screen's button navigation.
    """

    BINDINGS = [
        Binding("up", "focus_previous_button", show=False),
        Binding("down", "focus_next_button", show=False),
    ]

    def action_focus_previous_button(self) -> None:
        self.screen.focus_previous(Button)

    def action_focus_next_button(self) -> None:
        self.screen.focus_next(Button)


def _format_run_summary(run: RunHistoryRow) -> str:
    return (
        f"{run.mode.label}  Score {run.score}  Streak {run.best_streak}  "
        f"{run.correct_answers}✓/{run.wrong_answers}✕  {format_source_date(run.source_date)}"
    )


def _format_question(question: QuestionHistory) -> str:
    outcome = "✓" if question.is_correct else "✕"
    score_sign = "+" if question.score_delta >= 0 else ""
    guess_label = "No guess" if question.guess is None else question.guess.title()
    return (
        f"{question.question_index + 1:>2}. "
        f"{question.player_a_name} ({question.player_a_team_abbreviation}) "
        f"{question.player_a_points} pts  →  "
        f"{question.player_b_name} ({question.player_b_team_abbreviation}) "
        f"{question.revealed_points} pts  |  {guess_label} {outcome} "
        f"{score_sign}{question.score_delta}"
    )


def _format_round_heading(round_history: RoundHistory) -> str:
    score_sign = "+" if round_history.score_delta >= 0 else ""
    return (
        f"ROUND {round_history.round_index + 1}  {round_history.game_date:%d-%m-%Y}  "
        f"{round_history.correct_answers}✓/{round_history.wrong_answers}✕  "
        f"{score_sign}{round_history.score_delta}"
    )


class RunHistoryScreen(Screen[None]):
    DEFAULT_CSS = """
    RunHistoryScreen #run-history-list {
        width: 100%;
        height: 1fr;
        padding: 1 2;
    }

    RunHistoryScreen #run-history-empty {
        color: $muted;
        width: 100%;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("up", "focus_previous_button", "Prev"),
        ("down", "focus_next_button", "Next"),
        ("enter", "open_selected", "Open"),
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield HeaderBand(
            "RUN HISTORY",
            "open a run to inspect its rounds",
            id="run-history-header",
        )
        yield _RunHistoryList(id="run-history-list")
        footer = FooterHints(id="run-history-footer")
        footer.set_hints(hints(("↑/↓", "move"), ("enter", "open"), ("esc", "back"), ("Q", "quit")))
        yield footer

    async def on_screen_resume(self, _: events.ScreenResume) -> None:
        """Reload saved runs whenever this screen becomes active.

        Textual sends ScreenResume both on the initial push and every time
        this installed screen is pushed again, so runs saved since the last
        visit always appear.
        """
        await self._refresh_runs()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if isinstance(event.button, _RunRow):
            self.app.push_screen(RunHistoryDetailScreen(event.button.run_id))

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_open_selected(self) -> None:
        focused = self.focused
        if isinstance(focused, Button):
            focused.press()

    def action_focus_previous_button(self) -> None:
        self.focus_previous(Button)

    def action_focus_next_button(self) -> None:
        self.focus_next(Button)

    def action_quit(self) -> None:
        self.app.exit()

    async def _refresh_runs(self) -> None:
        run_list = self.query_one("#run-history-list", _RunHistoryList)
        await run_list.remove_children()
        runs = self.app.run_history_service.list_runs()
        if runs:
            rows = [_RunRow(run) for run in runs]
            await run_list.mount(*rows)
            rows[0].focus()
        else:
            await run_list.mount(
                Label("No saved runs yet. Play a run to see it here.", id="run-history-empty")
            )


class RunHistoryDetailScreen(Screen[None]):
    DEFAULT_CSS = """
    RunHistoryDetailScreen #run-detail-content {
        width: 100%;
        height: 1fr;
        padding: 1 2;
    }

    RunHistoryDetailScreen #run-detail-empty {
        color: $muted;
        width: 100%;
        margin-top: 1;
    }

    RunHistoryDetailScreen .round-history-heading {
        color: $accent;
        text-style: bold;
        width: 100%;
        margin-top: 1;
    }

    RunHistoryDetailScreen .question-history-row {
        width: 100%;
        color: $muted;
    }
    """

    BINDINGS = [
        Binding("up", "scroll_questions_up", "Scroll", show=False),
        Binding("down", "scroll_questions_down", "Scroll", show=False),
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, run_id: int) -> None:
        super().__init__()
        self._run_id = run_id

    def compose(self) -> ComposeResult:
        detail = self.app.run_history_service.get_run(self._run_id)

        subtitle = "" if detail is None else _format_run_summary(detail.run)
        yield HeaderBand("RUN DETAILS", subtitle, id="run-detail-header")
        yield VerticalScroll(*self._detail_widgets(detail), id="run-detail-content")
        footer = FooterHints(id="run-detail-footer")
        footer.set_hints(hints(("↑/↓", "scroll"), ("esc", "back"), ("Q", "quit")))
        yield footer

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_quit(self) -> None:
        self.app.exit()

    def action_scroll_questions_up(self) -> None:
        self.query_one("#run-detail-content", VerticalScroll).scroll_up()

    def action_scroll_questions_down(self) -> None:
        self.query_one("#run-detail-content", VerticalScroll).scroll_down()

    @staticmethod
    def _detail_widgets(detail: RunHistoryDetail | None) -> list[Label]:
        if detail is None:
            return [Label("This saved run is no longer available.", id="run-detail-empty")]
        if not detail.rounds:
            return [Label("No rounds were recorded for this run.", id="run-detail-empty")]

        widgets: list[Label] = []
        for round_history in detail.rounds:
            widgets.append(
                Label(_format_round_heading(round_history), classes="round-history-heading")
            )
            widgets.extend(
                Label(_format_question(question), classes="question-history-row", markup=False)
                for question in round_history.questions
            )
        return widgets
