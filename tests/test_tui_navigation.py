from __future__ import annotations

import asyncio
from datetime import date

import pytest
from sqlmodel import Session
from textual.widgets import Button, Label

import hoophigher.tui.screens.game as game_screen_module
from hoophigher.data import RunRepository, create_sqlite_engine
from hoophigher.domain.enums import RunEndReason
from hoophigher.domain.models import GameBoxScore, PlayerLine, TeamGameInfo
from hoophigher.app import HoopHigherApp


@pytest.fixture(autouse=True)
def _use_mock_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOOPHIGHER_STATS_PROVIDER", "mock")


def _correct_guess_key(app: HoopHigherApp) -> str:
    question = app.gameplay_service.snapshot().current_question
    assert question is not None
    return "h" if question.answer.value == "higher" else "l"


def _wrong_guess_key(app: HoopHigherApp) -> str:
    question = app.gameplay_service.snapshot().current_question
    assert question is not None
    return "l" if question.answer.value == "higher" else "h"


def _label_texts(app: HoopHigherApp) -> list[str]:
    return [label.visual.plain for label in app.screen.query(Label)]


def _enter_binding_description(app: HoopHigherApp) -> str | None:
    binding = app.active_bindings.get("enter")
    return None if binding is None else binding.binding.description


def test_home_screen_supports_arrow_navigation() -> None:
    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test() as pilot:
            assert getattr(app.screen.focused, "id", None) == "start-game"

            await pilot.press("down")
            await pilot.pause()
            assert getattr(app.screen.focused, "id", None) == "open-leaderboard"

            await pilot.press("down")
            await pilot.pause()
            assert getattr(app.screen.focused, "id", None) == "open-stats"

            await pilot.press("down")
            await pilot.pause()
            assert getattr(app.screen.focused, "id", None) == "quit-game"

            await pilot.press("up")
            await pilot.pause()
            assert getattr(app.screen.focused, "id", None) == "open-stats"

            await pilot.press("up")
            await pilot.pause()
            assert getattr(app.screen.focused, "id", None) == "open-leaderboard"

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


def test_mode_select_shows_loading_state_while_starting_game(monkeypatch) -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_start_game(self, mode) -> bool:
        started.set()
        await release.wait()
        return False

    monkeypatch.setattr(HoopHigherApp, "start_game", fake_start_game)

    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test() as pilot:
            await pilot.press("enter")
            await pilot.press("1")
            await asyncio.wait_for(started.wait(), timeout=1)
            await pilot.pause()

            assert app.screen.query_one("#mode-loading-status", Label).has_class("-visible")
            assert app.screen.query_one("#mode-endless", Button).disabled is True
            assert app.screen.query_one("#mode-arcade", Button).disabled is True
            assert app.screen.query_one("#mode-historical", Button).disabled is True

            release.set()
            await pilot.pause()

            assert app.screen.query_one("#mode-loading-status", Label).has_class("-visible") is False
            assert app.screen.query_one("#mode-endless", Button).disabled is False

    asyncio.run(scenario())


def test_home_screen_can_open_stats_and_return_home() -> None:
    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test() as pilot:
            assert type(app.screen).__name__ == "HomeScreen"

            await pilot.press("s")
            await pilot.pause()
            assert type(app.screen).__name__ == "StatsScreen"

            await pilot.press("escape")
            await pilot.pause()
            assert type(app.screen).__name__ == "HomeScreen"

    asyncio.run(scenario())


def test_home_screen_can_open_stats_from_focused_button() -> None:
    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test() as pilot:
            await pilot.press("down")
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()
            assert getattr(app.screen.focused, "id", None) == "open-stats"

            await pilot.press("enter")
            await pilot.pause()
            assert type(app.screen).__name__ == "StatsScreen"

    asyncio.run(scenario())


def test_stats_screen_refreshes_after_a_run_is_played(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'hoophigher.db'}"
    monkeypatch.setattr(game_screen_module, "_FEEDBACK_DURATION_SECONDS", 0.01)

    async def scenario() -> None:
        app = HoopHigherApp(database_url=database_url)

        async with app.run_test() as pilot:
            await pilot.press("down")
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()
            assert getattr(app.screen.focused, "id", None) == "open-stats"

            await pilot.press("enter")
            await pilot.pause()
            assert type(app.screen).__name__ == "StatsScreen"
            assert "Runs played: 0" in _label_texts(app)
            assert "Questions answered: 0" in _label_texts(app)

            await pilot.press("escape")
            await pilot.pause()
            assert type(app.screen).__name__ == "HomeScreen"

            await pilot.press("up")
            await pilot.pause()
            await pilot.press("up")
            await pilot.pause()
            assert getattr(app.screen.focused, "id", None) == "start-game"

            await pilot.press("enter")
            await pilot.press("1")
            await pilot.pause()

            await pilot.press(_correct_guess_key(app))
            await pilot.pause(0.05)
            await pilot.press("escape")
            await pilot.pause()
            assert type(app.screen).__name__ == "HomeScreen"

            await pilot.press("s")
            await pilot.pause()
            assert type(app.screen).__name__ == "StatsScreen"
            assert "Runs played: 1" in _label_texts(app)
            assert "Questions answered: 1" in _label_texts(app)

    asyncio.run(scenario())


def test_home_screen_q_exits_app() -> None:
    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")
        exit_called = False

        def fake_exit(*args, **kwargs) -> None:
            nonlocal exit_called
            exit_called = True

        app.exit = fake_exit  # type: ignore[method-assign]

        async with app.run_test() as pilot:
            await pilot.press("q")
            await pilot.pause()

            assert exit_called is True

    asyncio.run(scenario())


def test_game_screen_surfaces_active_game_context() -> None:
    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test() as pilot:
            await pilot.press("enter")
            await pilot.press("1")
            await pilot.pause()

            snapshot = app.gameplay_service.snapshot()
            active_game = app.screen.query_one("#active-game-title", Label)
            player_a_name = app.screen.query_one("#pa-name", Label)
            player_b_name = app.screen.query_one("#pb-name", Label)

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
            assert player_a_name.visual.plain != ""
            assert player_b_name.visual.plain != ""

    asyncio.run(scenario())


def test_game_screen_renders_provider_strings_as_plain_text(monkeypatch: pytest.MonkeyPatch) -> None:
    game = GameBoxScore(
        game_id="markup-game-[red]1[/red]",
        game_date=date(2025, 1, 12),
        home_team=TeamGameInfo(
            team_id="home",
            name="Home [red]Team[/red]",
            abbreviation="HOM [red]X[/red]",
            score=101,
        ),
        away_team=TeamGameInfo(
            team_id="away",
            name="Away [blue]Team[/blue]",
            abbreviation="AWY [blue]Y[/blue]",
            score=99,
        ),
        player_lines=tuple(
            PlayerLine(
                player_id=f"p{index}",
                player_name=f"Player {index} [red]Name[/red]",
                team_id="home" if index % 2 == 0 else "away",
                team_abbreviation="HOM [red]X[/red]" if index % 2 == 0 else "AWY [blue]Y[/blue]",
                points=10 + index,
                minutes=30 - index,
            )
            for index in range(1, 8)
        ),
    )

    class MarkupProvider:
        async def get_games_by_date(self, _game_date: date) -> list[GameBoxScore]:
            return [game]

        async def get_game_boxscore(
            self,
            _game_id: str,
            *,
            game_date_fallback: date | None = None,
        ) -> GameBoxScore:
            return game

    monkeypatch.setattr("hoophigher.app.MockProvider", MarkupProvider)

    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test() as pilot:
            await pilot.press("enter")
            await pilot.press("1")
            await pilot.pause()

            label_texts = _label_texts(app)

            assert any("[RED]NAME[/RED]" in text for text in label_texts)
            assert any("[red]X[/red]" in text for text in label_texts)

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


def test_game_screen_footer_keeps_confirm_binding_visible(monkeypatch) -> None:
    monkeypatch.setattr(game_screen_module, "_FEEDBACK_DURATION_SECONDS", 0.01)

    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test() as pilot:
            await pilot.press("enter")
            await pilot.press("1")
            await pilot.pause()

            assert getattr(app.screen.focused, "id", None) == "guess-higher"
            assert _enter_binding_description(app) == "Confirm"

            await pilot.press(_correct_guess_key(app))
            await pilot.pause(0.05)

            assert getattr(app.screen.focused, "id", None) == "guess-higher"
            assert _enter_binding_description(app) == "Confirm"

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


def test_game_screen_escape_returns_home_and_persists_user_exit(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'hoophigher.db'}"
    run_id: int | None = None
    monkeypatch.setattr(game_screen_module, "_FEEDBACK_DURATION_SECONDS", 0.01)

    async def scenario() -> None:
        nonlocal run_id
        app = HoopHigherApp(database_url=database_url)

        async with app.run_test() as pilot:
            await pilot.press("enter")
            await pilot.press("1")
            await pilot.pause()

            run_id = app.gameplay_service.snapshot().run_id

            await pilot.press("escape")
            await pilot.pause()

            assert type(app.screen).__name__ == "HomeScreen"
            assert app.gameplay_service.snapshot().end_reason is RunEndReason.USER_EXIT

    asyncio.run(scenario())

    assert run_id is not None
    engine = create_sqlite_engine(database_url)
    with Session(engine) as session:
        run_record = RunRepository(session).get(run_id)

    assert run_record is not None
    assert run_record.end_reason == RunEndReason.USER_EXIT.value


def test_round_summary_reports_completed_round_and_resets_for_next_round(monkeypatch) -> None:
    monkeypatch.setattr(game_screen_module, "_FEEDBACK_DURATION_SECONDS", 0.01)

    async def scenario() -> None:
        app = HoopHigherApp(database_url="sqlite://")

        async with app.run_test() as pilot:
            await pilot.press("enter")
            await pilot.press("1")
            await pilot.pause()

            for _ in range(app.gameplay_service.snapshot().total_questions):
                await pilot.press(_correct_guess_key(app))
                await pilot.pause(0.05)

            assert type(app.screen).__name__ == "RoundSummaryScreen"
            summary_labels = [label.visual.plain for label in app.screen.query(Label)]
            assert "ROUND 1 COMPLETE" in summary_labels
            assert "✓ 5   ✕ 0   (5 questions)" in summary_labels
            assert "Score Delta: +500" in summary_labels

            await pilot.press("enter")
            await pilot.pause()

            assert type(app.screen).__name__ == "GameScreen"
            assert app.gameplay_service.snapshot().round_index == 1
            assert app.gameplay_service.snapshot().question_index == 0

            await pilot.press(_wrong_guess_key(app))
            await pilot.pause(0.05)

            for _ in range(app.gameplay_service.snapshot().total_questions - 1):
                await pilot.press(_correct_guess_key(app))
                await pilot.pause(0.05)

            assert type(app.screen).__name__ == "RoundSummaryScreen"
            summary_labels = [label.visual.plain for label in app.screen.query(Label)]
            assert "ROUND 2 COMPLETE" in summary_labels
            assert "✓ 4   ✕ 1   (5 questions)" in summary_labels
            assert "Score Delta: +340" in summary_labels

    asyncio.run(scenario())
