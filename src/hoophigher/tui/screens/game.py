from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Header, Label

from hoophigher.domain.enums import GuessDirection
from hoophigher.services import GameplaySnapshot

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

    BINDINGS = [("enter", "go_home", "Home"), ("escape", "go_home", "Home")]

    def __init__(self, snapshot: GameplaySnapshot) -> None:
        super().__init__()
        self._snapshot = snapshot

    def compose(self) -> ComposeResult:
        s = self._snapshot
        with Vertical(id="gameover-overlay"):
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

    # ── Layout ────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)

        # Status bar
        with Horizontal(id="status-bar"):
            yield Label("", id="status-mode")
            yield Label("", id="status-score")
            yield Label("", id="status-streak")

        # Feedback flash (hidden by default via CSS display:none)
        yield Label("", id="feedback-bar")

        with Vertical(id="game-layout"):
            with Vertical(id="day-games-panel"):
                yield Label("", id="active-game-title")
                yield Label("", id="active-game-score")
                with Horizontal(id="games-tabs"):
                    for index, _game in enumerate(self._snapshot.games_today):
                        yield Label("", id=f"game-tab-{index}", classes="browser-tab")

            # Main matchup panel
            with Horizontal(id="matchup-area"):
                # Player A (left)
                with Vertical(id="player-a-half", classes="player-panel"):
                    with Vertical(classes="player-card"):
                        yield Label("", id="pa-name", classes="player-name-label player-name-primary")
                        yield Label("", id="pa-team", classes="player-team-label")
                        yield Label("", id="pa-pts", classes="player-pts-value")
                        yield Label("", id="pa-minutes", classes="player-minutes-label")

                # VS divider
                with Vertical(id="vs-divider"):
                    yield Label("VS", id="vs-text")

                # Player B (right)
                with Vertical(id="player-b-half", classes="player-panel"):
                    with Vertical(classes="player-card player-card-b"):
                        yield Label("", id="pb-name", classes="player-name-label player-name-primary")
                        yield Label("", id="pb-team", classes="player-team-label")
                        yield Label("? PTS", id="mystery-label")
                        yield Label("", id="pb-minutes", classes="player-minutes-label")
                        yield Label("", id="pb-compare", classes="compare-hint")
            with Vertical(id="actions-panel"):
                yield Label("Use H/L or ←/→ + Enter", id="controls-hint")
                with Horizontal(id="guess-actions"):
                    yield Button(
                        "▲  HIGHER  [H]",
                        id="guess-higher",
                        variant="success",
                        classes="guess-btn",
                    )
                    yield Button(
                        "▼  LOWER  [L]",
                        id="guess-lower",
                        variant="error",
                        classes="guess-btn",
                    )

        # Bottom info bar
        with Horizontal(id="info-bar"):
            yield Label("", id="progress-text")
            yield Label("", id="history-text")

        yield Footer()

    # ── Lifecycle ──────────────────────────────────────────────

    def on_mount(self) -> None:
        self._refresh_view()
        # Focus the higher button by default for arrow navigation
        self.query_one("#guess-higher", Button).focus()

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

        self.query_one("#status-mode", Label).update(
            f"  {s.mode.value.upper()}"
        )
        self.query_one("#status-score", Label).update(
            f"SCORE: {s.score}"
        )
        self.query_one("#status-streak", Label).update(
            f"STREAK: {s.current_streak}  (BEST: {s.best_streak})"
        )
        self._refresh_game_header()
        self._refresh_game_tabs()

        # Progress
        self.query_one("#progress-text", Label).update(
            f"Round {s.round_index + 1}  •  Q {s.question_index + 1}/{s.total_questions}"
        )

        # History text
        if self._history:
            last = self._history[-1]
            self.query_one("#history-text", Label).update(last.description)
        else:
            self.query_one("#history-text", Label).update("")

        question = s.current_question
        if question is None:
            self.query_one("#pa-name", Label).update("—")
            self.query_one("#pa-pts", Label).update("")
            self.query_one("#pa-team", Label).update("")
            self.query_one("#pa-minutes", Label).update("")
            self.query_one("#pb-name", Label).update("—")
            self.query_one("#mystery-label", Label).update("? PTS")
            self.query_one("#pb-team", Label).update("")
            self.query_one("#pb-minutes", Label).update("")
            self.query_one("#pb-compare", Label).update("")
            self._set_buttons_disabled(True)
            return

        # Player A — show team, name, points, minutes
        self.query_one("#pa-team", Label).update(
            question.player_a.team_abbreviation
        )
        self.query_one("#pa-name", Label).update(
            question.player_a.player_name.upper()
        )
        self.query_one("#pa-pts", Label).update(
            f"{question.player_a.points} PTS"
        )
        self.query_one("#pa-minutes", Label).update(
            f"{question.player_a.minutes} MIN"
        )

        # Player B — show team, name, hidden points
        self.query_one("#pb-team", Label).update(
            question.player_b.team_abbreviation
        )
        self.query_one("#pb-name", Label).update(
            question.player_b.player_name.upper()
        )
        self.query_one("#mystery-label", Label).update("? PTS")
        self.query_one("#pb-minutes", Label).update(
            f"{question.player_b.minutes} MIN"
        )
        self.query_one("#pb-compare", Label).update(
            f"More or fewer than {question.player_a.points} pts?"
        )

        self._set_buttons_disabled(False)
        self.query_one("#guess-higher", Button).focus()

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

        # Show revealed points on player B
        self.query_one("#mystery-label", Label).update(f"{revealed_points} PTS")

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
        self.query_one("#guess-higher", Button).disabled = disabled
        self.query_one("#guess-lower", Button).disabled = disabled

    def _leave_run(self) -> None:
        self._snapshot = self.app.gameplay_service.end_run()
        self.app.pop_screen()
        self.app.pop_screen()

    def _refresh_game_header(self) -> None:
        game = self._snapshot.current_game
        self.query_one("#active-game-title", Label).update(
            f"{game.away_team.abbreviation} @ {game.home_team.abbreviation}"
        )
        away_score = game.away_team.score if game.away_team.score is not None else "?"
        home_score = game.home_team.score if game.home_team.score is not None else "?"
        self.query_one("#active-game-score", Label).update(
            f"{game.away_team.abbreviation} {away_score}  •  {game.home_team.abbreviation} {home_score}"
        )

    def _refresh_game_tabs(self) -> None:
        current_game_id = self._snapshot.current_game.game_id
        for index, game in enumerate(self._snapshot.games_today):
            tab = self.query_one(f"#game-tab-{index}", Label)
            away_score = game.away_team.score if game.away_team.score is not None else "?"
            home_score = game.home_team.score if game.home_team.score is not None else "?"
            tab.update(
                f"{game.away_team.abbreviation} {away_score} | {game.home_team.abbreviation} {home_score}"
            )
            tab.remove_class("browser-tab-active")
            if game.game_id == current_game_id:
                tab.add_class("browser-tab-active")
