from __future__ import annotations

import asyncio

import pytest

from hoophigher.app import HoopHigherApp


@pytest.fixture(autouse=True)
def _use_mock_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOOPHIGHER_STATS_PROVIDER", "mock")


def _wrong_guess_key(app: HoopHigherApp) -> str:
    question = app.gameplay_service.snapshot().current_question
    assert question is not None
    return "l" if question.player_b.points > question.player_a.points else "h"


def test_escape_during_finished_feedback_does_not_stack_game_over() -> None:
    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test() as pilot:
            await pilot.press("enter")
            await pilot.press("2")
            await pilot.pause()

            await pilot.press(_wrong_guess_key(app))
            await pilot.press("escape")
            await pilot.pause(1.5)

            stack_names = [type(screen).__name__ for screen in app.screen_stack]
            assert stack_names.count("GameOverScreen") == 1

            await pilot.press("enter")
            await pilot.pause()

            assert [type(screen).__name__ for screen in app.screen_stack] == [
                "Screen",
                "HomeScreen",
            ]

    asyncio.run(scenario())
