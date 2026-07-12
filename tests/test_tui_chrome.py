from __future__ import annotations

import asyncio
from datetime import date

from textual.app import App, ComposeResult
from textual.widgets import Static

from hoophigher.domain.enums import GameMode
from hoophigher.domain.models import NBAGame, TeamGameInfo
from hoophigher.services import GameplaySnapshot
from hoophigher.tui.theme import THEME_VARIABLE_DEFAULTS
from hoophigher.tui.widgets import FooterHints, HeaderBand, Scorebug, hints


def _snapshot(**overrides) -> GameplaySnapshot:
    game = NBAGame(
        game_id="game-1",
        source_date=date(2025, 4, 12),
        home_team=TeamGameInfo(team_id="den", name="Denver", abbreviation="DEN", score=109),
        away_team=TeamGameInfo(team_id="lal", name="Lakers", abbreviation="LAL", score=105),
        player_lines=(),
    )
    values = dict(
        run_id=1,
        round_id=1,
        mode=GameMode.ENDLESS,
        source_date=date(2025, 4, 12),
        score=640,
        current_streak=4,
        best_streak=6,
        correct_answers=6,
        wrong_answers=1,
        end_reason=None,
        game_id="game-1",
        current_game=game,
        games_today=(game,),
        round_index=1,
        question_index=2,
        total_questions=5,
        current_question=None,
    )
    values.update(overrides)
    return GameplaySnapshot(**values)


class _ChromeApp(App[None]):
    def get_theme_variable_defaults(self) -> dict[str, str]:
        return THEME_VARIABLE_DEFAULTS

    def compose(self) -> ComposeResult:
        yield Scorebug(id="scorebug")
        yield HeaderBand("LEADERBOARD", "top 10 · this machine", id="band")
        yield FooterHints(id="footer-hints")


def test_scorebug_renders_run_and_score_sides() -> None:
    async def scenario() -> None:
        app = _ChromeApp()
        async with app.run_test() as pilot:
            scorebug = app.query_one("#scorebug", Scorebug)
            scorebug.update_snapshot(_snapshot())
            await pilot.pause()

            run_text = app.query_one("#scorebug-run", Static).visual.plain
            score_text = app.query_one("#scorebug-score", Static).visual.plain
            assert "HOOP HIGHER" in run_text
            assert "ENDLESS" in run_text
            assert "round 2" in run_text
            assert "Q 3/5" in run_text
            assert "score 640" in score_text
            assert "streak 4" in score_text
            assert "best 6" in score_text

    asyncio.run(scenario())


def test_scorebug_flash_shows_gain_marker_then_settles() -> None:
    async def scenario() -> None:
        app = _ChromeApp()
        async with app.run_test() as pilot:
            scorebug = app.query_one("#scorebug", Scorebug)
            scorebug.update_snapshot(_snapshot(score=740, current_streak=5))
            scorebug.show_scoring_event(is_gain=True)
            await pilot.pause()

            score_text = app.query_one("#scorebug-score", Static).visual.plain
            assert "740 ▲" in score_text

            await pilot.pause(1.0)
            score_text = app.query_one("#scorebug-score", Static).visual.plain
            assert "▲" not in score_text
            assert "740" in score_text

    asyncio.run(scenario())


def test_scorebug_tiers_abbreviate() -> None:
    async def scenario() -> None:
        app = _ChromeApp()
        async with app.run_test() as pilot:
            scorebug = app.query_one("#scorebug", Scorebug)
            scorebug.update_snapshot(_snapshot())

            scorebug.set_tier("sm")
            await pilot.pause()
            run_text = app.query_one("#scorebug-run", Static).visual.plain
            assert "E" in run_text
            assert "ENDLESS" not in run_text
            assert "Q3/5" in run_text

            scorebug.set_tier("xs")
            await pilot.pause()
            run_text = app.query_one("#scorebug-run", Static).visual.plain
            score_text = app.query_one("#scorebug-score", Static).visual.plain
            assert run_text.strip() == "HOOP HIGHER"
            assert "★4" in score_text

    asyncio.run(scenario())


def test_header_band_shows_back_hint_title_and_subtitle() -> None:
    async def scenario() -> None:
        app = _ChromeApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            band_text = app.query_one("#header-band-text", Static).visual.plain
            assert "‹ back" in band_text
            assert "LEADERBOARD" in band_text
            assert "top 10 · this machine" in band_text

    asyncio.run(scenario())


def test_footer_hints_renders_key_pairs() -> None:
    async def scenario() -> None:
        app = _ChromeApp()
        async with app.run_test() as pilot:
            footer = app.query_one("#footer-hints", FooterHints)
            footer.set_hints(hints(("H", "higher"), ("L", "lower"), ("esc", "abandon")))
            await pilot.pause()
            assert footer.visual.plain == "H higher · L lower · esc abandon"

    asyncio.run(scenario())
