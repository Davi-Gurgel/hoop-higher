from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import CenterMiddle, Horizontal, Vertical
from textual.widgets import Button, Label

from hoophigher.domain.models import GameBoxScore, Question
from hoophigher.services import GameplaySnapshot


class GameStatusStrip(Horizontal):
    DEFAULT_CSS = """
    GameStatusStrip {
        height: 3;
        width: 100%;
        background: #161b22;
        border-bottom: solid #30363d;
        padding: 0 2;
    }

    GameStatusStrip #status-mode {
        width: 2fr;
        text-align: left;
        color: #f0883e;
        text-style: bold;
        content-align: left middle;
    }

    GameStatusStrip #status-score {
        width: 1fr;
        text-align: center;
        color: #58a6ff;
        text-style: bold;
        content-align: center middle;
    }

    GameStatusStrip #status-streak {
        width: 2fr;
        text-align: right;
        color: #3fb950;
        text-style: bold;
        content-align: right middle;
    }

    GameScreen.-w-xs GameStatusStrip {
        height: 2;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("", id="status-mode")
        yield Label("", id="status-score")
        yield Label("", id="status-streak")

    def update_snapshot(self, snapshot: GameplaySnapshot) -> None:
        self.query_one("#status-mode", Label).update(
            f"  {snapshot.mode.value.upper()}  •  ROUND {snapshot.round_index + 1}  •  Q {snapshot.question_index + 1}/{snapshot.total_questions}"
        )
        self.query_one("#status-score", Label).update(f"SCORE: {snapshot.score}")
        self.query_one("#status-streak", Label).update(
            f"STREAK: {snapshot.current_streak}  (BEST: {snapshot.best_streak})"
        )


class GameContextStrip(Vertical):
    DEFAULT_CSS = """
    GameContextStrip {
        width: 100%;
        height: auto;
        padding: 0 2 0 2;
        background: #11161d;
        border-bottom: solid #30363d;
    }

    GameContextStrip #context-meta {
        width: 100%;
        height: auto;
    }

    GameContextStrip #progress-text {
        width: 1fr;
        text-align: left;
        color: #8b949e;
        text-style: italic;
        content-align: left middle;
    }

    GameContextStrip #history-text {
        width: 100%;
        text-align: right;
        color: #8b949e;
        content-align: right middle;
    }

    GameContextStrip #active-game-title {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: #f0883e;
    }

    GameContextStrip #active-game-score {
        width: 100%;
        text-align: center;
        color: #8b949e;
        margin-bottom: 1;
    }

    GameContextStrip #games-tabs {
        width: 100%;
        height: 3;
    }

    GameContextStrip .browser-tab {
        width: auto;
        min-width: 18;
        height: 3;
        padding: 0 2;
        margin-right: 1;
        background: #161b22;
        color: #8b949e;
        border: round #30363d;
        text-align: center;
        content-align: center middle;
    }

    GameContextStrip .browser-tab-active {
        color: #f0f6fc;
        border: round #1f6feb;
        text-style: bold;
    }

    GameScreen.-w-sm GameContextStrip .browser-tab,
    GameScreen.-h-sm GameContextStrip .browser-tab {
        min-width: 14;
        padding: 0 1;
    }

    GameScreen.-w-xs GameContextStrip,
    GameScreen.-h-xs GameContextStrip {
        padding: 0 1 0 1;
    }

    GameScreen.-w-xs GameContextStrip #active-game-score,
    GameScreen.-h-xs GameContextStrip #active-game-score,
    GameScreen.-w-xs GameContextStrip #games-tabs,
    GameScreen.-h-xs GameContextStrip #games-tabs,
    GameScreen.-w-xs GameContextStrip #history-text,
    GameScreen.-h-xs GameContextStrip #history-text {
        display: none;
    }
    """

    def __init__(self, total_games: int, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._total_games = total_games

    def compose(self) -> ComposeResult:
        with Horizontal(id="context-meta"):
            yield Label("", id="history-text")
        yield Label("", id="active-game-title")
        yield Label("", id="active-game-score")
        with Horizontal(id="games-tabs"):
            for index in range(self._total_games):
                yield Label("", id=f"game-tab-{index}", classes="browser-tab")

    def update_snapshot(self, snapshot: GameplaySnapshot) -> None:
        self._update_header(snapshot.current_game)
        self._update_tabs(snapshot.current_game.game_id, snapshot.games_today)

    def update_history(self, text: str) -> None:
        self.query_one("#history-text", Label).update(text)

    def _update_header(self, game: GameBoxScore) -> None:
        self.query_one("#active-game-title", Label).update(
            f"{game.away_team.abbreviation} @ {game.home_team.abbreviation}"
        )
        away_score = game.away_team.score if game.away_team.score is not None else "?"
        home_score = game.home_team.score if game.home_team.score is not None else "?"
        self.query_one("#active-game-score", Label).update(
            f"{game.away_team.abbreviation} {away_score}  •  {game.home_team.abbreviation} {home_score}"
        )

    def _update_tabs(self, current_game_id: str, games_today: tuple[GameBoxScore, ...]) -> None:
        for index, game in enumerate(games_today):
            tab = self.query_one(f"#game-tab-{index}", Label)
            away_score = game.away_team.score if game.away_team.score is not None else "?"
            home_score = game.home_team.score if game.home_team.score is not None else "?"
            tab.update(
                f"{game.away_team.abbreviation} {away_score} | {game.home_team.abbreviation} {home_score}"
            )
            tab.remove_class("browser-tab-active")
            if game.game_id == current_game_id:
                tab.add_class("browser-tab-active")


class PlayerCard(Vertical):
    DEFAULT_CSS = """
    PlayerCard {
        width: 100%;
        height: 100%;
        min-height: 14;
        padding: 1 3;
        background: #161b22;
        border: round #30363d;
        content-align: center middle;
    }

    PlayerCard.player-card-b {
        background: #162226;
    }

    PlayerCard .player-name-label {
        text-align: center;
        text-style: bold;
        color: #f0f6fc;
        width: 100%;
        margin-bottom: 0;
    }

    PlayerCard .player-team-label {
        text-align: center;
        color: #8b949e;
        width: 100%;
        margin-bottom: 1;
    }

    PlayerCard .player-pts-value,
    PlayerCard #mystery-label {
        text-align: center;
        text-style: bold;
        color: #58a6ff;
        width: 100%;
        margin-bottom: 1;
    }

    PlayerCard .player-minutes-label {
        text-align: center;
        color: #58a6ff;
        width: 100%;
        margin-top: 1;
    }

    GameScreen.-w-xs PlayerCard,
    GameScreen.-h-xs PlayerCard {
        min-height: 10;
        padding: 1 2;
    }
    """

    def __init__(self, prefix: str, *, secondary: bool = False, **kwargs: object) -> None:
        classes = kwargs.pop("classes", "")
        classes = f"{classes} player-card-b".strip() if secondary else classes
        super().__init__(classes=classes, **kwargs)
        self._prefix = prefix
        self._points_id = "mystery-label" if prefix == "pb" else f"{prefix}-pts"

    def compose(self) -> ComposeResult:
        yield Label("", id=f"{self._prefix}-name", classes="player-name-label")
        yield Label("", id=f"{self._prefix}-team", classes="player-team-label")
        yield Label("", id=self._points_id, classes="player-pts-value")
        yield Label("", id=f"{self._prefix}-minutes", classes="player-minutes-label")

    def update_content(self, *, name: str, team: str, points: str, minutes: str) -> None:
        self.query_one(f"#{self._prefix}-name", Label).update(name)
        self.query_one(f"#{self._prefix}-team", Label).update(team)
        self.query_one(f"#{self._points_id}", Label).update(points)
        self.query_one(f"#{self._prefix}-minutes", Label).update(minutes)


class MatchupPanel(Vertical):
    DEFAULT_CSS = """
    MatchupPanel {
        width: 100%;
        height: 1fr;
        min-height: 16;
        padding: 1 4;
    }

    MatchupPanel #matchup-content {
        width: 100%;
        height: 100%;
        min-height: 16;
    }

    MatchupPanel .player-panel {
        width: 1fr;
        height: 100%;
        content-align: center middle;
    }

    MatchupPanel #player-a-half,
    MatchupPanel #player-b-half {
        width: 1fr;
        height: 100%;
        padding: 0 1;
    }

    MatchupPanel #vs-divider {
        width: 6;
        height: 100%;
    }

    MatchupPanel #vs-text {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: #f0883e;
        content-align: center middle;
    }

    GameScreen.-w-xs MatchupPanel,
    GameScreen.-h-xs MatchupPanel {
        min-height: 12;
        padding: 0 1;
    }

    GameScreen.-w-xs MatchupPanel #matchup-content {
        layout: vertical;
        min-height: 12;
    }

    GameScreen.-w-xs MatchupPanel #vs-divider {
        width: 100%;
        height: 3;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._player_a_card = PlayerCard("pa")
        self._player_b_card = PlayerCard("pb", secondary=True)

    def compose(self) -> ComposeResult:
        with Horizontal(id="matchup-content"):
            with Vertical(id="player-a-half", classes="player-panel"):
                yield self._player_a_card
            with CenterMiddle(id="vs-divider"):
                yield Label("VS", id="vs-text")
            with Vertical(id="player-b-half", classes="player-panel"):
                yield self._player_b_card

    def clear(self) -> None:
        self._player_a_card.update_content(name="—", team="", points="", minutes="")
        self._player_b_card.update_content(name="—", team="", points="? PTS", minutes="")

    def set_question(self, question: Question) -> None:
        self._player_a_card.update_content(
            name=question.player_a.player_name.upper(),
            team=question.player_a.team_abbreviation,
            points=f"{question.player_a.points} PTS",
            minutes=f"{question.player_a.minutes} MIN",
        )
        self._player_b_card.update_content(
            name=question.player_b.player_name.upper(),
            team=question.player_b.team_abbreviation,
            points="? PTS",
            minutes=f"{question.player_b.minutes} MIN",
        )

    def reveal_points(self, points: int) -> None:
        self._player_b_card.update_content(
            name=self.query_one("#pb-name", Label).visual.plain,
            team=self.query_one("#pb-team", Label).visual.plain,
            points=f"{points} PTS",
            minutes=self.query_one("#pb-minutes", Label).visual.plain,
        )


class GuessBar(Vertical):
    DEFAULT_CSS = """
    GuessBar {
        width: 100%;
        height: auto;
        padding: 1 2 2 2;
    }

    GuessBar #pb-compare {
        text-align: center;
        color: #79c0ff;
        width: 100%;
        margin-bottom: 1;
    }

    GuessBar #controls-hint {
        text-align: center;
        color: #58a6ff;
        width: 100%;
        margin: 1 0;
    }

    GuessBar #guess-actions {
        width: 100%;
        height: auto;
    }

    GuessBar .guess-btn {
        width: 1fr;
        min-height: 3;
        margin: 0 1;
    }

    GameScreen.-w-sm GuessBar {
        padding: 1 1 1 1;
    }

    GameScreen.-w-xs GuessBar,
    GameScreen.-h-xs GuessBar {
        padding: 1 1 1 1;
    }

    GameScreen.-w-xs GuessBar #controls-hint,
    GameScreen.-h-xs GuessBar #controls-hint {
        display: none;
    }

    GameScreen.-w-xs GuessBar .guess-btn,
    GameScreen.-h-xs GuessBar .guess-btn {
        margin: 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("", id="pb-compare")
        yield Label("Use H/L or ←/→ + Enter", id="controls-hint")
        with Horizontal(id="guess-actions"):
            yield Button("▲  HIGHER  [H]", id="guess-higher", variant="success", classes="guess-btn")
            yield Button("▼  LOWER  [L]", id="guess-lower", variant="error", classes="guess-btn")

    def set_prompt(self, text: str) -> None:
        self.query_one("#pb-compare", Label).update(text)

    def set_controls_hint(self, text: str) -> None:
        self.query_one("#controls-hint", Label).update(text)

    def set_label_mode(self, mode: str) -> None:
        labels = {
            "full": ("▲  HIGHER  [H]", "▼  LOWER  [L]"),
            "compact": ("▲  HIGHER", "▼  LOWER"),
            "mini": ("▲ H", "▼ L"),
        }
        higher_text, lower_text = labels[mode]
        self.query_one("#guess-higher", Button).label = higher_text
        self.query_one("#guess-lower", Button).label = lower_text

    def set_buttons_disabled(self, disabled: bool) -> None:
        self.query_one("#guess-higher", Button).disabled = disabled
        self.query_one("#guess-lower", Button).disabled = disabled
