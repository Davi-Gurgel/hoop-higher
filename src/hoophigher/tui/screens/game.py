from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Static

from hoophigher.domain.enums import GuessDirection
from hoophigher.services import GameplaySnapshot
from hoophigher.tui.screens.round_summary import RoundSummary, RoundSummaryScreen


@dataclass(frozen=True, slots=True)
class AnswerHistoryItem:
    index: int
    is_correct: bool
    score_delta: int
    description: str


class GameScreen(Screen[None]):
    BINDINGS = [
        ("h", "guess_higher", "Higher"),
        ("l", "guess_lower", "Lower"),
        ("escape", "go_home", "Home"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, snapshot: GameplaySnapshot) -> None:
        super().__init__()
        self._snapshot = snapshot
        self._history: list[AnswerHistoryItem] = []
        self._round_history: list[AnswerHistoryItem] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="game-layout"):
            yield Label("", id="status-line")
            with Horizontal(id="score-row"):
                yield Label("", id="score-label")
                yield Label("", id="mode-label")
                yield Label("", id="progress-label")
            with Vertical(id="question-panel"):
                yield Label("", id="question-player-a")
                yield Label("", id="question-player-b")
            with Horizontal(id="action-row"):
                yield Button("Higher [H]", id="guess-higher", variant="success")
                yield Button("Lower [L]", id="guess-lower", variant="error")
                yield Button("Home [Esc]", id="back-home")
            yield Static("", id="history-panel")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_view()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "guess-higher":
            await self._submit_guess(GuessDirection.HIGHER)
            return
        if event.button.id == "guess-lower":
            await self._submit_guess(GuessDirection.LOWER)
            return
        if event.button.id == "back-home":
            self.app.pop_screen()
            self.app.pop_screen()

    async def action_guess_higher(self) -> None:
        await self._submit_guess(GuessDirection.HIGHER)

    async def action_guess_lower(self) -> None:
        await self._submit_guess(GuessDirection.LOWER)

    def action_go_home(self) -> None:
        self.app.pop_screen()
        self.app.pop_screen()

    async def _submit_guess(self, guess: GuessDirection) -> None:
        if self._snapshot.is_finished:
            return

        question = self._snapshot.current_question
        if question is None:
            return

        previous_snapshot = self._snapshot
        was_last_question = previous_snapshot.question_index == previous_snapshot.total_questions - 1
        result = await self.app.gameplay_service.submit_answer(guess)
        history_item = AnswerHistoryItem(
            index=previous_snapshot.question_index + 1,
            is_correct=result.is_correct,
            score_delta=result.score_delta,
            description=(
                f"Q{previous_snapshot.question_index + 1}: "
                f"{result.question.player_a.player_name} vs {result.question.player_b.player_name} "
                f"-> {'OK' if result.is_correct else 'MISS'} ({result.score_delta:+d})"
            ),
        )
        self._history.append(history_item)
        self._history = self._history[-8:]
        self._round_history.append(history_item)

        self._snapshot = self.app.gameplay_service.snapshot()
        if was_last_question and not self._snapshot.is_finished:
            summary = RoundSummary(
                round_index=self._snapshot.round_index - 1,
                game_id=previous_snapshot.game_id,
                questions=len(self._round_history),
                correct_answers=sum(1 for item in self._round_history if item.is_correct),
                wrong_answers=sum(1 for item in self._round_history if not item.is_correct),
                score_delta=sum(item.score_delta for item in self._round_history),
            )
            self._round_history.clear()
            self.app.push_screen(RoundSummaryScreen(summary))

        self._refresh_view()

    def _refresh_view(self) -> None:
        status = self.query_one("#status-line", Label)
        score_label = self.query_one("#score-label", Label)
        mode_label = self.query_one("#mode-label", Label)
        progress_label = self.query_one("#progress-label", Label)
        player_a_label = self.query_one("#question-player-a", Label)
        player_b_label = self.query_one("#question-player-b", Label)
        history_panel = self.query_one("#history-panel", Static)
        higher = self.query_one("#guess-higher", Button)
        lower = self.query_one("#guess-lower", Button)

        score_label.update(
            f"Score: {self._snapshot.score} | Streak: {self._snapshot.current_streak} | Best: {self._snapshot.best_streak}"
        )
        mode_label.update(f"Mode: {self._snapshot.mode.value}")
        progress_label.update(
            f"Round {self._snapshot.round_index + 1} - Q {self._snapshot.question_index + 1}/{self._snapshot.total_questions}"
        )

        if self._snapshot.is_finished:
            status.update(f"Run Finished: {self._snapshot.end_reason.value if self._snapshot.end_reason else 'done'}")
            player_a_label.update("Press Esc to return to mode selection.")
            player_b_label.update("")
            higher.disabled = True
            lower.disabled = True
        else:
            question = self._snapshot.current_question
            if question is None:
                status.update("Loading next question...")
                player_a_label.update("")
                player_b_label.update("")
                return
            status.update(f"Run #{self._snapshot.run_id} | Game: {self._snapshot.game_id}")
            player_a_label.update(f"A: {question.player_a.player_name} - {question.player_a.points} pts")
            player_b_label.update(f"B: {question.player_b.player_name} - ? pts")
            higher.disabled = False
            lower.disabled = False

        history_lines = ["Recent Answers:"]
        if not self._history:
            history_lines.append("- no answers yet")
        else:
            history_lines.extend(f"- {item.description}" for item in reversed(self._history))
        history_panel.update("\n".join(history_lines))
