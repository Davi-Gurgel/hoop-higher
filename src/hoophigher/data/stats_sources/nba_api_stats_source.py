from __future__ import annotations

import asyncio
import time
import warnings
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import date
from typing import ContextManager

from sqlalchemy.engine import Engine
from hoophigher.data.stats_sources.base import StatsSource
from hoophigher.data.cache_repository import CacheRepository
from hoophigher.data.db import create_sqlite_engine, default_sqlite_url, init_db, session_scope
from hoophigher.data.stats_sources import nba_api_parsing
from hoophigher.data.stats_sources.nba_api_parsing import (
    NON_FINAL_GAME_STATUSES,
    _has_available_player_stats,
    _is_game_shell,
    _looks_like_scoreboard_v3_payload,
    _merge_game_seed,
    _parse_nba_game_payload,
    _parse_scoreboard_payload,
)
from hoophigher.domain.models import NBAGame

# Compatibility aliases for callers that imported these parser details from
# this module before parsing moved to ``nba_api_parsing``.
GameStatus = nba_api_parsing.GameStatus
_parse_game_status = nba_api_parsing._parse_game_status

ScoreboardFetch = Callable[[date, float], Mapping[str, object]]
NBAGameFetch = Callable[[str, float], Mapping[str, object]]
CacheRepositoryContextFactory = Callable[[], ContextManager[CacheRepository]]


class NBAApiStatsSource(StatsSource):
    def __init__(
        self,
        *,
        cache_repository_factory: CacheRepositoryContextFactory | None = None,
        engine: Engine | None = None,
        scoreboard_fetch: ScoreboardFetch | None = None,
        nba_game_fetch: NBAGameFetch | None = None,
        timeout_seconds: int,
        max_retries: int,
        retry_delay_seconds: float,
    ) -> None:
        if cache_repository_factory is not None:
            self._cache_repository_factory = cache_repository_factory
        else:
            stats_source_engine = engine or self._create_default_engine()
            self._cache_repository_factory = self._build_cache_factory(stats_source_engine)

        self._scoreboard_fetch = scoreboard_fetch or _default_scoreboard_fetch
        self._nba_game_fetch = nba_game_fetch or _default_nba_game_fetch
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds

    async def get_games_by_date(self, source_date: date) -> list[NBAGame]:
        """Return games for a source date.

        Returns lightweight shells from the scoreboard when full NBA game
        data is not already cached.  The caller should use ``get_nba_game``
        to fetch full player-level data for the specific games it needs.
        """
        with self._cache_repository_factory() as cache_repository:
            cached_games = cache_repository.get_games_by_date(source_date)
        if cached_games is not None and all(
            _is_game_shell(game) or _has_available_player_stats(game.player_lines)
            for game in cached_games
        ):
            return cached_games

        payload = await self._fetch_with_retries(
            fetch_operation=self._scoreboard_fetch,
            fetch_args=(source_date, self._timeout_seconds),
            operation_name="scoreboard",
            operation_context=f"source_date={source_date.isoformat()}",
        )
        seeds = _parse_scoreboard_payload(payload, expected_date=source_date)

        # Only final games are Playable NBA Games. Live and scheduled games
        # are excluded before shells are built. A payload with no status
        # information at all preserves historical behavior (treated as
        # final).
        final_seeds = [seed for seed in seeds if seed.status not in NON_FINAL_GAME_STATUSES]
        all_games_final = len(final_seeds) == len(seeds)

        # Build lightweight game shells from scoreboard data.
        # No NBA game API calls are made here — those happen on demand
        # via get_nba_game when the gameplay service needs them.
        games: list[NBAGame] = []
        for seed in final_seeds:
            # Check if this individual game is already cached with stats.
            with self._cache_repository_factory() as cache_repository:
                cached_game = cache_repository.get_nba_game(seed.game_id)
            if cached_game is not None and _has_available_player_stats(cached_game.player_lines):
                games.append(_merge_game_seed(seed=seed, game=cached_game))
            else:
                # Return a shell with no player lines — caller fetches on demand.
                games.append(
                    NBAGame(
                        game_id=seed.game_id,
                        source_date=seed.source_date,
                        home_team=seed.home_team,
                        away_team=seed.away_team,
                        player_lines=(),
                    )
                )

        games.sort(key=lambda game: game.game_id)
        # A source date containing non-final games is not permanently
        # cached as complete — the next call re-fetches to pick up games
        # that have since gone final.
        if all_games_final:
            with self._cache_repository_factory() as cache_repository:
                cache_repository.set_games_by_date(source_date, games)
        return games

    async def get_nba_game(
        self,
        game_id: str,
        *,
        source_date_fallback: date | None = None,
    ) -> NBAGame:
        return await self._get_nba_game(
            game_id,
            source_date_fallback=source_date_fallback,
        )

    async def _get_nba_game(
        self,
        game_id: str,
        *,
        source_date_fallback: date | None,
    ) -> NBAGame:
        with self._cache_repository_factory() as cache_repository:
            cached_game = cache_repository.get_nba_game(game_id)
        if cached_game is not None and _has_available_player_stats(cached_game.player_lines):
            return cached_game

        payload = await self._fetch_with_retries(
            fetch_operation=self._nba_game_fetch,
            fetch_args=(game_id, self._timeout_seconds),
            operation_name="boxscore",
            operation_context=f"game_id={game_id}",
        )
        game = _parse_nba_game_payload(
            payload,
            expected_game_id=game_id,
            source_date_fallback=source_date_fallback,
        )
        with self._cache_repository_factory() as cache_repository:
            cache_repository.set_nba_game(game)
        return game

    async def _fetch_with_retries(
        self,
        *,
        fetch_operation: Callable[..., Mapping[str, object]],
        fetch_args: tuple[object, ...],
        operation_name: str,
        operation_context: str,
    ) -> Mapping[str, object]:
        attempts = self._max_retries + 1
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                return await asyncio.to_thread(fetch_operation, *fetch_args)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == attempts:
                    break
                if self._retry_delay_seconds > 0:
                    await asyncio.sleep(self._retry_delay_seconds * attempt)

        if last_error is None:
            raise LookupError(
                f"Failed to fetch {operation_name} with retries exhausted ({operation_context})."
            )

        raise LookupError(
            f"Failed to fetch {operation_name} after {attempts} attempts ({operation_context})."
        ) from last_error

    def _create_default_engine(self) -> Engine:
        engine = create_sqlite_engine(default_sqlite_url())
        init_db(engine)
        return engine

    def _build_cache_factory(self, engine: Engine) -> CacheRepositoryContextFactory:
        @contextmanager
        def cache_context() -> Iterator[CacheRepository]:
            with session_scope(engine) as session:
                yield CacheRepository(session)

        return cache_context


def _default_scoreboard_fetch(source_date: date, timeout_seconds: float) -> Mapping[str, object]:
    started_at = time.monotonic()
    try:
        from nba_api.stats.endpoints import scoreboardv3
    except ImportError:
        scoreboardv3 = None

    if scoreboardv3 is not None:
        try:
            # `game_date` here is the nba_api library's own parameter name.
            endpoint = scoreboardv3.ScoreboardV3(
                game_date=source_date.isoformat(),
                timeout=timeout_seconds,
            )
            payload = endpoint.get_dict()
            if _looks_like_scoreboard_v3_payload(payload):
                return payload
        except Exception:
            pass

    # Fallback for environments where V3 is unavailable or returns an unexpected shape.
    remaining_timeout_seconds = _remaining_timeout_seconds(
        timeout_seconds=timeout_seconds,
        started_at=started_at,
        operation_name="scoreboard",
    )
    from nba_api.stats.endpoints import scoreboardv2

    endpoint_v2 = scoreboardv2.ScoreboardV2(
        game_date=source_date.isoformat(),
        timeout=remaining_timeout_seconds,
    )
    return endpoint_v2.get_dict()


def _default_nba_game_fetch(game_id: str, timeout_seconds: float) -> Mapping[str, object]:
    started_at = time.monotonic()
    from nba_api.stats.endpoints import boxscoretraditionalv2, boxscoretraditionalv3

    try:
        endpoint = boxscoretraditionalv3.BoxScoreTraditionalV3(
            game_id=game_id,
            timeout=timeout_seconds,
        )
        return endpoint.get_dict()
    except Exception:
        pass

    remaining_timeout_seconds = _remaining_timeout_seconds(
        timeout_seconds=timeout_seconds,
        started_at=started_at,
        operation_name="boxscore",
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        endpoint_v2 = boxscoretraditionalv2.BoxScoreTraditionalV2(
            game_id=game_id,
            timeout=remaining_timeout_seconds,
        )
    return endpoint_v2.get_dict()


def _remaining_timeout_seconds(
    *,
    timeout_seconds: float,
    started_at: float,
    operation_name: str,
) -> float:
    remaining = timeout_seconds - (time.monotonic() - started_at)
    if remaining <= 0:
        raise TimeoutError(f"No timeout budget remaining for {operation_name} fallback request.")
    return remaining
