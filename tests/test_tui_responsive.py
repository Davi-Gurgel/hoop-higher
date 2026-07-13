from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone

import pytest
from sqlmodel import Session
from textual.geometry import Size
from textual.widget import Widget
from textual.widgets import Button

from hoophigher.app import HoopHigherApp
from hoophigher.data import (
    QuestionRecord,
    RoundRecord,
    RunRecord,
    create_sqlite_engine,
    init_db,
)
from hoophigher.domain.enums import GameMode
from hoophigher.tui.screens import RunHistoryDetailScreen

TERMINAL_SIZES: tuple[Size, ...] = (
    Size(140, 40),
    Size(110, 32),
    Size(90, 26),
    Size(72, 24),
)

TARGET_TINY_SIZE = Size(60, 20)

RESPONSIVE_TARGET_SIZES: tuple[Size, ...] = (
    *TERMINAL_SIZES,
    Size(60, 20),
)


@pytest.fixture(autouse=True)
def _use_mock_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOOPHIGHER_STATS_PROVIDER", "mock")


def _widget_fits_terminal(widget: Widget, size: Size) -> None:
    region = widget.region
    assert region.width > 0
    assert region.height > 0
    assert region.right <= size.width
    assert region.bottom <= size.height


def _seed_run_history_detail(database_url: str) -> int:
    engine = create_sqlite_engine(database_url)
    init_db(engine)
    with Session(engine) as session:
        run = RunRecord(
            mode=GameMode.ENDLESS,
            source_date=date(2025, 1, 12),
            final_score=340,
            correct_answers=2,
            wrong_answers=0,
            best_streak=2,
            end_reason="user_exit",
            created_at=datetime(2025, 1, 3, 9, 0, tzinfo=timezone.utc),
        )
        session.add(run)
        session.flush()
        assert run.id is not None

        round_record = RoundRecord(
            run_id=run.id,
            round_index=0,
            game_id="game-1",
            game_date=date(2025, 1, 12),
            total_questions=2,
            correct_answers=2,
            wrong_answers=0,
            score_delta=340,
        )
        session.add(round_record)
        session.flush()
        assert round_record.id is not None

        session.add_all(
            [
                QuestionRecord(
                    run_id=run.id,
                    round_id=round_record.id,
                    question_index=0,
                    player_a_id="a1",
                    player_a_name="Player A1",
                    player_a_team_id="home",
                    player_a_team_abbreviation="HOM",
                    player_a_points=20,
                    player_a_minutes=30,
                    player_b_id="b1",
                    player_b_name="Player B1",
                    player_b_team_id="away",
                    player_b_team_abbreviation="AWY",
                    player_b_points=24,
                    player_b_minutes=31,
                    difficulty="medium",
                    guess="higher",
                    is_correct=True,
                    score_delta=100,
                    revealed_points=24,
                    response_time_ms=900,
                ),
                QuestionRecord(
                    run_id=run.id,
                    round_id=round_record.id,
                    question_index=1,
                    player_a_id="a2",
                    player_a_name="Player A2",
                    player_a_team_id="home",
                    player_a_team_abbreviation="HOM",
                    player_a_points=18,
                    player_a_minutes=28,
                    player_b_id="b2",
                    player_b_name="Player B2",
                    player_b_team_id="away",
                    player_b_team_abbreviation="AWY",
                    player_b_points=12,
                    player_b_minutes=27,
                    difficulty="easy",
                    guess="lower",
                    is_correct=True,
                    score_delta=240,
                    revealed_points=12,
                    response_time_ms=1100,
                ),
            ]
        )
        session.commit()
        return run.id


def test_home_screen_primary_actions_render_across_terminal_sizes() -> None:
    async def scenario() -> None:
        for size in RESPONSIVE_TARGET_SIZES:
            app = HoopHigherApp(database_url="sqlite://")

            async with app.run_test(size=(size.width, size.height)) as pilot:
                await pilot.pause()

                for button_id in (
                    "#start-game",
                    "#open-leaderboard",
                    "#open-stats",
                    "#open-run-history",
                    "#quit-game",
                ):
                    _widget_fits_terminal(app.screen.query_one(button_id, Button), size)
                assert getattr(app.screen.focused, "id", None) == "start-game"

    asyncio.run(scenario())


def test_run_history_screens_render_across_terminal_sizes(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'responsive-run-history.db'}"
    run_id = _seed_run_history_detail(database_url)

    async def scenario() -> None:
        for size in RESPONSIVE_TARGET_SIZES:
            app = HoopHigherApp(database_url=database_url)

            async with app.run_test(size=(size.width, size.height)) as pilot:
                await pilot.press("h")
                await pilot.pause()
                _widget_fits_terminal(app.screen.query_one("#run-history-list", Widget), size)
                _widget_fits_terminal(app.screen.query_one("#run-history-footer", Widget), size)

                app.push_screen(RunHistoryDetailScreen(run_id=run_id))
                await pilot.pause()
                _widget_fits_terminal(app.screen.query_one("#run-detail-content", Widget), size)
                _widget_fits_terminal(app.screen.query_one("#run-detail-footer", Widget), size)

    asyncio.run(scenario())


def test_game_screen_guess_buttons_render_across_terminal_sizes() -> None:
    async def scenario() -> None:
        for size in TERMINAL_SIZES:
            app = HoopHigherApp(database_url="sqlite://")

            async with app.run_test(size=(size.width, size.height)) as pilot:
                await pilot.press("enter")
                await pilot.press("1")
                await pilot.pause()

                higher = app.screen.query_one("#guess-higher", Button)
                lower = app.screen.query_one("#guess-lower", Button)

                _widget_fits_terminal(higher, size)
                _widget_fits_terminal(lower, size)
                assert higher.disabled is False
                assert lower.disabled is False

                await pilot.press("right")
                await pilot.pause()
                assert getattr(app.screen.focused, "id", None) == "guess-lower"

    asyncio.run(scenario())


def test_game_screen_guess_buttons_fit_tiny_terminal_target() -> None:
    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test(size=(TARGET_TINY_SIZE.width, TARGET_TINY_SIZE.height)) as pilot:
            await pilot.press("enter")
            await pilot.press("1")
            await pilot.pause()

            higher = app.screen.query_one("#guess-higher", Button)
            lower = app.screen.query_one("#guess-lower", Button)

            _widget_fits_terminal(higher, TARGET_TINY_SIZE)
            _widget_fits_terminal(lower, TARGET_TINY_SIZE)

    asyncio.run(scenario())


def test_game_screen_enables_scroll_before_cards_clip_on_mid_height_terminal() -> None:
    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test(size=(140, 26)) as pilot:
            await pilot.press("enter")
            await pilot.press("1")
            await pilot.pause()

            game_scroll = app.screen.query_one("#game-scroll", Widget)

            assert game_scroll.max_scroll_y > 0

    asyncio.run(scenario())


def test_game_reveal_keeps_tiny_layout_scrollable_without_visible_scrollbar() -> None:
    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test(size=(TARGET_TINY_SIZE.width, TARGET_TINY_SIZE.height)) as pilot:
            await pilot.press("enter")
            await pilot.press("1")
            await pilot.pause()

            question = app.gameplay_service.snapshot().current_question
            assert question is not None
            guess = "h" if question.correct_guess.value == "higher" else "l"
            await pilot.press(guess)
            await pilot.pause(0.05)

            game_scroll = app.screen.query_one("#game-scroll", Widget)
            assert game_scroll.max_scroll_y > 0
            assert game_scroll.scrollbar_size_vertical == 0

    asyncio.run(scenario())


def test_game_over_modal_return_action_renders_on_small_terminal() -> None:
    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test(size=(60, 20)) as pilot:
            await pilot.press("enter")
            await pilot.press("2")
            await pilot.pause()

            question = app.gameplay_service.snapshot().current_question
            assert question is not None
            wrong_guess = "l" if question.player_b.points > question.player_a.points else "h"

            await pilot.press(wrong_guess)
            await pilot.pause(1.5)

            button = app.screen.query_one("#gameover-home", Button)
            _widget_fits_terminal(button, Size(60, 20))

    asyncio.run(scenario())
