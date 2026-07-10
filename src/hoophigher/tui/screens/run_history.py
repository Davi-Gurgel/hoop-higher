from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label

from hoophigher.services import QuestionHistory, RoundHistory, RunHistoryDetail, RunHistoryRow
from hoophigher.tui.widgets import DialogShell


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
        f"{run.mode_label}  Score {run.score}  Streak {run.best_streak}  "
        f"{run.correct_answers}✓/{run.wrong_answers}✕  {run.source_date_label}"
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
    RunHistoryScreen {
        align: center middle;
    }

    RunHistoryScreen #run-history-panel {
        width: 90%;
        max-width: 76;
        height: 80%;
        max-height: 24;
        border: heavy #f0883e;
    }

    RunHistoryScreen #run-history-title {
        text-align: center;
        text-style: bold;
        color: #f0883e;
        width: 100%;
        margin-bottom: 1;
    }

    RunHistoryScreen #run-history-subtitle {
        text-align: center;
        color: #8b949e;
        width: 100%;
        margin-bottom: 1;
    }

    RunHistoryScreen #run-history-list {
        height: 1fr;
        width: 100%;
    }

    RunHistoryScreen .run-history-row {
        width: 100%;
        margin-bottom: 1;
        text-align: left;
    }

    RunHistoryScreen #run-history-empty {
        color: #8b949e;
        text-align: center;
        width: 100%;
        margin-top: 2;
    }

    RunHistoryScreen #run-history-back {
        width: 100%;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("up", "focus_previous_button", "Prev"),
        ("down", "focus_next_button", "Next"),
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with DialogShell(id="run-history-panel"):
            yield Label("RUN HISTORY", id="run-history-title")
            yield Label(
                "Review saved runs and open one to inspect its rounds.",
                id="run-history-subtitle",
            )
            yield _RunHistoryList(id="run-history-list")
            yield Button("←  Back  [Esc]", id="run-history-back", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        self.call_after_refresh(self._refresh_runs)

    def on_show(self, _: events.Show) -> None:
        self.call_after_refresh(self._refresh_runs)

    def on_screen_resume(self, _: events.ScreenResume) -> None:
        self.call_after_refresh(self._refresh_runs)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run-history-back":
            self.app.pop_screen()
            return
        run_id = event.button.id.removeprefix("history-run-") if event.button.id else ""
        if run_id.isdigit():
            self.app.push_screen(RunHistoryDetailScreen(int(run_id)))

    def action_back(self) -> None:
        self.app.pop_screen()

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
            await run_list.mount(
                *[
                    Button(
                        _format_run_summary(run),
                        id=f"history-run-{run.run_id}",
                        classes="run-history-row",
                    )
                    for run in runs
                ]
            )
            self.query_one(f"#history-run-{runs[0].run_id}", Button).focus()
        else:
            await run_list.mount(
                Label("No saved runs yet. Play a run to see it here.", id="run-history-empty")
            )
            self.query_one("#run-history-back", Button).focus()


class RunHistoryDetailScreen(Screen[None]):
    DEFAULT_CSS = """
    RunHistoryDetailScreen {
        align: center middle;
    }

    RunHistoryDetailScreen #run-detail-panel {
        width: 90%;
        max-width: 96;
        height: 80%;
        max-height: 28;
        border: heavy #f0883e;
    }

    RunHistoryDetailScreen #run-detail-title {
        text-align: center;
        text-style: bold;
        color: #f0883e;
        width: 100%;
        margin-bottom: 1;
    }

    RunHistoryDetailScreen #run-detail-subtitle {
        text-align: center;
        color: #8b949e;
        width: 100%;
        margin-bottom: 1;
    }

    RunHistoryDetailScreen #run-detail-content {
        height: 1fr;
        width: 100%;
    }

    RunHistoryDetailScreen #run-detail-empty {
        color: #8b949e;
        text-align: center;
        width: 100%;
        margin-top: 2;
    }

    RunHistoryDetailScreen #run-detail-back {
        width: 100%;
        margin-top: 1;
    }

    RunHistoryDetailScreen .round-history-heading {
        color: #58a6ff;
        text-style: bold;
        width: 100%;
        margin-top: 1;
    }

    RunHistoryDetailScreen .question-history-row {
        width: 100%;
        color: #c9d1d9;
    }
    """

    BINDINGS = [
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, run_id: int) -> None:
        super().__init__()
        self._run_id = run_id

    def compose(self) -> ComposeResult:
        detail = self.app.run_history_service.get_run(self._run_id)

        yield Header(show_clock=False)
        with DialogShell(id="run-detail-panel"):
            yield Label("RUN DETAILS", id="run-detail-title")
            if detail is None:
                yield Label("This saved run is no longer available.", id="run-detail-empty")
            else:
                yield Label(_format_run_summary(detail.run), id="run-detail-subtitle")
                yield VerticalScroll(*self._detail_widgets(detail), id="run-detail-content")
            yield Button("←  Back  [Esc]", id="run-detail-back", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#run-detail-back", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run-detail-back":
            self.app.pop_screen()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_quit(self) -> None:
        self.app.exit()

    @staticmethod
    def _detail_widgets(detail: RunHistoryDetail) -> list[Label]:
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
