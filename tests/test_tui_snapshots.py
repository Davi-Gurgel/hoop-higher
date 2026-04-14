from __future__ import annotations

from collections.abc import Awaitable, Callable

from textual.pilot import Pilot

from hoophigher.app import HoopHigherApp


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
    for _ in range(snapshot.total_questions):
        question = app.gameplay_service.snapshot().current_question
        assert question is not None
        guess_key = "h" if question.answer.value == "higher" else "l"
        await pilot.press(guess_key)
        await pilot.pause(1.4)


def _compare_app(
    snap_compare,
    *,
    terminal_size: tuple[int, int],
    run_before: Callable[[Pilot], Awaitable[None] | None] | None = None,
) -> bool:
    app = HoopHigherApp(database_url="sqlite://")
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
