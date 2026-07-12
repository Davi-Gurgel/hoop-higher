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
    """One matchup card: dim label, bold name, muted meta, hero point total."""

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
    """

    def __init__(self, prefix: str, *, hidden_side: bool = False, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._prefix = prefix
        self._hidden_side = hidden_side

    def compose(self) -> ComposeResult:
        yield Static("", id=f"{self._prefix}-label", classes="player-label")
        yield Label("", id=f"{self._prefix}-name", classes="player-name-label", markup=False)
        yield Label("", id=f"{self._prefix}-meta", classes="player-meta-label", markup=False)
        yield Static("", id=f"{self._prefix}-pts", classes="player-pts-value")

    def show_player(self, *, name: str, team: str, minutes: int) -> None:
        if self._hidden_side:
            label = "PLAYER B · [$accent]HIDDEN[/]"
        else:
            label = "PLAYER A · LOCKED"
        self.query_one(f"#{self._prefix}-label", Static).update(Content.from_markup(label))
        self.query_one(f"#{self._prefix}-name", Label).update(name)
        self.query_one(f"#{self._prefix}-meta", Label).update(f"{team} · {minutes} min")
        if self._hidden_side:
            self.query_one(f"#{self._prefix}-pts", Static).update(
                Content.from_markup("[$hidden-glyph]— —[/][$dim] PTS[/]")
            )

    def show_points(self, points: int) -> None:
        self.query_one(f"#{self._prefix}-pts", Static).update(
            Content.from_markup(f"[bold $warning]{points}[/][$dim] PTS[/]")
        )

    def clear(self) -> None:
        self.query_one(f"#{self._prefix}-label", Static).update("")
        self.query_one(f"#{self._prefix}-name", Label).update("—")
        self.query_one(f"#{self._prefix}-meta", Label).update("")
        self.query_one(f"#{self._prefix}-pts", Static).update("")


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

    def reveal_points(self, points: int) -> None:
        self._player_b_card.show_points(points)


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

    def compose(self) -> ComposeResult:
        yield Static("", id="pb-compare")
        with Horizontal(id="guess-actions"):
            yield GuessButton(Content("▲ HIGHER [H]"), id="guess-higher", classes="guess-btn")
            yield GuessButton(Content("▼ LOWER [L]"), id="guess-lower", classes="guess-btn")

    def set_prompt(self, prompt: Content | str) -> None:
        self.query_one("#pb-compare", Static).update(prompt)

    def set_label_mode(self, mode: str) -> None:
        labels = {
            "full": ("▲ HIGHER [H]", "▼ LOWER [L]"),
            "compact": ("▲ HIGHER", "▼ LOWER"),
            "mini": ("▲ HI · H", "▼ LO · L"),
        }
        higher_text, lower_text = labels[mode]
        self.query_one("#guess-higher", Button).label = Content(higher_text)
        self.query_one("#guess-lower", Button).label = Content(lower_text)

    def set_buttons_disabled(self, disabled: bool) -> None:
        self.query_one("#guess-higher", Button).disabled = disabled
        self.query_one("#guess-lower", Button).disabled = disabled
