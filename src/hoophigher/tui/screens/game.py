from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.content import Content
from textual.screen import Screen
from textual.widgets import Button

from hoophigher.domain.enums import GuessDirection
from hoophigher.domain.formatting import player_first_name, player_last_name
from hoophigher.domain.models import Question, QuestionResult
from hoophigher.services import GameplaySnapshot
from hoophigher.tui.responsive import Tier, tier_for
from hoophigher.tui.screens.game_over import GameOverScreen
from hoophigher.tui.screens.round_summary import RoundSummary, RoundSummaryScreen
from hoophigher.tui.widgets import (
    FooterHints,
    GameContextStrip,
    GuessBar,
    MatchupPanel,
    Scorebug,
    StatusStrip,
    hints,
)
from hoophigher.tui.widgets.gameplay import LastGuess

_FEEDBACK_DURATION_SECONDS = 1.2
_REVEAL_HELD_HINT = "[blink $warning]reveal held · next question in 1.2s…[/]"

_FOOTER_HINTS: dict[Tier, str] = {
    "full": hints(
        ("H", "higher"),
        ("L", "lower"),
        ("←/→", "move"),
        ("enter", "guess"),
        ("esc", "abandon"),
        ("Q", "quit"),
    ),
    "sm": hints(("H", ""), ("L", ""), ("←/→", ""), ("esc", ""), ("Q", "")),
    "xs": hints(("H/L", ""), ("esc", "home")),
}


@dataclass(slots=True)
class RoundTally:
    questions: int = 0
    correct_answers: int = 0
    wrong_answers: int = 0
    score_delta: int = 0

    def record(self, result: QuestionResult) -> None:
        self.questions += 1
        self.correct_answers += int(result.is_correct)
        self.wrong_answers += int(not result.is_correct)
        self.score_delta += result.score_delta


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

    GameScreen.-h-sm #game-scroll,
    GameScreen.-h-xs #game-scroll {
        overflow-y: auto;
        scrollbar-size-vertical: 0;
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
        self._round_tally = RoundTally()
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

        with Vertical(id="game-layout"):
            with Vertical(id="game-scroll"):
                yield self._context_strip
                yield self._matchup_panel
            yield StatusStrip(id="verdict-strip")
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

        self._round_tally.record(result)
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
        self._show_reveal(result, guess)

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
            previous_game = previous_snapshot.current_game
            summary = RoundSummary(
                round_index=self._snapshot.round_index - 1,
                game_id=previous_snapshot.game_id,
                source_date=previous_game.source_date,
                matchup=(
                    f"{previous_game.away_team.abbreviation} @ "
                    f"{previous_game.home_team.abbreviation}"
                ),
                questions=self._round_tally.questions,
                correct_answers=self._round_tally.correct_answers,
                wrong_answers=self._round_tally.wrong_answers,
                score_delta=self._round_tally.score_delta,
            )
            self._round_tally = RoundTally()
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
        # Copy (labels, hints, scorebug) also degrades on short terminals so
        # the pinned rows keep fitting; card layout is width-only — short-
        # but-wide terminals keep full cards and scroll instead.
        copy_tier = tier_for(width, height)
        layout_tier = tier_for(width)

        self._guess_bar.set_tier(copy_tier)
        self._scorebug.set_tier(copy_tier)
        self._footer.set_hints(_FOOTER_HINTS[copy_tier])
        self._matchup_panel.set_tier(layout_tier)

        question = self._snapshot.current_question
        if question is None:
            self._guess_bar.set_prompt("")
        else:
            self._guess_bar.set_prompt(self._build_compare_prompt(question, copy_tier))

    def _build_compare_prompt(self, question: Question, tier: Tier) -> Content:
        points = question.player_a.points
        if tier == "full":
            return Content.from_markup(
                "Did [bold]$b_name[/] score [bold]more[/] or [bold]fewer[/] "
                f"than $a_name's [$warning]{points}[/]?",
                b_name=player_last_name(question.player_b.player_name),
                a_name=player_first_name(question.player_a.player_name),
            )
        return Content.from_markup(f"More or fewer than [$warning]{points}[/]?")

    def _show_reveal(self, result: QuestionResult, guess: GuessDirection) -> None:
        """Reveal B's number, drop the verdict strip, flash the scorebug."""
        went_over = result.revealed_points > result.question.player_a.points
        self._matchup_panel.reveal(
            result.revealed_points,
            is_correct=result.is_correct,
            went_over=went_over,
        )

        signed_delta = f"{result.score_delta:+d}".replace("-", "−")
        strip = self.query_one("#verdict-strip", StatusStrip)
        if result.is_correct:
            strip.show(
                "-success",
                Content.from_markup(
                    "[bold $success]CALLED IT.[/]  $b_name went for "
                    f"{result.revealed_points} — that's {'over' if went_over else 'under'}.",
                    b_name=player_last_name(result.question.player_b.player_name),
                ),
                f"[bold $success]{signed_delta}[/]",
            )
        else:
            strip.show(
                "-danger",
                Content.from_markup(
                    f"[bold $error]ICE COLD.[/]  He dropped {result.revealed_points} "
                    f"— you said {guess.value}.",
                ),
                f"[bold $error]{signed_delta}[/]",
            )
            losing_button = "guess-higher" if guess is GuessDirection.HIGHER else "guess-lower"
            self._guess_bar.mark_wrong(losing_button)

        # The service has already advanced to the next question (and may have
        # started the next round), but the UI is still revealing this answer.
        # Refresh only scoring here; _present_question advances the counters.
        self._scorebug.update_scoring(self._snapshot)
        self._scorebug.show_scoring_event(is_gain=result.is_correct)
        self._footer.set_hints(_REVEAL_HELD_HINT)

    def _hide_feedback(self) -> None:
        self.query_one("#verdict-strip", StatusStrip).hide()
        self._guess_bar.clear_wrong()

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
