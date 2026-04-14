from __future__ import annotations

from dataclasses import dataclass

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Header, Label

from hoophigher.domain.enums import GuessDirection
from hoophigher.domain.models import Question
from hoophigher.services import GameplaySnapshot
from hoophigher.tui.widgets import (
    DialogShell,
    GameContextStrip,
    GameStatusStrip,
    GuessBar,
    MatchupPanel,
)

_MAX_HISTORY_ITEMS = 6
_FEEDBACK_DURATION_SECONDS = 1.2


@dataclass(frozen=True, slots=True)
class AnswerHistoryItem:
    index: int
    is_correct: bool
    score_delta: int
    description: str


class GameOverScreen(ModalScreen[None]):
    """Shown when the run ends (arcade miss or user exit)."""

    DEFAULT_CSS = """
    GameOverScreen {
        align: center middle;
    }

    GameOverScreen #gameover-overlay {
        width: 56;
        border: heavy #f85149;
    }

    GameOverScreen #gameover-title {
        text-align: center;
        text-style: bold;
        color: #f85149;
        width: 100%;
        margin-bottom: 1;
    }

    GameOverScreen .gameover-stat {
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }

    GameOverScreen .gameover-stat-highlight {
        text-align: center;
        text-style: bold;
        color: #f0883e;
        width: 100%;
        margin-bottom: 1;
    }

    GameOverScreen #gameover-home {
        width: 100%;
        margin-top: 1;
    }
    """

    BINDINGS = [("enter", "go_home", "Home"), ("escape", "go_home", "Home")]

    def __init__(self, snapshot: GameplaySnapshot) -> None:
        super().__init__()
        self._snapshot = snapshot

    def compose(self) -> ComposeResult:
        s = self._snapshot
        with DialogShell(id="gameover-overlay"):
            yield Label("GAME OVER", id="gameover-title")
            yield Label(
                f"Mode: {s.mode.value.upper()}",
                classes="gameover-stat",
            )
            yield Label(f"Final Score: {s.score}", classes="gameover-stat-highlight")
            yield Label(
                f"✓ {s.correct_answers}  ✕ {s.wrong_answers}",
                classes="gameover-stat",
            )
            yield Label(
                f"Best Streak: {s.best_streak}",
                classes="gameover-stat",
            )
            if s.end_reason is not None:
                yield Label(
                    f"Reason: {s.end_reason.value.replace('_', ' ').title()}",
                    classes="gameover-stat",
                )
            yield Button("Return Home [Enter]", id="gameover-home", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "gameover-home":
            self.action_go_home()

    def action_go_home(self) -> None:
        self.dismiss()
        self.app.pop_screen()  # GameScreen
        self.app.pop_screen()  # ModeSelectScreen


class GameScreen(Screen[None]):
    DEFAULT_CSS = """
    GameScreen #game-layout {
        width: 100%;
        height: 1fr;
    }

    GameScreen #game-scroll {
        width: 100%;
        height: 1fr;
        overflow-y: hidden;
    }

    GameScreen #feedback-bar {
        height: 3;
        width: 100%;
        padding: 1 2;
        text-align: center;
        text-style: bold;
        display: none;
    }

    GameScreen #feedback-bar.feedback-correct {
        background: #1a3a1a;
        color: #3fb950;
        display: block;
    }

    GameScreen #feedback-bar.feedback-wrong {
        background: #3a1a1a;
        color: #f85149;
        display: block;
    }

    GameScreen.-h-xs #game-scroll {
        overflow-y: auto;
    }
    """

    BINDINGS = [
        ("h", "guess_higher", "Higher"),
        ("l", "guess_lower", "Lower"),
        ("left", "focus_higher", "Focus Higher"),
        ("right", "focus_lower", "Focus Lower"),
        ("enter", "submit_focused_guess", "Confirm"),
        ("escape", "go_home", "Home"),
        ("q", "quit_run", "Quit"),
    ]

    def __init__(self, snapshot: GameplaySnapshot) -> None:
        super().__init__()
        self._snapshot = snapshot
        self._history: list[AnswerHistoryItem] = []
        self._round_history: list[AnswerHistoryItem] = []
        self._awaiting_feedback = False
        self._game_over_screen_visible = False
        self._status_strip = GameStatusStrip(id="status-bar")
        self._context_strip = GameContextStrip(
            len(snapshot.games_today),
            id="day-games-panel",
        )
        self._matchup_panel = MatchupPanel(id="matchup-area")
        self._guess_bar = GuessBar(id="actions-panel")

    # ── Layout ────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield self._status_strip
        yield Label("", id="feedback-bar")

        with Vertical(id="game-layout"):
            with Vertical(id="game-scroll"):
                yield self._context_strip
                yield self._matchup_panel
            yield self._guess_bar

        yield Footer()

    # ── Lifecycle ──────────────────────────────────────────────

    def on_mount(self) -> None:
        self._refresh_view()
        self.query_one("#guess-higher", Button).focus()

    def on_resize(self, event: events.Resize) -> None:
        self._sync_responsive_copy(event.size.width, event.size.height)

    # ── Actions ───────────────────────────────────────────────

    async def action_guess_higher(self) -> None:
        await self._submit_guess(GuessDirection.HIGHER)

    async def action_guess_lower(self) -> None:
        await self._submit_guess(GuessDirection.LOWER)

    def action_focus_higher(self) -> None:
        self.query_one("#guess-higher", Button).focus()

    def action_focus_lower(self) -> None:
        self.query_one("#guess-lower", Button).focus()

    async def action_submit_focused_guess(self) -> None:
        focused = self.focused
        if not isinstance(focused, Button):
            return
        if focused.id == "guess-higher":
            await self._submit_guess(GuessDirection.HIGHER)
        elif focused.id == "guess-lower":
            await self._submit_guess(GuessDirection.LOWER)

    def action_go_home(self) -> None:
        if self._snapshot.is_finished:
            self._show_game_over_screen()
            return
        self._leave_run()

    def action_quit_run(self) -> None:
        if not self._snapshot.is_finished:
            self._snapshot = self.app.gameplay_service.end_run()
        self.app.exit()

    # ── Button dispatch ───────────────────────────────────────

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "guess-higher":
            await self._submit_guess(GuessDirection.HIGHER)
        elif event.button.id == "guess-lower":
            await self._submit_guess(GuessDirection.LOWER)

    # ── Core guess logic ──────────────────────────────────────

    async def _submit_guess(self, guess: GuessDirection) -> None:
        if self._awaiting_feedback or self._snapshot.is_finished:
            return

        question = self._snapshot.current_question
        if question is None:
            return

        self._awaiting_feedback = True
        self._set_buttons_disabled(True)

        previous_snapshot = self._snapshot
        was_last_question = (
            previous_snapshot.question_index
            == previous_snapshot.total_questions - 1
        )

        result = await self.app.gameplay_service.submit_answer(guess)

        # Build history item
        history_item = AnswerHistoryItem(
            index=previous_snapshot.question_index + 1,
            is_correct=result.is_correct,
            score_delta=result.score_delta,
            description=(
                f"Q{previous_snapshot.question_index + 1}: "
                f"{result.question.player_a.player_name} vs "
                f"{result.question.player_b.player_name} "
                f"→ {'✓' if result.is_correct else '✕'} ({result.score_delta:+d})"
            ),
        )
        self._history.append(history_item)
        self._history = self._history[-_MAX_HISTORY_ITEMS:]
        self._round_history.append(history_item)

        self._snapshot = self.app.gameplay_service.snapshot()

        # Show reveal + feedback
        self._show_reveal(result.revealed_points, result.is_correct, result.score_delta)

        # After feedback delay, advance
        self.set_timer(
            _FEEDBACK_DURATION_SECONDS,
            lambda: self._after_feedback(was_last_question, previous_snapshot),
        )

    def _after_feedback(
        self,
        was_last_question: bool,
        previous_snapshot: GameplaySnapshot,
    ) -> None:
        self._awaiting_feedback = False
        self._hide_feedback()

        if self._snapshot.is_finished:
            self._show_game_over_screen()
            return

        if was_last_question and not self._snapshot.is_finished:
            from hoophigher.tui.screens.round_summary import (
                RoundSummary,
                RoundSummaryScreen,
            )

            summary = RoundSummary(
                round_index=self._snapshot.round_index - 1,
                game_id=previous_snapshot.game_id,
                questions=len(self._round_history),
                correct_answers=sum(
                    1 for item in self._round_history if item.is_correct
                ),
                wrong_answers=sum(
                    1 for item in self._round_history if not item.is_correct
                ),
                score_delta=sum(
                    item.score_delta for item in self._round_history
                ),
            )
            self._round_history.clear()
            self.app.push_screen(RoundSummaryScreen(summary))

        self._refresh_view()

    # ── View helpers ──────────────────────────────────────────

    def _refresh_view(self) -> None:
        s = self._snapshot

        self._status_strip.update_snapshot(s)
        self._context_strip.update_snapshot(s)

        if self._history:
            last = self._history[-1]
            self._context_strip.update_history(last.description)
        else:
            self._context_strip.update_history("")

        question = s.current_question
        if question is None:
            self._matchup_panel.clear()
            self._guess_bar.set_prompt("")
            self._guess_bar.set_controls_hint("Use H/L or ←/→ + Enter")
            self._set_buttons_disabled(True)
            self._sync_responsive_copy(self.size.width, self.size.height)
            return

        self._matchup_panel.set_question(question)
        self._set_buttons_disabled(False)
        self._sync_responsive_copy(self.size.width, self.size.height)
        self.query_one("#guess-higher", Button).focus()

    def _sync_responsive_copy(self, width: int, height: int) -> None:
        mode = "full"
        if width < 72 or height < 24:
            mode = "mini"
        elif width < 80 and height < 26:
            mode = "compact"

        self._guess_bar.set_label_mode(mode)

        question = self._snapshot.current_question
        if question is None:
            self._guess_bar.set_prompt("")
        else:
            self._guess_bar.set_prompt(self._build_compare_prompt(question, mode))

        controls_hint = {
            "full": "Use H/L or ←/→ + Enter",
            "compact": "H/L or ←/→ + Enter",
            "mini": "H/L or ←/→",
        }[mode]
        self._guess_bar.set_controls_hint(controls_hint)

    def _build_compare_prompt(self, question: Question, mode: str) -> str:
        if mode == "mini":
            return f"{question.player_b.player_name} vs {question.player_a.points} pts?"
        if mode == "compact":
            return (
                f"Did {question.player_b.player_name} score above or below "
                f"{question.player_a.points} pts?"
            )
        return (
            f"Did {question.player_b.player_name} score more or fewer than "
            f"{question.player_a.points} pts?"
        )

    def _show_reveal(
        self, revealed_points: int, is_correct: bool, score_delta: int
    ) -> None:
        """Flash feedback bar and reveal Player B's points."""
        feedback = self.query_one("#feedback-bar", Label)
        feedback.remove_class("feedback-correct", "feedback-wrong")

        if is_correct:
            feedback.update(f"✓  CORRECT!  +{score_delta} pts")
            feedback.add_class("feedback-correct")
        else:
            feedback.update(f"✕  WRONG!  {score_delta:+d} pts")
            feedback.add_class("feedback-wrong")

        self._matchup_panel.reveal_points(revealed_points)

    def _hide_feedback(self) -> None:
        feedback = self.query_one("#feedback-bar", Label)
        feedback.remove_class("feedback-correct", "feedback-wrong")
        feedback.update("")

    def _show_game_over_screen(self) -> None:
        if self._game_over_screen_visible:
            return
        self._game_over_screen_visible = True
        self.app.push_screen(GameOverScreen(self._snapshot))

    def _set_buttons_disabled(self, disabled: bool) -> None:
        self._guess_bar.set_buttons_disabled(disabled)

    def _leave_run(self) -> None:
        self._snapshot = self.app.gameplay_service.end_run()
        self.app.pop_screen()
        self.app.pop_screen()
