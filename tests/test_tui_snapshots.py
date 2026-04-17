from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date, datetime, timezone

from textual.pilot import Pilot
from sqlmodel import Session

import hoophigher.tui.screens.game as game_screen_module
from hoophigher.app import HoopHigherApp
from hoophigher.data import RunRecord, create_sqlite_engine, init_db
from hoophigher.domain.enums import GameMode


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
