from __future__ import annotations

import asyncio

from textual.widgets import Label

from hoophigher.domain.enums import RunEndReason
from hoophigher.app import HoopHigherApp


def test_home_screen_supports_arrow_navigation() -> None:
    async def scenario() -> None:
        app = HoopHigherApp()

        async with app.run_test() as pilot:
            assert getattr(app.screen.focused, "id", None) == "start-game"

            await pilot.press("down")
            await pilot.pause()
            assert getattr(app.screen.focused, "id", None) == "quit-game"

            await pilot.press("up")
            await pilot.pause()
            assert getattr(app.screen.focused, "id", None) == "start-game"

    asyncio.run(scenario())


def test_mode_select_supports_arrow_navigation() -> None:
    async def scenario() -> None:
        app = HoopHigherApp()

        async with app.run_test() as pilot:
            await pilot.press("enter")
            await pilot.pause()
            assert getattr(app.screen.focused, "id", None) == "mode-endless"

            await pilot.press("down")
            await pilot.pause()
            assert getattr(app.screen.focused, "id", None) == "mode-arcade"

            await pilot.press("down")
            await pilot.pause()
            assert getattr(app.screen.focused, "id", None) == "mode-historical"

            await pilot.press("up")
            await pilot.pause()
            assert getattr(app.screen.focused, "id", None) == "mode-arcade"

    asyncio.run(scenario())


def test_game_screen_surfaces_arrow_and_enter_controls() -> None:
    async def scenario() -> None:
        app = HoopHigherApp()

        async with app.run_test() as pilot:
            await pilot.press("enter")
            await pilot.press("1")
            await pilot.pause()

            controls_hint = app.screen.query_one("#controls-hint", Label)
            assert controls_hint.visual.plain == "Use H/L or ↑/↓ + Enter"

    asyncio.run(scenario())


def test_game_screen_shows_active_game_tabs_and_minutes_for_both_players() -> None:
    async def scenario() -> None:
        app = HoopHigherApp()

        async with app.run_test() as pilot:
            await pilot.press("enter")
            await pilot.press("1")
            await pilot.pause()

            active_game = app.screen.query_one("#active-game-title", Label)
            first_tab = app.screen.query_one("#game-tab-0", Label)
            player_a_minutes = app.screen.query_one("#pa-minutes", Label)
            player_b_minutes = app.screen.query_one("#pb-minutes", Label)

            assert "@" in active_game.visual.plain
            assert "|" in first_tab.visual.plain
            assert player_a_minutes.visual.plain.endswith("MIN")
            assert player_b_minutes.visual.plain.endswith("MIN")

    asyncio.run(scenario())


def test_game_screen_q_exits_app_and_marks_user_exit() -> None:
    async def scenario() -> None:
        app = HoopHigherApp()
        exit_called = False

        def fake_exit(*args, **kwargs) -> None:
            nonlocal exit_called
            exit_called = True

        app.exit = fake_exit  # type: ignore[method-assign]

        async with app.run_test() as pilot:
            await pilot.press("enter")
            await pilot.press("1")
            await pilot.pause()

            await pilot.press("q")
            await pilot.pause()

            assert exit_called is True
            assert app.gameplay_service.snapshot().end_reason is RunEndReason.USER_EXIT

    asyncio.run(scenario())
