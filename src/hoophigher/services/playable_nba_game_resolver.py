from __future__ import annotations

import asyncio
import calendar
from collections.abc import Awaitable, Callable, Sequence
from datetime import date
from random import Random

from hoophigher.data.stats_sources import StatsSource
from hoophigher.domain.enums import GameMode
from hoophigher.domain.models import NBAGame
from hoophigher.domain.round_generator import generate_round

MIN_HISTORICAL_GAMES = 5

_NBA_HISTORICAL_PROBE_MONTHS = (
    10,
    11,
    11,
    11,
    12,
    12,
    12,
    1,
    1,
    1,
    2,
    2,
    2,
    3,
    3,
    3,
    4,
)
_NBA_HISTORICAL_PREFERRED_WEEKDAYS = (1, 2, 3, 4, 5)

HistoricalEligibleSourceDatesFetcher = Callable[[int, int, int], Awaitable[Sequence[date]]]


class PlayableNBAGameResolver:
    """Resolve one Source Date and its Playable NBA Games for a new Run."""

    def __init__(
        self,
        *,
        stats_source: StatsSource,
        historical_start_year: int,
        historical_end_year: int,
        historical_rounds: int,
        historical_max_date_probes: int,
        playable_game_fetch_concurrency: int,
        non_historical_startup_games: int,
        rng: Random | None = None,
        historical_eligible_source_dates_fetcher: HistoricalEligibleSourceDatesFetcher
        | None = None,
    ) -> None:
        self._stats_source = stats_source
        self._rng = rng or Random()
        self._historical_start_year = historical_start_year
        self._historical_end_year = historical_end_year
        self._historical_rounds = historical_rounds
        self._historical_max_date_probes = historical_max_date_probes
        self._playable_game_fetch_concurrency = playable_game_fetch_concurrency
        self._non_historical_startup_games = non_historical_startup_games
        self._historical_eligible_source_dates_fetcher = historical_eligible_source_dates_fetcher

    async def resolve(
        self,
        *,
        mode: GameMode,
        source_date: date | None,
        candidate_dates: Sequence[date] | None,
        total_questions: int,
    ) -> tuple[date, tuple[NBAGame, ...]]:
        if source_date is not None:
            return await self._resolve_nba_games_for_source_date(
                mode=mode,
                source_date=source_date,
                total_questions=total_questions,
            )

        if candidate_dates is None:
            if mode is GameMode.HISTORICAL:
                return await self._resolve_historical_nba_games(total_questions=total_questions)
            raise ValueError("candidate_dates is required when source_date is not provided.")

        return await self._resolve_nba_games_from_candidate_source_dates(
            mode=mode,
            candidate_dates=candidate_dates,
            total_questions=total_questions,
        )

    async def _resolve_nba_games_for_source_date(
        self,
        *,
        mode: GameMode,
        source_date: date,
        total_questions: int,
    ) -> tuple[date, tuple[NBAGame, ...]]:
        game_shells = tuple(
            sorted(
                await self._stats_source.get_games_by_date(source_date),
                key=lambda game: game.game_id,
            )
        )
        if not game_shells:
            raise LookupError(f"No games found for source date: {source_date.isoformat()}")

        full_games = await self._fetch_playable_nba_games(
            game_shells,
            total_questions=total_questions,
            max_games=(
                self._historical_rounds
                if mode is GameMode.HISTORICAL
                else self._non_historical_startup_games
            ),
        )
        if not full_games:
            raise LookupError(f"No playable games found for source date: {source_date.isoformat()}")
        if mode is GameMode.HISTORICAL:
            return source_date, self._sample_historical_nba_games(source_date, full_games)
        return source_date, full_games

    async def _resolve_nba_games_from_candidate_source_dates(
        self,
        *,
        mode: GameMode,
        candidate_dates: Sequence[date],
        total_questions: int,
    ) -> tuple[date, tuple[NBAGame, ...]]:
        last_error: Exception | None = None
        saw_games = False
        max_games = (
            self._historical_rounds
            if mode is GameMode.HISTORICAL
            else self._non_historical_startup_games
        )

        for current_date in candidate_dates:
            try:
                game_shells = tuple(await self._stats_source.get_games_by_date(current_date))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_error = exc
                continue
            if game_shells:
                saw_games = True

            full_games = await self._fetch_playable_nba_games(
                tuple(sorted(game_shells, key=lambda game: game.game_id)),
                total_questions=total_questions,
                max_games=max_games,
            )
            if full_games:
                if mode is GameMode.HISTORICAL:
                    return current_date, self._sample_historical_nba_games(current_date, full_games)
                return current_date, full_games

        if saw_games:
            raise LookupError("No playable games found for provided candidate dates.")
        if last_error is not None:
            raise LookupError("No games found for provided candidate dates.") from last_error
        raise LookupError("No games found for provided candidate dates.")

    async def _resolve_historical_nba_games(
        self,
        *,
        total_questions: int,
    ) -> tuple[date, tuple[NBAGame, ...]]:
        if self._historical_eligible_source_dates_fetcher is not None:
            eligible_dates = tuple(
                await self._historical_eligible_source_dates_fetcher(
                    self._historical_start_year,
                    self._historical_end_year,
                    self._required_historical_games,
                )
            )
            if not eligible_dates:
                raise LookupError("No historical date with playable games was found.")
            shuffled = list(eligible_dates)
            self._rng.shuffle(shuffled)
            probe_dates: Sequence[date] = shuffled[: self._historical_max_date_probes]
            enforce_min_games = False
        else:
            probe_dates = self._generate_random_season_source_dates(
                start_year=self._historical_start_year,
                end_year=self._historical_end_year,
                count=self._historical_max_date_probes,
            )
            enforce_min_games = True

        last_error: Exception | None = None
        for candidate_date in probe_dates:
            try:
                game_shells = tuple(
                    sorted(
                        await self._stats_source.get_games_by_date(candidate_date),
                        key=lambda game: game.game_id,
                    )
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_error = exc
                continue

            if enforce_min_games and len(game_shells) < self._required_historical_games:
                continue

            full_games = await self._fetch_playable_nba_games(
                game_shells,
                total_questions=total_questions,
                max_games=self._historical_rounds,
            )
            if full_games:
                return candidate_date, self._sample_historical_nba_games(candidate_date, full_games)

        error = LookupError(
            f"No historical date with playable games was found after {len(probe_dates)} probes."
        )
        if last_error is not None:
            raise error from last_error
        raise error

    async def _fetch_playable_nba_games(
        self,
        game_shells: Sequence[NBAGame],
        *,
        total_questions: int,
        max_games: int | None = None,
    ) -> tuple[NBAGame, ...]:
        playable: list[NBAGame] = []
        needs_fetch: list[NBAGame] = []

        for game in game_shells:
            if game.player_lines:
                if self._can_generate_round(game, total_questions=total_questions):
                    playable.append(game)
                    if max_games is not None and len(playable) >= max_games:
                        return tuple(playable)
            else:
                needs_fetch.append(game)

        self._rng.shuffle(needs_fetch)
        step = self._playable_game_fetch_concurrency
        next_fetch_index = 0
        pending: set[asyncio.Task[NBAGame | None]] = set()
        task_order: dict[asyncio.Task[NBAGame | None], int] = {}

        try:
            while next_fetch_index < len(needs_fetch) or pending:
                while (
                    next_fetch_index < len(needs_fetch)
                    and len(pending) < step
                    and (max_games is None or len(playable) < max_games)
                ):
                    game_shell = needs_fetch[next_fetch_index]
                    task = asyncio.create_task(
                        self._fetch_playable_nba_game(
                            game_shell,
                            total_questions=total_questions,
                        )
                    )
                    pending.add(task)
                    task_order[task] = next_fetch_index
                    next_fetch_index += 1

                if not pending:
                    break

                done, pending = await asyncio.wait(
                    pending,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in sorted(done, key=task_order.__getitem__):
                    full_game = task.result()
                    if full_game is None:
                        continue
                    playable.append(full_game)
                    if max_games is not None and len(playable) >= max_games:
                        return tuple(playable)
        finally:
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

        return tuple(playable)

    async def _fetch_playable_nba_game(
        self,
        game_shell: NBAGame,
        *,
        total_questions: int,
    ) -> NBAGame | None:
        try:
            full_game = await self._stats_source.get_nba_game(
                game_shell.game_id,
                source_date_fallback=game_shell.source_date,
            )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            return None

        if self._can_generate_round(full_game, total_questions=total_questions):
            return full_game
        return None

    def _generate_random_season_source_dates(
        self,
        *,
        start_year: int,
        end_year: int,
        count: int,
    ) -> tuple[date, ...]:
        candidates: list[date] = []
        attempts = 0
        max_attempts = count * 3
        seen: set[date] = set()
        while len(candidates) < count and attempts < max_attempts:
            attempts += 1
            year = self._rng.randint(start_year, end_year)
            month = self._rng.choice(_NBA_HISTORICAL_PROBE_MONTHS)
            max_day = calendar.monthrange(year, month)[1]
            day = self._rng.randint(1, max_day)
            candidate = self._normalize_historical_probe_date(date(year, month, day))
            if candidate not in seen:
                seen.add(candidate)
                candidates.append(candidate)
        return tuple(candidates)

    @staticmethod
    def _normalize_historical_probe_date(candidate: date) -> date:
        if candidate.weekday() in _NBA_HISTORICAL_PREFERRED_WEEKDAYS:
            return candidate

        max_day = calendar.monthrange(candidate.year, candidate.month)[1]
        for offset in range(1, 4):
            for direction in (1, -1):
                adjusted_day = candidate.day + (offset * direction)
                if adjusted_day < 1 or adjusted_day > max_day:
                    continue
                adjusted = date(candidate.year, candidate.month, adjusted_day)
                if adjusted.weekday() in _NBA_HISTORICAL_PREFERRED_WEEKDAYS:
                    return adjusted
        return candidate

    @property
    def _required_historical_games(self) -> int:
        return max(MIN_HISTORICAL_GAMES, self._historical_rounds)

    def _sample_historical_nba_games(
        self,
        selected_date: date,
        games_for_date: tuple[NBAGame, ...],
    ) -> tuple[NBAGame, ...]:
        total_games = len(games_for_date)
        if total_games < 1:
            raise LookupError(f"Historical date {selected_date.isoformat()} has no playable games.")

        sampled_games = self._rng.sample(
            games_for_date,
            k=min(self._historical_rounds, total_games),
        )
        return tuple(sorted(sampled_games, key=lambda game: game.game_id))

    @staticmethod
    def _can_generate_round(game: NBAGame, *, total_questions: int) -> bool:
        try:
            generate_round(game, total_questions=total_questions)
        except ValueError:
            return False
        return True
