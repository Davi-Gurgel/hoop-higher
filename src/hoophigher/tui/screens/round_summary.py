from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.widgets import Button, Rule, Static

from hoophigher.tui.screens.modal import DeskModalScreen
from hoophigher.tui.widgets import DeskButton


@dataclass(frozen=True, slots=True)
class RoundSummary:
    round_index: int
    game_id: str
    source_date: date
    matchup: str
    questions: int
    correct_answers: int
    wrong_answers: int
    score_delta: int


class RoundSummaryScreen(DeskModalScreen):
    DEFAULT_CSS = """
    RoundSummaryScreen #summary-overlay {
        border: round $accent;
        background: $accent-fill;
    }

    RoundSummaryScreen .summary-split {
        width: 100%;
        height: 1;
    }

    RoundSummaryScreen .summary-split .split-left {
        width: 1fr;
    }

    RoundSummaryScreen .summary-split .split-right {
        width: auto;
    }

    RoundSummaryScreen #summary-rule {
        color: $border;
        margin: 0;
    }

    RoundSummaryScreen #summary-stats {
        margin-top: 1;
    }

    RoundSummaryScreen #summary-flavor {
        width: 100%;
        margin-top: 1;
    }

    /* The single action stays a solid accent fill in every state. */
    RoundSummaryScreen #summary-continue {
        width: auto;
        margin-top: 1;
        border: round $accent;
        background: $accent;
        color: $void;
        text-style: bold;
    }
    """

    BINDINGS = [("enter", "continue_round", "Continue")]

    def __init__(self, summary: RoundSummary) -> None:
        super().__init__()
        self._summary = summary

    def compose(self) -> ComposeResult:
        s = self._summary
        signed_delta = f"{s.score_delta:+d}".replace("-", "−")
        delta_color = "$success" if s.score_delta >= 0 else "$error"
        with Vertical(id="summary-overlay", classes="desk-modal-panel"):
            with Horizontal(classes="summary-split"):
                yield Static(
                    f"[bold $accent]ROUND {s.round_index + 1} · COMPLETE[/]",
                    classes="split-left",
                )
                yield Static(
                    Content.from_markup("[$muted]$matchup[/]", matchup=s.matchup),
                    classes="split-right",
                )
            yield Rule(id="summary-rule")
            with Horizontal(classes="summary-split", id="summary-stats"):
                yield Static(
                    f"[$success]✓ {s.correct_answers} right[/]   "
                    f"[$error]✗ {s.wrong_answers} wrong[/]",
                    classes="split-left",
                )
                yield Static(
                    f"[$dim]round [/][bold {delta_color}]{signed_delta}[/]",
                    classes="split-right",
                )
            yield Static("Next round pulls a different game. Stay hot.", id="summary-flavor")
            yield DeskButton(Content("▸ Continue [enter]"), id="summary-continue")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "summary-continue":
            self.dismiss()

    def action_continue_round(self) -> None:
        self.dismiss()
