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
        s = self._summary
        sign = "+" if s.score_delta >= 0 else ""
        with Vertical(id="summary-overlay"):
            yield Label(f"ROUND {s.round_index + 1} COMPLETE", id="summary-title")
            yield Label(f"Game: {s.game_id}", classes="summary-stat")
            yield Label(
                f"✓ {s.correct_answers}   ✕ {s.wrong_answers}   ({s.questions} questions)",
                classes="summary-stat",
            )
            yield Label(
                f"Score Delta: {sign}{s.score_delta}",
                classes="summary-stat-highlight",
            )
            yield Button("Continue  [Enter]", id="summary-continue", variant="success")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "summary-continue":
            self.dismiss()

    def action_continue_round(self) -> None:
        self.dismiss()
