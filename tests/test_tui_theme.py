from __future__ import annotations

import asyncio

import pytest

from hoophigher.app import HoopHigherApp
from hoophigher.tui.theme import (
    DARK_THEME_NAME,
    LIGHT_THEME_NAME,
    load_saved_theme_name,
    save_theme_name,
)


@pytest.fixture(autouse=True)
def _use_mock_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOOPHIGHER_STATS_PROVIDER", "mock")


def test_app_registers_and_defaults_to_hoop_higher_dark() -> None:
    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test() as pilot:
            await pilot.pause()
            assert DARK_THEME_NAME in app.available_themes
            assert LIGHT_THEME_NAME in app.available_themes
            assert app.theme == DARK_THEME_NAME

    asyncio.run(scenario())


def test_light_theme_can_be_activated() -> None:
    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test() as pilot:
            app.theme = LIGHT_THEME_NAME
            await pilot.pause()
            assert app.current_theme.name == LIGHT_THEME_NAME

    asyncio.run(scenario())


def test_app_stays_usable_under_ansi_fallback_theme() -> None:
    """The 16-color validation harness: custom tokens must still resolve and
    focus must survive without RGB color."""

    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test() as pilot:
            app.theme = "ansi-dark"
            await pilot.pause()
            assert getattr(app.screen.focused, "id", None) == "start-game"

            await pilot.press("enter")
            await pilot.press("1")
            await pilot.pause()
            assert type(app.screen).__name__ == "GameScreen"

    asyncio.run(scenario())


def test_t_binding_toggles_theme_from_any_screen() -> None:
    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.theme == DARK_THEME_NAME

            await pilot.press("t")
            await pilot.pause()
            assert app.theme == LIGHT_THEME_NAME

            await pilot.press("t")
            await pilot.pause()
            assert app.theme == DARK_THEME_NAME

    asyncio.run(scenario())


def test_theme_toggle_works_during_gameplay() -> None:
    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test() as pilot:
            await pilot.press("enter")
            await pilot.press("1")
            await pilot.pause()
            assert type(app.screen).__name__ == "GameScreen"

            await pilot.press("t")
            await pilot.pause()
            assert app.theme == LIGHT_THEME_NAME

    asyncio.run(scenario())


def test_theme_name_round_trips_through_settings_file(tmp_path) -> None:
    settings_path = tmp_path / "theme"
    assert load_saved_theme_name(settings_path) is None

    save_theme_name(LIGHT_THEME_NAME, settings_path)
    assert load_saved_theme_name(settings_path) == LIGHT_THEME_NAME

    save_theme_name(DARK_THEME_NAME, settings_path)
    assert load_saved_theme_name(settings_path) == DARK_THEME_NAME
