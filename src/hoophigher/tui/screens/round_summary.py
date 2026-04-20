from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from hoophigher.tui.widgets import DialogShell


@dataclass(frozen=True, slots=True)
class RoundSummary:
    round_index: int
    game_id: str
    game_date: date
    questions: int
    correct_answers: int
    wrong_answers: int
    score_delta: int


class RoundSummaryScreen(ModalScreen[None]):
    DEFAULT_CSS = """
    RoundSummaryScreen {
        align: center middle;
    }

    RoundSummaryScreen #summary-overlay {
        width: 56;
        border: heavy #f0883e;
    }

    RoundSummaryScreen #summary-title {
        text-align: center;
        text-style: bold;
        color: #f0883e;
        width: 100%;
        margin-bottom: 1;
    }

    RoundSummaryScreen .summary-stat {
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }

    RoundSummaryScreen .summary-stat-highlight {
        text-align: center;
        text-style: bold;
        color: #58a6ff;
        width: 100%;
        margin-bottom: 1;
    }

    RoundSummaryScreen #summary-continue {
        width: 100%;
        margin-top: 1;
    }
    """

    BINDINGS = [("enter", "continue_round", "Continue")]

    def __init__(self, summary: RoundSummary) -> None:
        super().__init__()
        self._summary = summary

    def compose(self) -> ComposeResult:
        s = self._summary
        sign = "+" if s.score_delta >= 0 else ""
        with DialogShell(id="summary-overlay"):
            yield Label(f"ROUND {s.round_index + 1} COMPLETE", id="summary-title")
            yield Label(f"Game: {s.game_id}", classes="summary-stat")
            yield Label(f"Date: {s.game_date:%d-%m-%Y}", classes="summary-stat")
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
