from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.content import Content
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Label

from hoophigher.domain.enums import GuessDirection
from hoophigher.domain.models import Question
from hoophigher.services import GameplaySnapshot
from hoophigher.tui.widgets import (
    DialogShell,
    FooterHints,
    GameContextStrip,
    GuessBar,
    MatchupPanel,
    Scorebug,
    hints,
)
from hoophigher.tui.widgets.gameplay import LastGuess

_FEEDBACK_DURATION_SECONDS = 1.2

_FOOTER_HINTS = {
    "full": hints(
        ("H", "higher"),
        ("L", "lower"),
        ("←/→", "move"),
        ("enter", "guess"),
        ("esc", "abandon"),
        ("Q", "quit"),
    ),
    "compact": hints(("H", ""), ("L", ""), ("←/→", ""), ("esc", ""), ("Q", "")),
    "mini": hints(("H/L", ""), ("esc", "home")),
}


@dataclass(frozen=True, slots=True)
class GuessHistoryItem:
    index: int
    is_correct: bool
    score_delta: int


class GameOverScreen(ModalScreen[None]):
    """Shown when the run ends (arcade miss or user exit)."""

    DEFAULT_CSS = """
    GameOverScreen {
        align: center middle;
    }

    GameOverScreen #gameover-overlay {
        width: 56;
        border: heavy $error;
    }

    GameOverScreen #gameover-title {
        text-align: center;
        text-style: bold;
        color: $error;
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
        color: $warning;
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
            if s.source_date is not None:
                yield Label(
                    f"Date: {s.source_date:%d-%m-%Y}",
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
                    f"Reason: {s.end_reason.label}",
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
        background: $success-fill;
        color: $success;
        display: block;
    }

    GameScreen #feedback-bar.feedback-wrong {
        background: $danger-fill;
        color: $error;
        display: block;
    }

    GameScreen.-h-sm #game-scroll,
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
        self._history: list[GuessHistoryItem] = []
        self._round_history: list[GuessHistoryItem] = []
        self._last_guess: LastGuess | None = None
        self._awaiting_feedback = False
        self._game_over_screen_visible = False
        self._question_started_at: float | None = None
        self._scorebug = Scorebug(id="scorebug")
        self._context_strip = GameContextStrip(
            len(snapshot.games_today),
            id="day-games-panel",
        )
        self._matchup_panel = MatchupPanel(id="matchup-area")
        self._guess_bar = GuessBar(id="actions-panel")
        self._footer = FooterHints(id="game-footer")

    # ── Layout ────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield self._scorebug
        yield Label("", id="feedback-bar")

        with Vertical(id="game-layout"):
            with Vertical(id="game-scroll"):
                yield self._context_strip
                yield self._matchup_panel
            yield self._guess_bar

        yield self._footer

    # ── Lifecycle ──────────────────────────────────────────────

    def on_mount(self) -> None:
        self.query_one("#guess-higher", Button).focus()

    def on_screen_resume(self, _event: events.ScreenResume) -> None:
        """Present the current Question whenever this screen becomes active.

        Textual sends ScreenResume on the initial push and again when a
        covering screen (the Round Summary) pops, so time spent reading the
        summary never counts toward a response time.
        """
        if not self._awaiting_feedback and not self._snapshot.is_finished:
            self._present_question()

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
        response_time_ms = self._response_time_ms()
        self._question_started_at = None

        previous_snapshot = self._snapshot
        was_last_question = (
            previous_snapshot.question_index == previous_snapshot.total_questions - 1
        )

        result = await self.app.gameplay_service.submit_guess(
            guess,
            response_time_ms=response_time_ms,
        )

        history_item = GuessHistoryItem(
            index=previous_snapshot.question_index + 1,
            is_correct=result.is_correct,
            score_delta=result.score_delta,
        )
        self._history.append(history_item)
        self._round_history.append(history_item)
        self._last_guess = LastGuess(
            player_a_name=result.question.player_a.player_name,
            player_a_points=result.question.player_a.points,
            guessed_over=guess is GuessDirection.HIGHER,
            player_b_name=result.question.player_b.player_name,
            player_b_points=result.revealed_points,
            is_correct=result.is_correct,
            score_delta=result.score_delta,
        )

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
                source_date=previous_snapshot.current_game.source_date,
                questions=len(self._round_history),
                correct_answers=sum(1 for item in self._round_history if item.is_correct),
                wrong_answers=sum(1 for item in self._round_history if not item.is_correct),
                score_delta=sum(item.score_delta for item in self._round_history),
            )
            self._round_history.clear()
            self.app.push_screen(RoundSummaryScreen(summary))
            return

        self._present_question()

    # ── View helpers ──────────────────────────────────────────

    def _present_question(self) -> None:
        """Repaint the screen and start timing the answerable Question, if any."""
        self._refresh_view()
        question = self._snapshot.current_question
        self._question_started_at = None if question is None else monotonic()

    def _refresh_view(self) -> None:
        s = self._snapshot

        self._scorebug.update_snapshot(s)
        self._context_strip.update_snapshot(s)
        self._context_strip.update_last_guess(self._last_guess)

        question = s.current_question
        if question is None:
            self._matchup_panel.clear()
            self._guess_bar.set_prompt("")
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
        self._scorebug.set_tier({"full": "full", "compact": "sm", "mini": "xs"}[mode])
        self._footer.set_hints(_FOOTER_HINTS[mode])

        question = self._snapshot.current_question
        if question is None:
            self._guess_bar.set_prompt("")
        else:
            self._guess_bar.set_prompt(self._build_compare_prompt(question, mode))

    def _build_compare_prompt(self, question: Question, mode: str) -> Content:
        points = question.player_a.points
        if mode == "full":
            first_name = question.player_a.player_name.split()
            last_name = question.player_b.player_name.split()
            return Content.from_markup(
                "Did [bold]$b_name[/] score [bold]more[/] or [bold]fewer[/] "
                f"than $a_name's [$warning]{points}[/]?",
                b_name=last_name[-1] if last_name else question.player_b.player_name,
                a_name=first_name[0] if first_name else question.player_a.player_name,
            )
        return Content.from_markup(f"More or fewer than [$warning]{points}[/]?")

    def _show_reveal(self, revealed_points: int, is_correct: bool, score_delta: int) -> None:
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

    def _response_time_ms(self) -> int | None:
        """Elapsed answer time, or None when no Question timing was running."""
        if self._question_started_at is None:
            return None
        return int((monotonic() - self._question_started_at) * 1000)

    def _leave_run(self) -> None:
        self._snapshot = self.app.gameplay_service.end_run()
        self.app.pop_screen()
        self.app.pop_screen()
