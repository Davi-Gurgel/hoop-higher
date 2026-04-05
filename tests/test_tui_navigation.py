from __future__ import annotations

import asyncio

from textual.widgets import Label

from hoophigher.domain.enums import RunEndReason
from hoophigher.app import HoopHigherApp


def test_home_screen_supports_arrow_navigation() -> None:
    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

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
        app = HoopHigherApp(database_url="sqlite://")

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


def test_game_screen_surfaces_left_right_controls() -> None:
    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test() as pilot:
            await pilot.press("enter")
            await pilot.press("1")
            await pilot.pause()

            controls_hint = app.screen.query_one("#controls-hint", Label)
            assert controls_hint.visual.plain == "Use H/L or ←/→ + Enter"

    asyncio.run(scenario())


def test_game_screen_shows_active_game_tabs_and_minutes_for_both_players() -> None:
    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test() as pilot:
            await pilot.press("enter")
            await pilot.press("1")
            await pilot.pause()

            snapshot = app.gameplay_service.snapshot()
            active_game = app.screen.query_one("#active-game-title", Label)
            first_tab = app.screen.query_one("#game-tab-0", Label)
            player_a_minutes = app.screen.query_one("#pa-minutes", Label)
            player_b_minutes = app.screen.query_one("#pb-minutes", Label)

            assert "@" in active_game.visual.plain
            assert snapshot.current_game.game_id in {
                game.game_id for game in snapshot.games_today
            }
            current_game_index = next(
                i
                for i, g in enumerate(snapshot.games_today)
                if g.game_id == snapshot.current_game.game_id
            )
            assert app.screen.query_one(f"#game-tab-{current_game_index}", Label).has_class("browser-tab-active")
            assert (
                first_tab.visual.plain
                == f"{snapshot.games_today[0].away_team.abbreviation} {snapshot.games_today[0].away_team.score} | "
                f"{snapshot.games_today[0].home_team.abbreviation} {snapshot.games_today[0].home_team.score}"
            )
            assert player_a_minutes.visual.plain.endswith("MIN")
            assert player_b_minutes.visual.plain.endswith("MIN")

    asyncio.run(scenario())


def test_game_screen_left_right_arrows_focus_buttons_before_enter() -> None:
    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test() as pilot:
            await pilot.press("enter")
            await pilot.press("1")
            await pilot.pause()

            await pilot.press("right")
            await pilot.pause()
            assert getattr(app.screen.focused, "id", None) == "guess-lower"

            await pilot.press("left")
            await pilot.pause()
            assert getattr(app.screen.focused, "id", None) == "guess-higher"

    asyncio.run(scenario())


def test_game_screen_enter_confirms_focused_guess() -> None:
    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test() as pilot:
            await pilot.press("enter")
            await pilot.press("1")
            await pilot.pause()

            starting_index = app.gameplay_service.snapshot().question_index

            await pilot.press("left")
            await pilot.press("enter")
            await pilot.pause(1.4)

            assert app.gameplay_service.snapshot().question_index == starting_index + 1

    asyncio.run(scenario())


def test_game_screen_active_tab_moves_after_round_end() -> None:
    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test() as pilot:
            await pilot.press("enter")
            await pilot.press("1")
            await pilot.pause()

            initial_snapshot = app.gameplay_service.snapshot()
            initial_active_index = next(
                index
                for index, game in enumerate(initial_snapshot.games_today)
                if game.game_id == initial_snapshot.current_game.game_id
            )

            for _ in range(initial_snapshot.total_questions):
                question = app.gameplay_service.snapshot().current_question
                assert question is not None
                guess_key = "h" if question.answer.value == "higher" else "l"
                await pilot.press(guess_key)
                await pilot.pause(1.4)

            await pilot.press("enter")
            await pilot.pause()

            next_snapshot = app.gameplay_service.snapshot()
            next_active_index = next(
                index
                for index, game in enumerate(next_snapshot.games_today)
                if game.game_id == next_snapshot.current_game.game_id
            )

            assert next_active_index != initial_active_index
            active_tab = app.screen.query_one(f"#game-tab-{next_active_index}", Label)
            assert active_tab.has_class("browser-tab-active")

    asyncio.run(scenario())


def test_game_screen_q_exits_app_and_marks_user_exit() -> None:
    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")
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
