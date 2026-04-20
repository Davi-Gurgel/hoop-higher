from __future__ import annotations

import asyncio
import warnings
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import ContextManager

from sqlalchemy.engine import Engine
from hoophigher.data.api.base import StatsProvider
from hoophigher.data.cache_repository import CacheRepository
from hoophigher.data.db import create_sqlite_engine, init_db, session_scope
from hoophigher.domain.models import GameBoxScore
from hoophigher.domain.models import PlayerLine, TeamGameInfo

ScoreboardFetch = Callable[[date, int], Mapping[str, object]]
BoxScoreFetch = Callable[[str, int], Mapping[str, object]]
CacheRepositoryContextFactory = Callable[[], ContextManager[CacheRepository]]
DEFAULT_BOXSCORE_FETCH_CONCURRENCY = 6


@dataclass(frozen=True, slots=True)
class _ScoreboardSeed:
    game_id: str
    game_date: date
    home_team: TeamGameInfo
    away_team: TeamGameInfo


class NBAApiProvider(StatsProvider):
    def __init__(
        self,
        *,
        cache_repository_factory: CacheRepositoryContextFactory | None = None,
        engine: Engine | None = None,
        scoreboard_fetch: ScoreboardFetch | None = None,
        boxscore_fetch: BoxScoreFetch | None = None,
        timeout_seconds: int = 20,
        max_retries: int = 2,
        boxscore_fetch_concurrency: int = DEFAULT_BOXSCORE_FETCH_CONCURRENCY,
    ) -> None:
        if timeout_seconds < 1:
            raise ValueError("timeout_seconds must be at least 1.")
        if max_retries < 0:
            raise ValueError("max_retries must be greater than or equal to 0.")
        if boxscore_fetch_concurrency < 1:
            raise ValueError("boxscore_fetch_concurrency must be at least 1.")

        if cache_repository_factory is not None:
            self._cache_repository_factory = cache_repository_factory
        else:
            provider_engine = engine or self._create_default_engine()
            self._cache_repository_factory = self._build_cache_factory(provider_engine)

        self._scoreboard_fetch = scoreboard_fetch or _default_scoreboard_fetch
        self._boxscore_fetch = boxscore_fetch or _default_boxscore_fetch
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._boxscore_fetch_concurrency = boxscore_fetch_concurrency

    async def get_games_by_date(self, game_date: date) -> list[GameBoxScore]:
        with self._cache_repository_factory() as cache_repository:
            cached_games = cache_repository.get_games_by_date(game_date)
        if cached_games is not None:
            return cached_games

        payload = await self._fetch_with_retries(
            fetch_operation=self._scoreboard_fetch,
            fetch_args=(game_date, self._timeout_seconds),
            operation_name="scoreboard",
            operation_context=f"game_date={game_date.isoformat()}",
        )
        seeds = _parse_scoreboard_payload(payload, expected_date=game_date)

        games = list(await self._get_seeded_boxscores(seeds))

        games.sort(key=lambda game: game.game_id)
        with self._cache_repository_factory() as cache_repository:
            cache_repository.set_games_by_date(game_date, games)
        return games

    async def get_game_boxscore(self, game_id: str) -> GameBoxScore:
        return await self._get_game_boxscore(game_id, game_date_fallback=None)

    async def _get_seeded_boxscores(self, seeds: Sequence[_ScoreboardSeed]) -> tuple[GameBoxScore, ...]:
        semaphore = asyncio.Semaphore(self._boxscore_fetch_concurrency)

        async def fetch_seed(seed: _ScoreboardSeed) -> GameBoxScore:
            async with semaphore:
                game = await self._get_game_boxscore(seed.game_id, game_date_fallback=seed.game_date)
            return _merge_game_seed(seed=seed, game=game)

        return tuple(await asyncio.gather(*(fetch_seed(seed) for seed in seeds)))

    async def _get_game_boxscore(
        self,
        game_id: str,
        *,
        game_date_fallback: date | None,
    ) -> GameBoxScore:
        with self._cache_repository_factory() as cache_repository:
            cached_game = cache_repository.get_game_boxscore(game_id)
        if cached_game is not None:
            return cached_game

        payload = await self._fetch_with_retries(
            fetch_operation=self._boxscore_fetch,
            fetch_args=(game_id, self._timeout_seconds),
            operation_name="boxscore",
            operation_context=f"game_id={game_id}",
        )
        game = _parse_boxscore_payload(
            payload,
            expected_game_id=game_id,
            game_date_fallback=game_date_fallback,
        )
        with self._cache_repository_factory() as cache_repository:
            cache_repository.set_game_boxscore(game)
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

        if last_error is None:
            raise LookupError(
                f"Failed to fetch {operation_name} with retries exhausted ({operation_context})."
            )

        raise LookupError(
            f"Failed to fetch {operation_name} after {attempts} attempts ({operation_context})."
        ) from last_error

    def _create_default_engine(self) -> Engine:
        database_path = Path("var/hoophigher.db").resolve()
        engine = create_sqlite_engine(f"sqlite:///{database_path}")
        init_db(engine)
        return engine

    def _build_cache_factory(self, engine: Engine) -> CacheRepositoryContextFactory:
        @contextmanager
        def cache_context() -> Iterator[CacheRepository]:
            with session_scope(engine) as session:
                yield CacheRepository(session)

        return cache_context


def _default_scoreboard_fetch(game_date: date, timeout_seconds: int) -> Mapping[str, object]:
    try:
        from nba_api.stats.endpoints import scoreboardv3
    except ImportError:
        scoreboardv3 = None

    if scoreboardv3 is not None:
        endpoint = scoreboardv3.ScoreboardV3(
            game_date=game_date.isoformat(),
            timeout=timeout_seconds,
        )
        payload = endpoint.get_dict()
        if _looks_like_scoreboard_v3_payload(payload):
            return payload

    # Fallback for environments where V3 is unavailable or returns an unexpected shape.
    from nba_api.stats.endpoints import scoreboardv2

    endpoint_v2 = scoreboardv2.ScoreboardV2(
        game_date=game_date.isoformat(),
        timeout=timeout_seconds,
    )
    return endpoint_v2.get_dict()


def _default_boxscore_fetch(game_id: str, timeout_seconds: int) -> Mapping[str, object]:
    from nba_api.stats.endpoints import boxscoretraditionalv2, boxscoretraditionalv3

    try:
        endpoint = boxscoretraditionalv3.BoxScoreTraditionalV3(
            game_id=game_id,
            timeout=timeout_seconds,
        )
        return endpoint.get_dict()
    except Exception:
        pass

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        endpoint_v2 = boxscoretraditionalv2.BoxScoreTraditionalV2(
            game_id=game_id,
            timeout=timeout_seconds,
        )
    return endpoint_v2.get_dict()


def _looks_like_scoreboard_v3_payload(payload: object) -> bool:
    if not isinstance(payload, Mapping):
        return False
    scoreboard = payload.get("scoreboard")
    if not isinstance(scoreboard, Mapping):
        return False
    games = scoreboard.get("games")
    return isinstance(games, list)


def _parse_scoreboard_payload(payload: Mapping[str, object], *, expected_date: date) -> list[_ScoreboardSeed]:
    v3_seeds = _parse_scoreboard_v3_payload(payload, expected_date=expected_date)
    if v3_seeds is not None:
        return v3_seeds
    return _parse_scoreboard_v2_payload(payload, expected_date=expected_date)


def _parse_scoreboard_v3_payload(
    payload: Mapping[str, object],
    *,
    expected_date: date,
) -> list[_ScoreboardSeed] | None:
    scoreboard = payload.get("scoreboard")
    if scoreboard is None:
        return None
    if not isinstance(scoreboard, Mapping):
        raise ValueError("Malformed scoreboard payload: expected mapping at payload['scoreboard'].")

    games = scoreboard.get("games")
    if not isinstance(games, list):
        raise ValueError("Malformed scoreboard payload: expected list at payload['scoreboard']['games'].")

    seeds: list[_ScoreboardSeed] = []
    for raw_game in games:
        if not isinstance(raw_game, Mapping):
            raise ValueError("Malformed scoreboard payload: expected mapping for each game entry.")
        game_id = _require_str(raw_game.get("gameId"), field="scoreboard.games[].gameId")
        game_date = _parse_date_field(
            raw_game.get("gameDate") or raw_game.get("gameDateEst"),
            field="scoreboard.games[].gameDate",
            fallback=expected_date,
        )
        home_raw = _require_mapping(raw_game.get("homeTeam"), field="scoreboard.games[].homeTeam")
        away_raw = _require_mapping(raw_game.get("awayTeam"), field="scoreboard.games[].awayTeam")

        seeds.append(
            _ScoreboardSeed(
                game_id=game_id,
                game_date=game_date,
                home_team=_parse_team(
                    home_raw,
                    field="scoreboard.games[].homeTeam",
                    team_id_keys=("teamId",),
                    abbreviation_keys=("teamTricode", "teamAbbreviation"),
                    name_keys=("teamName",),
                    score_keys=("score",),
                ),
                away_team=_parse_team(
                    away_raw,
                    field="scoreboard.games[].awayTeam",
                    team_id_keys=("teamId",),
                    abbreviation_keys=("teamTricode", "teamAbbreviation"),
                    name_keys=("teamName",),
                    score_keys=("score",),
                ),
            )
        )
    return seeds


def _parse_scoreboard_v2_payload(
    payload: Mapping[str, object],
    *,
    expected_date: date,
) -> list[_ScoreboardSeed]:
    result_sets = _require_list(payload.get("resultSets"), field="payload['resultSets']")
    game_headers = _parse_v2_result_set(result_sets, set_name="GameHeader")
    line_scores = _parse_v2_result_set(result_sets, set_name="LineScore", optional=True)

    tricode_by_game_and_team: dict[tuple[str, str], str] = {}
    for line in line_scores:
        game_id = _optional_str(line.get("GAME_ID"))
        team_id = _optional_str(line.get("TEAM_ID"))
        tricode = _optional_str(line.get("TEAM_ABBREVIATION"))
        if game_id and team_id and tricode:
            tricode_by_game_and_team[(game_id, team_id)] = tricode

    seeds: list[_ScoreboardSeed] = []
    for row in game_headers:
        game_id = _require_str(row.get("GAME_ID"), field="resultSets.GameHeader.GAME_ID")
        game_date = _parse_date_field(
            row.get("GAME_DATE_EST"),
            field="resultSets.GameHeader.GAME_DATE_EST",
            fallback=expected_date,
        )
        home_team_id = _require_str(row.get("HOME_TEAM_ID"), field="resultSets.GameHeader.HOME_TEAM_ID")
        away_team_id = _require_str(
            row.get("VISITOR_TEAM_ID"),
            field="resultSets.GameHeader.VISITOR_TEAM_ID",
        )
        home_abbrev = tricode_by_game_and_team.get((game_id, home_team_id), "UNK")
        away_abbrev = tricode_by_game_and_team.get((game_id, away_team_id), "UNK")

        seeds.append(
            _ScoreboardSeed(
                game_id=game_id,
                game_date=game_date,
                home_team=TeamGameInfo(
                    team_id=home_team_id,
                    name=home_abbrev,
                    abbreviation=home_abbrev,
                    score=_optional_int(row.get("PTS_HOME")),
                ),
                away_team=TeamGameInfo(
                    team_id=away_team_id,
                    name=away_abbrev,
                    abbreviation=away_abbrev,
                    score=_optional_int(row.get("PTS_AWAY")),
                ),
            )
        )
    return seeds


def _parse_v2_result_set(
    result_sets: list[object],
    *,
    set_name: str,
    optional: bool = False,
) -> list[dict[str, object]]:
    for result_set in result_sets:
        if not isinstance(result_set, Mapping):
            continue
        name = _optional_str(result_set.get("name"))
        if name != set_name:
            continue
        headers = _require_list(result_set.get("headers"), field=f"resultSets.{set_name}.headers")
        row_set = _require_list(result_set.get("rowSet"), field=f"resultSets.{set_name}.rowSet")
        parsed_rows: list[dict[str, object]] = []
        for raw_row in row_set:
            if not isinstance(raw_row, list):
                raise ValueError(f"Malformed payload: expected list rows in resultSets.{set_name}.rowSet.")
            parsed_rows.append(dict(zip([str(header) for header in headers], raw_row, strict=False)))
        return parsed_rows
    if optional:
        return []
    raise ValueError(f"Malformed payload: missing result set '{set_name}'.")


def _parse_boxscore_payload(
    payload: Mapping[str, object],
    *,
    expected_game_id: str,
    game_date_fallback: date | None = None,
) -> GameBoxScore:
    if "boxScoreTraditional" in payload:
        box = _require_mapping(payload.get("boxScoreTraditional"), field="payload['boxScoreTraditional']")
        return _parse_boxscore_v3_payload(
            box,
            expected_game_id=expected_game_id,
            game_date_fallback=game_date_fallback,
        )

    if "resultSets" in payload:
        return _parse_boxscore_v2_payload(
            payload,
            expected_game_id=expected_game_id,
            game_date_fallback=game_date_fallback,
        )

    raise ValueError("Malformed boxscore payload: expected V3 or V2 structure.")


def _parse_boxscore_v3_payload(
    box: Mapping[str, object],
    *,
    expected_game_id: str,
    game_date_fallback: date | None,
) -> GameBoxScore:
    game_id = _optional_str(box.get("gameId"))
    if not game_id:
        game_meta = box.get("game")
        if isinstance(game_meta, Mapping):
            game_id = _optional_str(game_meta.get("gameId"))
    if not game_id or game_id != expected_game_id:
        raise LookupError(f"Game id '{expected_game_id}' not found in boxscore payload.")

    game_date = _parse_date_field(
        box.get("gameDate") or box.get("gameDateEst"),
        field="boxScoreTraditional.gameDate",
        fallback=game_date_fallback,
    )
    home_raw = _require_mapping(box.get("homeTeam"), field="boxScoreTraditional.homeTeam")
    away_raw = _require_mapping(box.get("awayTeam"), field="boxScoreTraditional.awayTeam")

    home_team = _parse_boxscore_v3_team(home_raw, field="boxScoreTraditional.homeTeam")
    away_team = _parse_boxscore_v3_team(away_raw, field="boxScoreTraditional.awayTeam")

    flat_players_raw = box.get("playersStats") or box.get("playerStats")
    if flat_players_raw is None:
        players = (
            _parse_v3_nested_player_rows(home_raw, team=home_team, field="boxScoreTraditional.homeTeam.players")
            + _parse_v3_nested_player_rows(away_raw, team=away_team, field="boxScoreTraditional.awayTeam.players")
        )
    else:
        players = _parse_player_rows(
            _require_list(flat_players_raw, field="boxScoreTraditional.playersStats"),
            field="boxScoreTraditional.playersStats",
        )
    return GameBoxScore(
        game_id=game_id,
        game_date=game_date,
        home_team=home_team,
        away_team=away_team,
        player_lines=tuple(players),
    )


def _parse_boxscore_v2_payload(
    payload: Mapping[str, object],
    *,
    expected_game_id: str,
    game_date_fallback: date | None,
) -> GameBoxScore:
    result_sets = _require_list(payload.get("resultSets"), field="payload['resultSets']")
    game_headers = _parse_v2_result_set(result_sets, set_name="GameSummary", optional=True)
    team_rows = _parse_v2_result_set(result_sets, set_name="TeamStats")
    player_rows = _parse_v2_result_set(result_sets, set_name="PlayerStats")

    target_header = _find_v2_game_summary(game_headers, expected_game_id=expected_game_id)
    game_date = _parse_v2_game_date(target_header, game_date_fallback=game_date_fallback)
    home_team_id = _optional_str(target_header.get("HOME_TEAM_ID")) if target_header is not None else None
    away_team_id = _optional_str(target_header.get("VISITOR_TEAM_ID")) if target_header is not None else None

    teams_by_id: dict[str, TeamGameInfo] = {}
    for row in team_rows:
        row_game_id = _optional_str(row.get("GAME_ID"))
        if row_game_id and row_game_id != expected_game_id:
            continue
        team_id = _optional_str(row.get("TEAM_ID"))
        if not team_id:
            continue
        teams_by_id[team_id] = TeamGameInfo(
            team_id=team_id,
            name=_optional_str(row.get("TEAM_NAME")) or _require_str(
                row.get("TEAM_ABBREVIATION"),
                field="TeamStats.TEAM_ABBREVIATION",
            ),
            abbreviation=_require_str(row.get("TEAM_ABBREVIATION"), field="TeamStats.TEAM_ABBREVIATION"),
            score=_optional_int(row.get("PTS")),
        )

    home_team, away_team = _resolve_v2_teams(
        teams_by_id=teams_by_id,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
    )
    if home_team is None or away_team is None:
        raise ValueError("Malformed boxscore payload: missing TeamStats rows for home or away team.")

    players = _parse_player_rows(
        [
            row
            for row in player_rows
            if (_optional_str(row.get("GAME_ID")) or expected_game_id) == expected_game_id
        ],
        field="PlayerStats",
    )
    return GameBoxScore(
        game_id=expected_game_id,
        game_date=game_date,
        home_team=home_team,
        away_team=away_team,
        player_lines=tuple(players),
    )


def _find_v2_game_summary(
    game_headers: Sequence[Mapping[str, object]],
    *,
    expected_game_id: str,
) -> Mapping[str, object] | None:
    for header in game_headers:
        if _optional_str(header.get("GAME_ID")) == expected_game_id:
            return header
    if game_headers:
        raise LookupError(f"Game id '{expected_game_id}' not found in boxscore payload.")
    return None


def _parse_v2_game_date(
    target_header: Mapping[str, object] | None,
    *,
    game_date_fallback: date | None,
) -> date:
    if target_header is None:
        if game_date_fallback is None:
            raise ValueError("Malformed boxscore payload: missing GameSummary and date fallback.")
        return game_date_fallback
    return _parse_date_field(
        target_header.get("GAME_DATE_EST"),
        field="GameSummary.GAME_DATE_EST",
        fallback=game_date_fallback,
    )


def _resolve_v2_teams(
    *,
    teams_by_id: Mapping[str, TeamGameInfo],
    home_team_id: str | None,
    away_team_id: str | None,
) -> tuple[TeamGameInfo | None, TeamGameInfo | None]:
    if home_team_id is not None or away_team_id is not None:
        return (
            teams_by_id.get(home_team_id or ""),
            teams_by_id.get(away_team_id or ""),
        )
    teams = tuple(teams_by_id.values())
    if len(teams) != 2:
        return None, None
    return teams[0], teams[1]


def _parse_team(
    payload: Mapping[str, object],
    *,
    field: str,
    team_id_keys: Sequence[str],
    abbreviation_keys: Sequence[str],
    name_keys: Sequence[str],
    score_keys: Sequence[str],
) -> TeamGameInfo:
    team_id = _require_str(_first_value(payload, team_id_keys), field=f"{field}.teamId")
    abbreviation = _require_str(_first_value(payload, abbreviation_keys), field=f"{field}.abbreviation")
    name = _optional_str(_first_value(payload, name_keys)) or abbreviation
    score = _optional_int(_first_value(payload, score_keys))
    return TeamGameInfo(team_id=team_id, name=name, abbreviation=abbreviation, score=score)


def _parse_boxscore_v3_team(payload: Mapping[str, object], *, field: str) -> TeamGameInfo:
    team_id = _require_str(payload.get("teamId"), field=f"{field}.teamId")
    abbreviation = _require_str(
        payload.get("teamTricode") or payload.get("teamAbbreviation"),
        field=f"{field}.teamTricode",
    )
    name = _optional_str(payload.get("teamName")) or abbreviation
    statistics = payload.get("statistics")
    stats = statistics if isinstance(statistics, Mapping) else {}
    score = _optional_int(payload.get("score") if payload.get("score") is not None else stats.get("points"))
    return TeamGameInfo(team_id=team_id, name=name, abbreviation=abbreviation, score=score)


def _parse_v3_nested_player_rows(
    team_payload: Mapping[str, object],
    *,
    team: TeamGameInfo,
    field: str,
) -> list[PlayerLine]:
    players_raw = _require_list(team_payload.get("players"), field=field)
    flattened_players: list[Mapping[str, object]] = []
    for player in players_raw:
        if not isinstance(player, Mapping):
            raise ValueError(f"Malformed payload: expected mapping rows for {field}.")
        statistics = player.get("statistics")
        stats = statistics if isinstance(statistics, Mapping) else {}
        flattened_players.append({**player, **stats})
    return _parse_player_rows(flattened_players, field=field, team=team)


def _parse_player_rows(
    rows: Sequence[object],
    *,
    field: str,
    team: TeamGameInfo | None = None,
) -> list[PlayerLine]:
    players: list[PlayerLine] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError(f"Malformed payload: expected mapping rows for {field}.")
        player_id = _optional_str(row.get("personId") or row.get("PLAYER_ID"))
        if not player_id:
            continue

        player_name = _parse_player_name(row)
        if not player_name:
            raise ValueError(f"Malformed payload: missing player name in {field}.")

        team_id = _optional_str(row.get("teamId") or row.get("TEAM_ID")) or (team.team_id if team else None)
        team_abbreviation = _optional_str(
            row.get("teamTricode") or row.get("teamAbbreviation") or row.get("TEAM_ABBREVIATION")
        ) or (team.abbreviation if team else None)
        points = _int_or_zero(row.get("points") if "points" in row else row.get("PTS"))
        minutes = _parse_minutes(row.get("minutes") if "minutes" in row else row.get("MIN"))

        players.append(
            PlayerLine(
                player_id=player_id,
                player_name=player_name,
                team_id=_require_str(team_id, field=f"{field}.teamId"),
                team_abbreviation=_require_str(team_abbreviation, field=f"{field}.teamAbbreviation"),
                points=points,
                minutes=minutes,
            )
        )
    return players


def _parse_player_name(row: Mapping[str, object]) -> str | None:
    explicit_name = _optional_str(row.get("name") or row.get("playerName") or row.get("PLAYER_NAME"))
    if explicit_name:
        return explicit_name
    first_name = _optional_str(row.get("firstName"))
    family_name = _optional_str(row.get("familyName"))
    if first_name and family_name:
        return f"{first_name} {family_name}"
    return first_name or family_name or _optional_str(row.get("nameI"))


def _merge_game_seed(*, seed: _ScoreboardSeed, game: GameBoxScore) -> GameBoxScore:
    if game.game_id != seed.game_id:
        raise LookupError(f"Game id '{seed.game_id}' not found in fetched payload.")
    home_team = TeamGameInfo(
        team_id=game.home_team.team_id,
        name=game.home_team.name,
        abbreviation=seed.home_team.abbreviation or game.home_team.abbreviation,
        score=seed.home_team.score if seed.home_team.score is not None else game.home_team.score,
    )
    away_team = TeamGameInfo(
        team_id=game.away_team.team_id,
        name=game.away_team.name,
        abbreviation=seed.away_team.abbreviation or game.away_team.abbreviation,
        score=seed.away_team.score if seed.away_team.score is not None else game.away_team.score,
    )
    return GameBoxScore(
        game_id=game.game_id,
        game_date=seed.game_date,
        home_team=home_team,
        away_team=away_team,
        player_lines=game.player_lines,
    )


def _first_value(payload: Mapping[str, object], keys: Sequence[str]) -> object | None:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return None


def _require_mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"Malformed payload: expected mapping at {field}.")
    return value


def _require_list(value: object, *, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"Malformed payload: expected list at {field}.")
    return value


def _require_str(value: object, *, field: str) -> str:
    text = _optional_str(value)
    if not text:
        raise ValueError(f"Malformed payload: missing or empty field {field}.")
    return text


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Malformed payload: invalid integer value {value!r}.") from exc


def _int_or_zero(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, str) and not value.strip():
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Malformed payload: invalid points value {value!r}.") from exc


def _parse_date_field(value: object, *, field: str, fallback: date | None = None) -> date:
    if value is None:
        if fallback is not None:
            return fallback
        raise ValueError(f"Malformed payload: missing date field {field}.")

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = _optional_str(value)
    if text is None:
        if fallback is not None:
            return fallback
        raise ValueError(f"Malformed payload: missing date field {field}.")

    try:
        return date.fromisoformat(text)
    except ValueError:
        pass

    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Malformed payload: unsupported date format for {field}: {text!r}.")


def _parse_minutes(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip()
    if not text:
        return 0

    if ":" in text:
        minutes_text = text.split(":", 1)[0].strip()
        if not minutes_text:
            return 0
        try:
            return int(minutes_text)
        except ValueError as exc:
            raise ValueError(f"Malformed payload: invalid minutes value {value!r}.") from exc

    if text.startswith("PT") and "M" in text:
        try:
            minutes_text = text[2 : text.index("M")]
            return int(minutes_text)
        except (ValueError, IndexError) as exc:
            raise ValueError(f"Malformed payload: invalid minutes value {value!r}.") from exc

    try:
        return int(float(text))
    except ValueError as exc:
        raise ValueError(f"Malformed payload: invalid minutes value {value!r}.") from exc
