from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date, datetime, timezone

import pytest
from textual.pilot import Pilot
from sqlmodel import Session

import hoophigher.tui.screens.game as game_screen_module
from hoophigher.app import HoopHigherApp
from hoophigher.data import (
    QuestionRecord,
    RoundRecord,
    RunRecord,
    create_sqlite_engine,
    init_db,
)
from hoophigher.domain.enums import GameMode


@pytest.fixture(autouse=True)
def _use_mock_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOOPHIGHER_STATS_PROVIDER", "mock")
    # Keep SVG snapshots independent from each developer's terminal theme.
    monkeypatch.setenv("NO_COLOR", "1")


async def _open_mode_select(pilot: Pilot) -> None:
    await pilot.press("enter")
    await pilot.pause()


async def _open_gameplay(pilot: Pilot, mode_key: str = "1") -> None:
    await pilot.press("enter")
    await pilot.press(mode_key)
    await pilot.pause()


async def _open_round_summary(pilot: Pilot) -> None:
    app = pilot.app
    await _open_gameplay(pilot, "1")

    snapshot = app.gameplay_service.snapshot()
    for question_index in range(snapshot.total_questions):
        question = app.gameplay_service.snapshot().current_question
        assert question is not None
        guess_key = "h" if question.answer.value == "higher" else "l"
        await pilot.press(guess_key)
        is_last_question = question_index == snapshot.total_questions - 1
        if is_last_question:
            for _ in range(20):
                if type(app.screen).__name__ == "RoundSummaryScreen":
                    break
                await pilot.pause(0.1)
            assert type(app.screen).__name__ == "RoundSummaryScreen"
        else:
            await pilot.pause(game_screen_module._FEEDBACK_DURATION_SECONDS + 0.1)


async def _open_leaderboard(pilot: Pilot) -> None:
    await pilot.press("l")
    await pilot.pause()


async def _open_stats(pilot: Pilot) -> None:
    await pilot.press("s")
    await pilot.pause()


def _seed_leaderboard_runs(database_url: str) -> None:
    engine = create_sqlite_engine(database_url)
    init_db(engine)
    with Session(engine) as session:
        session.add_all(
            [
                RunRecord(
                    mode=GameMode.HISTORICAL,
                    source_date=None,
                    final_score=640,
                    correct_answers=6,
                    wrong_answers=1,
                    best_streak=5,
                    end_reason="user_exit",
                    created_at=datetime(2025, 1, 3, 9, 15, tzinfo=timezone.utc),
                ),
                RunRecord(
                    mode=GameMode.ENDLESS,
                    source_date=date(2025, 1, 12),
                    final_score=520,
                    correct_answers=5,
                    wrong_answers=0,
                    best_streak=5,
                    end_reason="user_exit",
                    created_at=datetime(2025, 1, 3, 9, 30, tzinfo=timezone.utc),
                ),
                RunRecord(
                    mode=GameMode.ARCADE,
                    source_date=date(2025, 1, 13),
                    final_score=520,
                    correct_answers=4,
                    wrong_answers=1,
                    best_streak=4,
                    end_reason="wrong_answer",
                    created_at=datetime(2025, 1, 3, 9, 45, tzinfo=timezone.utc),
                ),
            ]
        )
        session.commit()


def _seed_stats_runs(database_url: str) -> None:
    engine = create_sqlite_engine(database_url)
    init_db(engine)
    with Session(engine) as session:
        first_run = RunRecord(
            mode=GameMode.ENDLESS,
            source_date=date(2025, 1, 12),
            final_score=340,
            correct_answers=3,
            wrong_answers=1,
            best_streak=3,
            end_reason="user_exit",
            created_at=datetime(2025, 1, 3, 9, 0, tzinfo=timezone.utc),
        )
        second_run = RunRecord(
            mode=GameMode.ARCADE,
            source_date=date(2025, 1, 13),
            final_score=420,
            correct_answers=2,
            wrong_answers=1,
            best_streak=2,
            end_reason="wrong_answer",
            created_at=datetime(2025, 1, 3, 10, 0, tzinfo=timezone.utc),
        )
        session.add_all([first_run, second_run])
        session.flush()

        first_round = RoundRecord(
            run_id=first_run.id or 1,
            round_index=0,
            game_id="game-1",
            game_date=date(2025, 1, 12),
            total_questions=4,
            correct_answers=3,
            wrong_answers=1,
            score_delta=340,
        )
        second_round = RoundRecord(
            run_id=second_run.id or 2,
            round_index=0,
            game_id="game-2",
            game_date=date(2025, 1, 13),
            total_questions=3,
            correct_answers=2,
            wrong_answers=1,
            score_delta=420,
        )
        session.add_all([first_round, second_round])
        session.flush()

        session.add_all(
            [
                QuestionRecord(
                    run_id=first_run.id or 1,
                    round_id=first_round.id or 1,
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
                    run_id=first_run.id or 1,
                    round_id=first_round.id or 1,
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
                    is_correct=False,
                    score_delta=-60,
                    revealed_points=12,
                    response_time_ms=1100,
                ),
                QuestionRecord(
                    run_id=second_run.id or 2,
                    round_id=second_round.id or 2,
                    question_index=0,
                    player_a_id="a3",
                    player_a_name="Player A3",
                    player_a_team_id="home",
                    player_a_team_abbreviation="HOM",
                    player_a_points=16,
                    player_a_minutes=29,
                    player_b_id="b3",
                    player_b_name="Player B3",
                    player_b_team_id="away",
                    player_b_team_abbreviation="AWY",
                    player_b_points=22,
                    player_b_minutes=33,
                    difficulty="medium",
                    guess="higher",
                    is_correct=True,
                    score_delta=150,
                    revealed_points=22,
                    response_time_ms=800,
                ),
            ]
        )
        session.commit()


def _compare_app(
    snap_compare,
    *,
    terminal_size: tuple[int, int],
    database_url: str = "sqlite://",
    run_before: Callable[[Pilot], Awaitable[None] | None] | None = None,
) -> bool:
    app = HoopHigherApp(database_url=database_url)
    return snap_compare(
        app,
        terminal_size=terminal_size,
        run_before=run_before,
    )


def test_home_snapshot(snap_compare) -> None:
    assert _compare_app(snap_compare, terminal_size=(110, 32))


def test_mode_select_snapshot(snap_compare) -> None:
    assert _compare_app(
        snap_compare,
        terminal_size=(110, 32),
        run_before=_open_mode_select,
    )


def test_gameplay_wide_snapshot(snap_compare) -> None:
    assert _compare_app(
        snap_compare,
        terminal_size=(140, 40),
        run_before=_open_gameplay,
    )


def test_gameplay_compact_snapshot(snap_compare) -> None:
    assert _compare_app(
        snap_compare,
        terminal_size=(90, 26),
        run_before=_open_gameplay,
    )


def test_gameplay_narrow_snapshot(snap_compare) -> None:
    assert _compare_app(
        snap_compare,
        terminal_size=(72, 24),
        run_before=_open_gameplay,
    )


def test_gameplay_tiny_snapshot(snap_compare) -> None:
    assert _compare_app(
        snap_compare,
        terminal_size=(60, 20),
        run_before=_open_gameplay,
    )


def test_round_summary_snapshot(snap_compare) -> None:
    assert _compare_app(
        snap_compare,
        terminal_size=(110, 32),
        run_before=_open_round_summary,
    )


def test_leaderboard_snapshot(snap_compare, tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'leaderboard-snapshot.db'}"
    _seed_leaderboard_runs(database_url)

    assert _compare_app(
        snap_compare,
        terminal_size=(110, 32),
        database_url=database_url,
        run_before=_open_leaderboard,
    )


def test_stats_snapshot(snap_compare, tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'stats-snapshot.db'}"
    _seed_stats_runs(database_url)

    assert _compare_app(
        snap_compare,
        terminal_size=(110, 32),
        database_url=database_url,
        run_before=_open_stats,
    )


def test_stats_empty_snapshot(snap_compare) -> None:
    assert _compare_app(
        snap_compare,
        terminal_size=(110, 32),
        run_before=_open_stats,
    )
