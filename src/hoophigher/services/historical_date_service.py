from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import date, datetime

from hoophigher.data.repositories import HistoricalIndexRepository

SEASON_TYPES: tuple[str, ...] = (
    "Pre Season",
    "Regular Season",
    "Playoffs",
    "All Star",
)

LeagueGameLogRow = Mapping[str, object]
LeagueGameLogFetcher = Callable[[str, str, int], Awaitable[Sequence[LeagueGameLogRow]]]


class HistoricalDateService:
    def __init__(
        self,
        *,
        index_repository: HistoricalIndexRepository,
        fetcher: LeagueGameLogFetcher | None = None,
        timeout_seconds: int = 20,
    ) -> None:
        if timeout_seconds < 1:
            raise ValueError("timeout_seconds must be at least 1.")
        self._index_repository = index_repository
        self._fetcher = fetcher or self._default_fetcher
        self._timeout_seconds = timeout_seconds

    async def get_or_build_eligible_dates(
        self,
        *,
        start_year: int,
        end_year: int,
        min_games: int,
    ) -> tuple[date, ...]:
        if start_year > end_year:
            raise ValueError(
                f"Invalid year window: start_year ({start_year}) must be less than or equal to end_year ({end_year})."
            )
        if min_games < 1:
            raise ValueError(f"min_games must be at least 1 (got {min_games}).")

        indexed_dates = self._index_repository.list_window_dates(
            start_year=start_year,
            end_year=end_year,
            min_games=min_games,
        )
        if indexed_dates:
            return tuple(indexed_dates)

        unique_games_by_date: dict[date, set[str]] = defaultdict(set)
        for season in self._iter_seasons_for_window(start_year=start_year, end_year=end_year):
            for season_type in SEASON_TYPES:
                rows = await self._fetcher(season, season_type, self._timeout_seconds)
                self._accumulate_rows(unique_games_by_date=unique_games_by_date, rows=rows)

        eligible_rows: list[tuple[date, int]] = []
        for game_date, game_ids in unique_games_by_date.items():
            if start_year <= game_date.year <= end_year and len(game_ids) >= min_games:
                eligible_rows.append((game_date, len(game_ids)))

        eligible_rows.sort(key=lambda item: item[0])
        if not eligible_rows:
            raise LookupError(
                "No eligible historical dates found "
                f"for window {start_year}-{end_year} with min_games={min_games}."
            )

        self._index_repository.replace_window(
            start_year=start_year,
            end_year=end_year,
            min_games=min_games,
            rows=eligible_rows,
        )

        return tuple(game_date for game_date, _ in eligible_rows)

    async def _default_fetcher(
        self,
        season: str,
        season_type: str,
        timeout_seconds: int,
    ) -> Sequence[LeagueGameLogRow]:
        return await asyncio.to_thread(
            self._fetch_league_game_log_sync,
            season,
            season_type,
            timeout_seconds,
        )

    def _fetch_league_game_log_sync(
        self,
        season: str,
        season_type: str,
        timeout_seconds: int,
    ) -> Sequence[LeagueGameLogRow]:
        from nba_api.stats.endpoints import leaguegamelog

        endpoint = leaguegamelog.LeagueGameLog(
            season=season,
            season_type_all_star=season_type,
            player_or_team_abbreviation="T",
            timeout=timeout_seconds,
        )
        payload = endpoint.get_dict()
        return self._parse_league_game_log_payload(payload, season=season, season_type=season_type)

    def _parse_league_game_log_payload(
        self,
        payload: object,
        *,
        season: str,
        season_type: str,
    ) -> Sequence[LeagueGameLogRow]:
        if not isinstance(payload, Mapping):
            raise ValueError(
                "Malformed LeagueGameLog payload for "
                f"season={season!r} season_type={season_type!r}: expected mapping, got {type(payload).__name__}."
            )

        result_sets = payload.get("resultSets")
        if not isinstance(result_sets, list) or not result_sets:
            raise ValueError(
                "Malformed LeagueGameLog payload for "
                f"season={season!r} season_type={season_type!r}: expected non-empty list at payload['resultSets']."
            )

        first_set = result_sets[0]
        if not isinstance(first_set, Mapping):
            raise ValueError(
                "Malformed LeagueGameLog payload for "
                f"season={season!r} season_type={season_type!r}: expected mapping at payload['resultSets'][0]."
            )

        headers_value = first_set.get("headers")
        row_set_value = first_set.get("rowSet")
        if not isinstance(headers_value, list) or not isinstance(row_set_value, list):
            raise ValueError(
                "Malformed LeagueGameLog payload for "
                f"season={season!r} season_type={season_type!r}: expected list values for headers and rowSet in payload['resultSets'][0]."
            )

        headers = [str(header) for header in headers_value]
        parsed_rows: list[dict[str, object]] = []
        for raw_row in row_set_value:
            if not isinstance(raw_row, list):
                continue
            parsed_rows.append(dict(zip(headers, raw_row, strict=False)))
        return tuple(parsed_rows)

    def _iter_seasons_for_window(self, *, start_year: int, end_year: int) -> tuple[str, ...]:
        first_season_start_year = start_year - 1
        last_season_start_year = end_year
        return tuple(
            self._format_season(starting_year)
            for starting_year in range(first_season_start_year, last_season_start_year + 1)
        )

    def _format_season(self, starting_year: int) -> str:
        ending_year_suffix = (starting_year + 1) % 100
        return f"{starting_year}-{ending_year_suffix:02d}"

    def _accumulate_rows(
        self,
        *,
        unique_games_by_date: dict[date, set[str]],
        rows: Sequence[LeagueGameLogRow],
    ) -> None:
        for row in rows:
            game_id_raw = row.get("GAME_ID")
            game_date_raw = row.get("GAME_DATE")
            if not isinstance(game_id_raw, str) or not game_id_raw:
                continue
            game_date = self._parse_game_date(game_date_raw)
            unique_games_by_date[game_date].add(game_id_raw)

    def _parse_game_date(self, raw_value: object) -> date:
        if isinstance(raw_value, datetime):
            return raw_value.date()

        if isinstance(raw_value, date):
            return raw_value

        if not isinstance(raw_value, str):
            raise ValueError(f"Invalid GAME_DATE value: {raw_value!r}")

        normalized_value = raw_value.strip()
        if not normalized_value:
            raise ValueError("GAME_DATE is empty.")

        try:
            return date.fromisoformat(normalized_value)
        except ValueError:
            pass

        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%b %d, %Y"):
            try:
                return datetime.strptime(normalized_value, fmt).date()
            except ValueError:
                continue

        raise ValueError(f"Unsupported GAME_DATE format: {normalized_value!r}")
