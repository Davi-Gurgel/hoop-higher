import asyncio
import time
from datetime import date
from random import Random

import pytest

from hoophigher.data.stats_sources import MockStatsSource
from hoophigher.domain.enums import GameMode
from hoophigher.domain.models import NBAGame, PlayerLine, TeamGameInfo
from hoophigher.services import PlayableNBAGameResolver


class _FixedHistoricalProbeRandom(Random):
    def __init__(self, *, years: list[int], months: list[int], days: list[int]) -> None:
        super().__init__(1)
        self._years = iter(years)
        self._months = iter(months)
        self._days = iter(days)

    def randint(self, a: int, b: int) -> int:
        if a == b:
            return a
        if a > 12:
            return next(self._years)
        return next(self._days)

    def choice(self, seq):
        return next(self._months)


class _DateStatsSource:
    def __init__(self, games_by_date: dict[date, object]) -> None:
        self._games_by_date = games_by_date
        self.requested_dates: list[date] = []

    async def get_games_by_date(self, source_date: date) -> list[NBAGame]:
        self.requested_dates.append(source_date)
        value = self._games_by_date.get(source_date, ())
        if isinstance(value, Exception):
            raise value
        return list(value)

    async def get_nba_game(
        self,
        game_id: str,
        *,
        source_date_fallback: date | None = None,
    ) -> NBAGame:
        for games in self._games_by_date.values():
            if isinstance(games, Exception):
                continue
            for game in games:
                if game.game_id == game_id:
                    return game
        raise LookupError(f"Game not found: {game_id}")


def _make_game(*, game_id: str, source_date: date, minutes: int = 30) -> NBAGame:
    home_team = TeamGameInfo(team_id="home", name="Home", abbreviation="HME", score=110)
    away_team = TeamGameInfo(team_id="away", name="Away", abbreviation="AWY", score=104)
    return NBAGame(
        game_id=game_id,
        source_date=source_date,
        home_team=home_team,
        away_team=away_team,
        player_lines=tuple(
            PlayerLine(
                player_id=f"p{index}",
                player_name=f"Player {index}",
                team_id=away_team.team_id if index <= 3 else home_team.team_id,
                team_abbreviation=(
                    away_team.abbreviation if index <= 3 else home_team.abbreviation
                ),
                points=points,
                minutes=minutes,
            )
            for index, points in enumerate((31, 24, 19, 15, 9, 4), start=1)
        ),
    )


class _NoShuffleRandom(Random):
    def shuffle(self, x) -> None:
        return None

    def choice(self, seq):
        return seq[0]

    def sample(self, population, k):
        return list(population)[:k]


def _make_resolver(stats_source, **kwargs):
    values = {
        "historical_start_year": 2010,
        "historical_end_year": 2020,
        "historical_rounds": 5,
        "historical_max_date_probes": 10,
        "playable_game_fetch_concurrency": 8,
        "non_historical_startup_games": 5,
        "rng": Random(1),
    }
    values.update(kwargs)
    return PlayableNBAGameResolver(stats_source=stats_source, **values)


class _ShellNBAGameStatsSource:
    def __init__(self, *, game_count: int, source_date: date) -> None:
        self.max_in_flight = 0
        self.in_flight = 0
        self.requested_fallback_dates: list[date | None] = []
        self._games = tuple(
            NBAGame(
                game_id=f"shell-game-{index}",
                source_date=source_date,
                home_team=TeamGameInfo(
                    team_id=f"h-{index}", name="Home", abbreviation="HOM", score=110
                ),
                away_team=TeamGameInfo(
                    team_id=f"a-{index}", name="Away", abbreviation="AWY", score=103
                ),
                player_lines=(),
            )
            for index in range(1, game_count + 1)
        )

    async def get_games_by_date(self, source_date: date) -> list[NBAGame]:
        return list(self._games)

    async def get_nba_game(
        self,
        game_id: str,
        *,
        source_date_fallback: date | None = None,
    ) -> NBAGame:
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0.01)
            self.requested_fallback_dates.append(source_date_fallback)
            shell = next(game for game in self._games if game.game_id == game_id)
            return _make_game(game_id=shell.game_id, source_date=shell.source_date)
        finally:
            self.in_flight -= 1


class _ImmediateShellStatsSource(_ShellNBAGameStatsSource):
    def __init__(self, *, game_count: int, source_date: date) -> None:
        super().__init__(game_count=game_count, source_date=source_date)
        self.requested_ids: list[str] = []

    async def get_nba_game(
        self,
        game_id: str,
        *,
        source_date_fallback: date | None = None,
    ) -> NBAGame:
        self.requested_ids.append(game_id)
        shell = next(game for game in self._games if game.game_id == game_id)
        return _make_game(game_id=shell.game_id, source_date=shell.source_date)


class _SlowFirstShellStatsSource:
    def __init__(self, *, game_count: int, source_date: date) -> None:
        self.requested_ids: list[str] = []
        self.slow_fetch_cancelled = False
        self._games = tuple(
            NBAGame(
                game_id=f"shell-game-{index}",
                source_date=source_date,
                home_team=TeamGameInfo(
                    team_id=f"h-{index}", name="Home", abbreviation="HOM", score=110
                ),
                away_team=TeamGameInfo(
                    team_id=f"a-{index}", name="Away", abbreviation="AWY", score=103
                ),
                player_lines=(),
            )
            for index in range(1, game_count + 1)
        )

    async def get_games_by_date(self, source_date: date) -> list[NBAGame]:
        return list(self._games)

    async def get_nba_game(
        self,
        game_id: str,
        *,
        source_date_fallback: date | None = None,
    ) -> NBAGame:
        self.requested_ids.append(game_id)
        if game_id == "shell-game-1":
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                self.slow_fetch_cancelled = True
                raise
        else:
            await asyncio.sleep(0.01)
        shell = next(game for game in self._games if game.game_id == game_id)
        return _make_game(game_id=shell.game_id, source_date=shell.source_date)


class _MixedCachedShellStatsSource:
    def __init__(self, *, source_date: date) -> None:
        self.in_flight = 0
        self.max_in_flight = 0
        self.requested_ids: list[str] = []
        self._games = (
            _make_game(game_id="cached-1", source_date=source_date),
            _make_game(game_id="cached-2", source_date=source_date),
            _make_game(game_id="cached-3", source_date=source_date),
            NBAGame(
                game_id="shell-fail-1",
                source_date=source_date,
                home_team=TeamGameInfo(team_id="h-f1", name="Home", abbreviation="HOM", score=110),
                away_team=TeamGameInfo(team_id="a-f1", name="Away", abbreviation="AWY", score=103),
                player_lines=(),
            ),
            NBAGame(
                game_id="shell-fail-2",
                source_date=source_date,
                home_team=TeamGameInfo(team_id="h-f2", name="Home", abbreviation="HOM", score=110),
                away_team=TeamGameInfo(team_id="a-f2", name="Away", abbreviation="AWY", score=103),
                player_lines=(),
            ),
            NBAGame(
                game_id="shell-ok-1",
                source_date=source_date,
                home_team=TeamGameInfo(team_id="h-o1", name="Home", abbreviation="HOM", score=110),
                away_team=TeamGameInfo(team_id="a-o1", name="Away", abbreviation="AWY", score=103),
                player_lines=(),
            ),
            NBAGame(
                game_id="shell-ok-2",
                source_date=source_date,
                home_team=TeamGameInfo(team_id="h-o2", name="Home", abbreviation="HOM", score=110),
                away_team=TeamGameInfo(team_id="a-o2", name="Away", abbreviation="AWY", score=103),
                player_lines=(),
            ),
        )

    async def get_games_by_date(self, source_date: date) -> list[NBAGame]:
        return list(self._games)

    async def get_nba_game(
        self,
        game_id: str,
        *,
        source_date_fallback: date | None = None,
    ) -> NBAGame:
        self.requested_ids.append(game_id)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0.01)
            if game_id.startswith("shell-fail"):
                raise LookupError(f"Boxscore unavailable: {game_id}")
            shell = next(game for game in self._games if game.game_id == game_id)
            return _make_game(game_id=shell.game_id, source_date=shell.source_date)
        finally:
            self.in_flight -= 1


def test_resolver_selects_playable_games_without_run_persistence() -> None:
    resolver = _make_resolver(stats_source=MockStatsSource(), rng=Random(1))

    selected_date, games = asyncio.run(
        resolver.resolve(
            mode=GameMode.ENDLESS,
            source_date=date(2025, 1, 12),
            candidate_dates=None,
            total_questions=5,
        )
    )

    assert selected_date == date(2025, 1, 12)
    assert games
    assert {game.source_date for game in games} == {selected_date}


@pytest.mark.parametrize(
    ("has_unplayable_game", "message"),
    [
        (False, "No games found for source date: 2025-02-09"),
        (True, "No playable games found for source date: 2025-02-09"),
    ],
)
def test_source_date_resolution_preserves_specific_exhaustion_errors(
    has_unplayable_game: bool,
    message: str,
) -> None:
    source_date = date(2025, 2, 9)
    games = (
        (_make_game(game_id="unplayable", source_date=source_date, minutes=0),)
        if has_unplayable_game
        else ()
    )
    resolver = _make_resolver(stats_source=_DateStatsSource({source_date: games}))

    with pytest.raises(LookupError, match=message):
        asyncio.run(
            resolver.resolve(
                mode=GameMode.ENDLESS,
                source_date=source_date,
                candidate_dates=None,
                total_questions=5,
            )
        )


def test_source_date_resolution_preserves_stats_source_error() -> None:
    source_date = date(2025, 2, 9)
    source_error = RuntimeError("temporary Source Date failure")
    resolver = _make_resolver(
        stats_source=_DateStatsSource({source_date: source_error}),
    )

    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(
            resolver.resolve(
                mode=GameMode.ENDLESS,
                source_date=source_date,
                candidate_dates=None,
                total_questions=5,
            )
        )

    assert exc_info.value is source_error


def test_resolver_tries_candidate_dates_until_playable_games_are_found() -> None:
    first_date = date(2025, 2, 9)
    second_date = date(2025, 2, 10)
    stats_source = _DateStatsSource(
        {
            first_date: (_make_game(game_id="unplayable", source_date=first_date, minutes=0),),
            second_date: (_make_game(game_id="playable", source_date=second_date),),
        }
    )
    resolver = _make_resolver(stats_source=stats_source, rng=Random(1))

    selected_date, games = asyncio.run(
        resolver.resolve(
            mode=GameMode.ENDLESS,
            source_date=None,
            candidate_dates=[first_date, second_date],
            total_questions=5,
        )
    )

    assert selected_date == second_date
    assert [game.game_id for game in games] == ["playable"]


def test_resolver_reports_dates_with_no_playable_games() -> None:
    source_date = date(2025, 2, 9)
    resolver = _make_resolver(
        stats_source=_DateStatsSource(
            {source_date: (_make_game(game_id="unplayable", source_date=source_date, minutes=0),)}
        ),
        rng=Random(1),
    )

    with pytest.raises(LookupError, match="No playable games found"):
        asyncio.run(
            resolver.resolve(
                mode=GameMode.ENDLESS,
                source_date=None,
                candidate_dates=[source_date],
                total_questions=5,
            )
        )


def test_non_historical_resolution_requires_candidate_source_dates() -> None:
    resolver = _make_resolver(stats_source=MockStatsSource(), rng=Random(1))

    with pytest.raises(ValueError, match="candidate_dates is required"):
        asyncio.run(
            resolver.resolve(
                mode=GameMode.ENDLESS,
                source_date=None,
                candidate_dates=None,
                total_questions=5,
            )
        )


def test_resolution_tries_next_source_date_after_stats_source_error() -> None:
    first_date = date(2025, 2, 9)
    second_date = date(2025, 2, 10)
    resolver = _make_resolver(
        stats_source=_DateStatsSource(
            {
                first_date: RuntimeError("temporary failure"),
                second_date: (_make_game(game_id="playable", source_date=second_date),),
            }
        ),
        rng=Random(1),
    )

    selected_date, games = asyncio.run(
        resolver.resolve(
            mode=GameMode.ENDLESS,
            source_date=None,
            candidate_dates=[first_date, second_date],
            total_questions=5,
        )
    )

    assert selected_date == second_date
    assert [game.game_id for game in games] == ["playable"]


def test_shell_nba_games_are_fetched_concurrently_with_source_date_fallbacks() -> None:
    source_date = date(2025, 2, 10)
    stats_source = _ShellNBAGameStatsSource(game_count=4, source_date=source_date)
    resolver = _make_resolver(
        stats_source=stats_source,
        rng=_NoShuffleRandom(1),
    )

    selected_date, games = asyncio.run(
        resolver.resolve(
            mode=GameMode.ENDLESS,
            source_date=None,
            candidate_dates=[source_date],
            total_questions=5,
        )
    )

    assert selected_date == source_date
    assert len(games) == 4
    assert stats_source.max_in_flight > 1
    assert stats_source.requested_fallback_dates == [source_date] * 4


def test_non_historical_resolution_caps_boxscore_fetches_for_fast_startup() -> None:
    source_date = date(2025, 2, 10)
    stats_source = _ShellNBAGameStatsSource(game_count=8, source_date=source_date)
    resolver = _make_resolver(
        stats_source=stats_source,
        rng=_NoShuffleRandom(1),
        playable_game_fetch_concurrency=5,
        non_historical_startup_games=5,
    )

    _, games = asyncio.run(
        resolver.resolve(
            mode=GameMode.ENDLESS,
            source_date=None,
            candidate_dates=[source_date],
            total_questions=5,
        )
    )

    assert len(games) == 5
    assert len(stats_source.requested_fallback_dates) == 5


def test_fast_boxscore_fetches_stop_after_initial_concurrency_window() -> None:
    source_date = date(2025, 2, 10)
    stats_source = _ImmediateShellStatsSource(game_count=8, source_date=source_date)
    resolver = _make_resolver(
        stats_source=stats_source,
        rng=_NoShuffleRandom(1),
        playable_game_fetch_concurrency=5,
        non_historical_startup_games=5,
    )

    _, games = asyncio.run(
        resolver.resolve(
            mode=GameMode.ENDLESS,
            source_date=None,
            candidate_dates=[source_date],
            total_questions=5,
        )
    )

    assert [game.game_id for game in games] == [f"shell-game-{index}" for index in range(1, 6)]
    assert stats_source.requested_ids == [f"shell-game-{index}" for index in range(1, 6)]


def test_resolution_continues_after_partial_shell_fetch_batch_fails() -> None:
    source_date = date(2025, 2, 10)
    stats_source = _MixedCachedShellStatsSource(source_date=source_date)
    resolver = _make_resolver(
        stats_source=stats_source,
        rng=_NoShuffleRandom(1),
        playable_game_fetch_concurrency=5,
        non_historical_startup_games=5,
    )

    _, games = asyncio.run(
        resolver.resolve(
            mode=GameMode.ENDLESS,
            source_date=None,
            candidate_dates=[source_date],
            total_questions=5,
        )
    )

    assert [game.game_id for game in games] == [
        "cached-1",
        "cached-2",
        "cached-3",
        "shell-ok-1",
        "shell-ok-2",
    ]
    assert stats_source.requested_ids == [
        "shell-fail-1",
        "shell-fail-2",
        "shell-ok-1",
        "shell-ok-2",
    ]
    assert stats_source.max_in_flight == 4


def test_resolution_cancels_slow_shell_after_enough_nba_games_load() -> None:
    source_date = date(2025, 2, 10)
    stats_source = _SlowFirstShellStatsSource(game_count=4, source_date=source_date)
    resolver = _make_resolver(
        stats_source=stats_source,
        rng=_NoShuffleRandom(1),
        playable_game_fetch_concurrency=2,
        non_historical_startup_games=2,
    )

    started_at = time.monotonic()
    _, games = asyncio.run(
        resolver.resolve(
            mode=GameMode.ENDLESS,
            source_date=None,
            candidate_dates=[source_date],
            total_questions=5,
        )
    )

    assert time.monotonic() - started_at < 0.5
    assert len(games) == 2
    assert stats_source.slow_fetch_cancelled is True


def test_historical_resolution_uses_one_indexed_source_date() -> None:
    source_date = date(2018, 2, 14)
    stats_source = _DateStatsSource(
        {
            source_date: tuple(
                _make_game(game_id=f"historical-{index}", source_date=source_date)
                for index in range(1, 8)
            )
        }
    )
    requested_windows: list[tuple[int, int, int]] = []

    async def eligible_source_dates(start_year: int, end_year: int, min_games: int):
        requested_windows.append((start_year, end_year, min_games))
        return (source_date,)

    resolver = _make_resolver(
        stats_source=stats_source,
        rng=Random(4),
        historical_start_year=2010,
        historical_end_year=2020,
        historical_rounds=5,
        historical_eligible_source_dates_fetcher=eligible_source_dates,
    )

    selected_date, games = asyncio.run(
        resolver.resolve(
            mode=GameMode.HISTORICAL,
            source_date=None,
            candidate_dates=None,
            total_questions=5,
        )
    )

    assert requested_windows == [(2010, 2020, 5)]
    assert selected_date == source_date
    assert len(games) == 5
    assert {game.source_date for game in games} == {source_date}


def test_historical_index_tries_next_source_date_after_resolution_error() -> None:
    first_date = date(2018, 2, 13)
    second_date = date(2018, 2, 14)
    stats_source = _DateStatsSource(
        {
            first_date: LookupError("indexed Source Date no longer resolves"),
            second_date: tuple(
                _make_game(game_id=f"historical-{index}", source_date=second_date)
                for index in range(1, 6)
            ),
        }
    )

    async def eligible_source_dates(_start_year: int, _end_year: int, _min_games: int):
        return (first_date, second_date)

    resolver = _make_resolver(
        stats_source=stats_source,
        rng=_NoShuffleRandom(),
        historical_eligible_source_dates_fetcher=eligible_source_dates,
    )

    selected_date, games = asyncio.run(
        resolver.resolve(
            mode=GameMode.HISTORICAL,
            source_date=None,
            candidate_dates=None,
            total_questions=5,
        )
    )

    assert stats_source.requested_dates == [first_date, second_date]
    assert selected_date == second_date
    assert len(games) == 5


def test_historical_resolution_preserves_last_source_error_as_cause() -> None:
    failed_date = date(2018, 2, 13)
    unplayable_date = date(2018, 2, 14)
    source_error = RuntimeError("temporary Source Date failure")
    stats_source = _DateStatsSource(
        {
            failed_date: source_error,
            unplayable_date: (
                _make_game(
                    game_id="historical-unplayable",
                    source_date=unplayable_date,
                    minutes=0,
                ),
            ),
        }
    )

    async def eligible_source_dates(_start_year: int, _end_year: int, _min_games: int):
        return (failed_date, unplayable_date)

    resolver = _make_resolver(
        stats_source=stats_source,
        rng=_NoShuffleRandom(),
        historical_eligible_source_dates_fetcher=eligible_source_dates,
    )

    with pytest.raises(LookupError, match="after 2 probes") as exc_info:
        asyncio.run(
            resolver.resolve(
                mode=GameMode.HISTORICAL,
                source_date=None,
                candidate_dates=None,
                total_questions=5,
            )
        )

    assert exc_info.value.__cause__ is source_error


def test_historical_probes_prefer_high_signal_source_dates() -> None:
    rng = _FixedHistoricalProbeRandom(
        years=[2023, 2023, 2023, 2024, 2024, 2024, 2024],
        months=[10, 11, 12, 1, 2, 3, 4],
        days=[1, 1, 1, 1, 1, 1, 1],
    )
    stats_source = _DateStatsSource({})
    resolver = _make_resolver(
        stats_source=stats_source,
        rng=rng,
        historical_start_year=2023,
        historical_end_year=2024,
        historical_max_date_probes=7,
    )

    with pytest.raises(LookupError, match="historical date"):
        asyncio.run(
            resolver.resolve(
                mode=GameMode.HISTORICAL,
                source_date=None,
                candidate_dates=None,
                total_questions=5,
            )
        )

    assert stats_source.requested_dates == [
        date(2023, 10, 3),
        date(2023, 11, 1),
        date(2023, 12, 1),
        date(2024, 1, 2),
        date(2024, 2, 1),
        date(2024, 3, 1),
        date(2024, 4, 2),
    ]


def test_playability_probe_does_not_consume_resolver_rng_state() -> None:
    source_date = date(2025, 1, 12)
    rng = Random(11)
    resolver = _make_resolver(
        stats_source=_DateStatsSource(
            {source_date: (_make_game(game_id="probe-game", source_date=source_date),)}
        ),
        rng=rng,
    )
    state_before_resolution = rng.getstate()

    asyncio.run(
        resolver.resolve(
            mode=GameMode.ENDLESS,
            source_date=source_date,
            candidate_dates=None,
            total_questions=5,
        )
    )

    assert rng.getstate() == state_before_resolution
