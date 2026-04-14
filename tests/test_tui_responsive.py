from __future__ import annotations

import asyncio

import pytest
from textual.geometry import Size
from textual.widget import Widget
from textual.widgets import Button

from hoophigher.app import HoopHigherApp

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


def _widget_fits_terminal(widget: Widget, size: Size) -> None:
    region = widget.region
    assert region.width > 0
    assert region.height > 0
    assert region.right <= size.width
    assert region.bottom <= size.height


def test_home_screen_primary_actions_render_across_terminal_sizes() -> None:
    async def scenario() -> None:
        for size in TERMINAL_SIZES:
            app = HoopHigherApp(database_url="sqlite://")

            async with app.run_test(size=(size.width, size.height)) as pilot:
                await pilot.pause()

                start = app.screen.query_one("#start-game", Button)
                quit_button = app.screen.query_one("#quit-game", Button)

                _widget_fits_terminal(start, size)
                _widget_fits_terminal(quit_button, size)
                assert getattr(app.screen.focused, "id", None) == "start-game"

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


@pytest.mark.xfail(
    reason="Current gameplay layout overflows on tiny terminals; fixed in responsive refactor commits.",
    strict=True,
)
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
