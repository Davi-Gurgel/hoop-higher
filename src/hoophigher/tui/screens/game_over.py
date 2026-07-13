"""Game Over modal: danger-toned STAT DESK panel over the dimmed game."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.widgets import Button, Static

from hoophigher.services import GameplaySnapshot
from hoophigher.tui.screens.modal import DeskModalScreen
from hoophigher.tui.widgets import DeskButton


class GameOverScreen(DeskModalScreen):
    """Shown when the run ends (arcade miss or user exit)."""

    DEFAULT_CSS = """
    GameOverScreen #gameover-overlay {
        border: round $error;
        background: $danger-fill;
    }

    GameOverScreen #gameover-actions {
        width: 100%;
        height: auto;
        align-horizontal: center;
    }

    GameOverScreen #gameover-header {
        width: 100%;
        height: 1;
        margin-bottom: 1;
    }

    GameOverScreen #gameover-title {
        width: 1fr;
    }

    GameOverScreen #gameover-reason {
        width: auto;
        color: $error;
    }

    GameOverScreen .gameover-stat {
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }

    /* Outline treatment inside a danger modal: focus stays muted, not the
       stock accent fill. */
    GameOverScreen #gameover-home {
        width: auto;

        &:focus {
            border: round $muted;
            background: transparent;
            color: $foreground;
        }
    }
    """

    BINDINGS = [("enter", "go_home", "Home"), ("escape", "go_home", "Home")]

    def __init__(self, snapshot: GameplaySnapshot) -> None:
        super().__init__()
        self._snapshot = snapshot

    def compose(self) -> ComposeResult:
        s = self._snapshot
        with Vertical(id="gameover-overlay", classes="desk-modal-panel"):
            with Horizontal(id="gameover-header"):
                yield Static(
                    f"[bold $error]GAME OVER[/][$dim] · {s.mode.value}[/]",
                    id="gameover-title",
                )
                # Display follows the glossary term ("Wrong Guess"), while the
                # persisted enum value stays "wrong_answer".
                yield Static(
                    "" if s.end_reason is None else s.end_reason.name.replace("_", " ").title(),
                    id="gameover-reason",
                )
            yield Static("[$dim]FINAL SCORE[/]", classes="gameover-stat")
            yield Static(f"[bold $warning]{s.score:,}[/]", classes="gameover-stat")
            yield Static(
                f"[$success]✓ {s.correct_answers} right[/][$dim] · [/]"
                f"[$error]✗ {s.wrong_answers} wrong[/][$dim] · [/]"
                f"best streak [bold]{s.best_streak}[/]",
                classes="gameover-stat",
            )
            yield Static("[$warning]Cooked — but respectable.[/]", classes="gameover-stat")
            with Horizontal(id="gameover-actions"):
                yield DeskButton(Content("▸ Return home [enter / esc]"), id="gameover-home")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "gameover-home":
            self.action_go_home()

    def action_go_home(self) -> None:
        self.dismiss()
        self.app.pop_screen()  # GameScreen
        self.app.pop_screen()  # ModeSelectScreen
