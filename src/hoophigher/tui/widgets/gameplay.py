"""Game screen widgets: context strip, matchup cards, and guess bar.

Hero point totals render as bold + color emphasis (the handoff default);
the hidden total is a dim `— —` placeholder so the reveal is a pure text
swap. Player-provided strings always render with markup disabled.
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import CenterMiddle, Horizontal, Vertical
from textual.content import Content
from textual.widgets import Button, Label, Static

from hoophigher.domain.models import NBAGame, Question
from hoophigher.services import GameplaySnapshot


def _last_name(full_name: str) -> str:
    parts = full_name.split()
    return parts[-1] if parts else full_name


def _first_name(full_name: str) -> str:
    parts = full_name.split()
    return parts[0] if parts else full_name


@dataclass(frozen=True, slots=True)
class LastGuess:
    """The context row's `last Morant 34 ›over› Curry 29 ✓ +100` record."""

    player_a_name: str
    player_a_points: int
    guessed_over: bool
    player_b_name: str
    player_b_points: int
    is_correct: bool
    score_delta: int


class GameContextStrip(Vertical):
    """Date + matchup row with the last-guess record, over a games-chip strip."""

    DEFAULT_CSS = """
    GameContextStrip {
        width: 100%;
        height: auto;
        padding: 0 2;
        border-bottom: solid $border;
    }

    GameContextStrip #context-meta {
        width: 100%;
        height: 1;
    }

    GameContextStrip #context-date {
        width: auto;
        content-align: left middle;
    }

    GameContextStrip #context-last-guess {
        width: 1fr;
        content-align: right middle;
        text-align: right;
    }

    GameContextStrip #games-strip {
        width: 100%;
        height: 3;
        margin-top: 1;
    }

    GameContextStrip .game-chip {
        width: auto;
        height: 3;
        padding: 0 2;
        margin-right: 1;
        border: round $border;
        color: $dim;
        content-align: center middle;
    }

    GameContextStrip .game-chip.-active {
        border: round $accent;
        color: $accent;
        text-style: bold;
    }

    GameContextStrip #games-strip-summary {
        width: 100%;
        height: 1;
        margin-top: 1;
        color: $dim;
        display: none;
    }

    /* sm (and very short terminals): games strip collapses to the active
       summary line. xs: strip and last-guess line drop entirely. */
    GameScreen.-w-sm GameContextStrip #games-strip,
    GameScreen.-w-xs GameContextStrip #games-strip,
    GameScreen.-h-xs GameContextStrip #games-strip {
        display: none;
    }

    GameScreen.-w-sm GameContextStrip #games-strip-summary,
    GameScreen.-h-xs GameContextStrip #games-strip-summary {
        display: block;
    }

    GameScreen.-w-xs GameContextStrip #context-last-guess,
    GameScreen.-w-xs GameContextStrip #games-strip-summary {
        display: none;
    }
    """

    def __init__(self, total_games: int, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._total_games = total_games

    def compose(self) -> ComposeResult:
        with Horizontal(id="context-meta"):
            yield Static("", id="context-date")
            yield Static("", id="context-last-guess")
        with Horizontal(id="games-strip"):
            for index in range(self._total_games):
                yield Static("", id=f"game-tab-{index}", classes="game-chip")
        yield Static("", id="games-strip-summary")

    def update_snapshot(self, snapshot: GameplaySnapshot) -> None:
        game = snapshot.current_game
        self.query_one("#context-date", Static).update(
            Content.from_markup(
                "[bold]$date[/]  [$dim]$matchup[/]",
                date=f"{game.source_date:%b %d, %Y}",
                matchup=(f"· {game.away_team.abbreviation} @ {game.home_team.abbreviation}"),
            )
        )
        self._update_chips(game.game_id, snapshot.games_today)

    def update_last_guess(self, last_guess: LastGuess | None) -> None:
        target = self.query_one("#context-last-guess", Static)
        if last_guess is None:
            target.update("")
            return
        direction = "over" if last_guess.guessed_over else "under"
        verdict = (
            f"[$success]✓ +{last_guess.score_delta}[/]"
            if last_guess.is_correct
            else f"[$error]✗ {last_guess.score_delta}[/]"
        )
        target.update(
            Content.from_markup(
                f"[$dim]last  $a_name $a_points [/][$accent]›{direction}›[/]"
                f"[$dim] $b_name $b_points  [/]{verdict}",
                a_name=_last_name(last_guess.player_a_name),
                a_points=str(last_guess.player_a_points),
                b_name=_last_name(last_guess.player_b_name),
                b_points=str(last_guess.player_b_points),
            )
        )

    def _update_chips(self, current_game_id: str, games_today: tuple[NBAGame, ...]) -> None:
        active_position = 0
        for index, game in enumerate(games_today):
            chip = self.query_one(f"#game-tab-{index}", Static)
            is_active = game.game_id == current_game_id
            if is_active:
                active_position = index
                away_score = "?" if game.away_team.score is None else game.away_team.score
                home_score = "?" if game.home_team.score is None else game.home_team.score
                text = (
                    f"{game.away_team.abbreviation} {away_score} · "
                    f"{game.home_team.abbreviation} {home_score}"
                )
            else:
                text = f"{game.away_team.abbreviation} · {game.home_team.abbreviation}"
            chip.update(Content(text))
            chip.set_class(is_active, "-active")

        active_game = games_today[active_position] if games_today else None
        if active_game is not None:
            summary = self.query_one("#games-strip-summary", Static)
            summary.update(
                Content.from_markup(
                    "[$accent]$matchup[/][$dim] · game $position/$total[/]",
                    matchup=(
                        f"{active_game.away_team.abbreviation} @ "
                        f"{active_game.home_team.abbreviation}"
                    ),
                    position=str(active_position + 1),
                    total=str(len(games_today)),
                )
            )


class PlayerCard(Vertical):
    """One matchup card: dim label, bold name, muted meta, hero point total.

    Renders from internal state so the xs tier can swap to a single compact
    row (`A LeBron James  LAL  34p`) without losing the reveal treatment.
    """

    DEFAULT_CSS = """
    PlayerCard {
        width: 100%;
        height: 100%;
        min-height: 10;
        padding: 1 2;
        background: $card-fill;
        border: round $border;
    }

    PlayerCard .player-label {
        width: 100%;
        color: $dim;
        margin-bottom: 1;
    }

    PlayerCard .player-name-label {
        width: 100%;
        text-style: bold;
    }

    PlayerCard .player-meta-label {
        width: 100%;
        color: $muted;
        margin-bottom: 1;
    }

    PlayerCard .player-pts-value {
        width: 100%;
    }

    PlayerCard .player-compact-line {
        width: 100%;
        display: none;
    }

    PlayerCard.-revealed-success {
        border: round $success;
        background: $success-fill;
    }

    PlayerCard.-revealed-danger {
        border: round $error;
        background: $danger-fill;
    }

    PlayerCard.-compact {
        border: none;
        background: transparent;
        padding: 0 1;
        min-height: 1;
        height: auto;
    }

    PlayerCard.-compact .player-label,
    PlayerCard.-compact .player-name-label,
    PlayerCard.-compact .player-meta-label,
    PlayerCard.-compact .player-pts-value {
        display: none;
    }

    PlayerCard.-compact .player-compact-line {
        display: block;
    }
    """

    def __init__(self, prefix: str, *, hidden_side: bool = False, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._prefix = prefix
        self._hidden_side = hidden_side
        self._tier = "full"
        self._name = "—"
        self._team = ""
        self._minutes: int | None = None
        self._points: int | None = None
        self._reveal_state: tuple[bool, bool] | None = None  # (is_correct, went_over)

    def compose(self) -> ComposeResult:
        yield Static("", id=f"{self._prefix}-label", classes="player-label")
        yield Label("", id=f"{self._prefix}-name", classes="player-name-label", markup=False)
        yield Label("", id=f"{self._prefix}-meta", classes="player-meta-label", markup=False)
        yield Static("", id=f"{self._prefix}-pts", classes="player-pts-value")
        yield Static("", id=f"{self._prefix}-compact", classes="player-compact-line")

    def on_mount(self) -> None:
        self._render_card()

    def show_player(self, *, name: str, team: str, minutes: int) -> None:
        self._name = name
        self._team = team
        self._minutes = minutes
        self._points = None
        self._reveal_state = None
        self._render_card()

    def show_points(self, points: int) -> None:
        self._points = points
        self._render_card()

    def reveal(self, points: int, *, is_correct: bool, went_over: bool) -> None:
        """Flip the hidden total to the real number and recolor the card."""
        self._points = points
        self._reveal_state = (is_correct, went_over)
        self._render_card()

    def clear(self) -> None:
        self._name = "—"
        self._team = ""
        self._minutes = None
        self._points = None
        self._reveal_state = None
        self._render_card()

    def set_tier(self, tier: str) -> None:
        if tier != self._tier:
            self._tier = tier
            self.set_class(tier == "xs", "-compact")
            self._render_card()

    def _render_card(self) -> None:
        if not self.is_mounted:
            return
        side = "B" if self._hidden_side else "A"
        if self._reveal_state is not None:
            is_correct, _went_over = self._reveal_state
            color = "$success" if is_correct else "$error"
            self.set_class(is_correct, "-revealed-success")
            self.set_class(not is_correct, "-revealed-danger")
            label = Content.from_markup(f"PLAYER B · [{color}]REVEALED[/]")
        else:
            self.remove_class("-revealed-success", "-revealed-danger")
            if self._hidden_side:
                label = Content.from_markup("PLAYER B · [$accent]HIDDEN[/]")
            else:
                label = Content.from_markup("PLAYER A · LOCKED")
        self.query_one(f"#{self._prefix}-label", Static).update(label)
        self.query_one(f"#{self._prefix}-name", Label).update(self._name)
        minutes_label = (
            ""
            if self._minutes is None
            else (f"{self._minutes} min" if self._tier == "full" else f"{self._minutes}m")
        )
        meta = f"{self._team} · {minutes_label}" if self._team else ""
        self.query_one(f"#{self._prefix}-meta", Label).update(meta)
        self.query_one(f"#{self._prefix}-pts", Static).update(self._points_markup(" PTS"))
        compact = Content.from_markup(
            "[$dim]$side[/] [bold]$name[/]  [$muted]$team[/]  ",
            side=side,
            name=self._name,
            team=self._team,
        )
        self.query_one(f"#{self._prefix}-compact", Static).update(
            compact + self._points_markup("p")
        )

    def _points_markup(self, unit: str) -> Content:
        if self._points is None:
            if self._hidden_side:
                glyph = "— —" if self._tier == "full" else "——"
                return Content.from_markup(f"[$hidden-glyph]{glyph}[/][$dim]{unit}[/]")
            return Content("")
        if self._reveal_state is not None:
            is_correct, went_over = self._reveal_state
            color = "$success" if is_correct else "$error"
            arrow = "▲" if went_over else "▼"
            return Content.from_markup(f"[bold {color}]{self._points} {arrow}[/][$dim]{unit}[/]")
        return Content.from_markup(f"[bold $warning]{self._points}[/][$dim]{unit}[/]")


class MatchupPanel(Vertical):
    DEFAULT_CSS = """
    MatchupPanel {
        width: 100%;
        height: auto;
        padding: 1 2;
    }

    MatchupPanel #matchup-content {
        width: 100%;
        height: auto;
    }

    MatchupPanel PlayerCard {
        width: 1fr;
        height: auto;
    }

    MatchupPanel #vs-divider {
        width: 6;
        height: 100%;
        min-height: 10;
    }

    MatchupPanel #vs-text {
        width: 100%;
        text-align: center;
        color: $dim;
    }

    MatchupPanel.-compact #matchup-content {
        layout: vertical;
    }

    MatchupPanel.-compact #vs-divider {
        width: 100%;
        height: 1;
        min-height: 1;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._player_a_card = PlayerCard("pa")
        self._player_b_card = PlayerCard("pb", hidden_side=True)

    def compose(self) -> ComposeResult:
        with Horizontal(id="matchup-content"):
            yield self._player_a_card
            with CenterMiddle(id="vs-divider"):
                yield Label("VS", id="vs-text")
            yield self._player_b_card

    def clear(self) -> None:
        self._player_a_card.clear()
        self._player_b_card.clear()

    def set_tier(self, tier: str) -> None:
        self.set_class(tier == "xs", "-compact")
        self._player_a_card.set_tier(tier)
        self._player_b_card.set_tier(tier)
        self.query_one("#vs-text", Label).update("— vs —" if tier == "xs" else "VS")

    def set_question(self, question: Question) -> None:
        self._player_a_card.show_player(
            name=question.player_a.player_name,
            team=question.player_a.team_abbreviation,
            minutes=question.player_a.minutes,
        )
        self._player_a_card.show_points(question.player_a.points)
        self._player_b_card.show_player(
            name=question.player_b.player_name,
            team=question.player_b.team_abbreviation,
            minutes=question.player_b.minutes,
        )

    def reveal(self, points: int, *, is_correct: bool, went_over: bool) -> None:
        self._player_b_card.reveal(points, is_correct=is_correct, went_over=went_over)


class GuessButton(Button, inherit_bindings=False):
    """Gameplay buttons keep focus, but let the screen own the Enter binding.

    Neither button carries green/red at rest — focus is the accent fill.
    """

    BINDINGS = []

    DEFAULT_CSS = """
    GuessButton, GuessButton.-style-default {
        width: 1fr;
        height: 3;
        min-width: 0;
        border: round $border;
        background: transparent;
        color: $muted;
        text-align: center;
        content-align: center middle;
        text-style: none;

        &:hover {
            border: round $muted;
            background: transparent;
        }

        &:focus {
            border: round $accent;
            background: $accent;
            color: $void;
            text-style: bold;
            background-tint: transparent;
        }

        &:disabled {
            border: round $border;
            background: transparent;
            color: $disabled-text;
            text-opacity: 1;
        }

        &.-wrong, &.-wrong:disabled {
            border: round $error;
            background: transparent;
            color: $error;
        }
    }
    """


class GuessBar(Vertical):
    DEFAULT_CSS = """
    GuessBar {
        width: 100%;
        height: auto;
        padding: 1 2;
    }

    GuessBar #pb-compare {
        width: 100%;
        text-align: center;
        color: $muted;
        margin-bottom: 1;
    }

    GuessBar #guess-actions {
        width: 100%;
        height: auto;
    }

    GuessBar .guess-btn {
        margin: 0 1;
    }
    """

    _LABELS = {
        "full": ("▲ HIGHER [H]", "▼ LOWER [L]"),
        "compact": ("▲ HIGHER", "▼ LOWER"),
        "mini": ("▲ HI · H", "▼ LO · L"),
    }

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._label_mode = "full"

    def compose(self) -> ComposeResult:
        yield Static("", id="pb-compare")
        with Horizontal(id="guess-actions"):
            yield GuessButton(Content("▲ HIGHER [H]"), id="guess-higher", classes="guess-btn")
            yield GuessButton(Content("▼ LOWER [L]"), id="guess-lower", classes="guess-btn")

    def set_prompt(self, prompt: Content | str) -> None:
        self.query_one("#pb-compare", Static).update(prompt)

    def set_label_mode(self, mode: str) -> None:
        self._label_mode = mode
        higher_text, lower_text = self._LABELS[mode]
        self.query_one("#guess-higher", Button).label = Content(higher_text)
        self.query_one("#guess-lower", Button).label = Content(lower_text)

    def mark_wrong(self, button_id: str) -> None:
        """Give the losing guess button a danger outline and a ✗ marker."""
        button = self.query_one(f"#{button_id}", Button)
        button.add_class("-wrong")
        button.label = Content(f"✗ {button.label.plain}")

    def clear_wrong(self) -> None:
        for button in self.query(GuessButton):
            button.remove_class("-wrong")
        self.set_label_mode(self._label_mode)

    def set_buttons_disabled(self, disabled: bool) -> None:
        self.query_one("#guess-higher", Button).disabled = disabled
        self.query_one("#guess-lower", Button).disabled = disabled
