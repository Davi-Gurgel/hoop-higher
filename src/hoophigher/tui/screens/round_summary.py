from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


@dataclass(frozen=True, slots=True)
class RoundSummary:
    round_index: int
    game_id: str
    questions: int
    correct_answers: int
    wrong_answers: int
    score_delta: int


class RoundSummaryScreen(ModalScreen[None]):
    BINDINGS = [("enter", "continue_round", "Continue")]

    def __init__(self, summary: RoundSummary) -> None:
        super().__init__()
        self._summary = summary

    def compose(self) -> ComposeResult:
        with Vertical(id="summary-panel"):
            yield Label(f"Round {self._summary.round_index + 1} Complete", id="summary-title")
            yield Label(f"Game: {self._summary.game_id}")
            yield Label(
                f"Questions: {self._summary.questions} | Correct: {self._summary.correct_answers} | Wrong: {self._summary.wrong_answers}"
            )
            yield Label(f"Score Delta: {self._summary.score_delta}")
            yield Button("Continue", id="summary-continue", variant="success")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "summary-continue":
            self.dismiss()

    def action_continue_round(self) -> None:
        self.dismiss()
