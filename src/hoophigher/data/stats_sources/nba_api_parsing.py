from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from hoophigher.domain.models import NBAGame, PlayerLine, TeamGameInfo


class NBAGameStatus(StrEnum):
    """NBA game status values recognized when the source reports them.

    A parsed NBA game's status is ``None`` when the payload carried no status
    information at all, in which case historical behavior is preserved: the
    NBA game is treated as final.
    """

    FINAL = "final"
    LIVE = "live"
    SCHEDULED = "scheduled"


NON_FINAL_NBA_GAME_STATUSES = (NBAGameStatus.LIVE, NBAGameStatus.SCHEDULED)

_STATUS_BY_NUMERIC_CODE: dict[int, NBAGameStatus] = {
    1: NBAGameStatus.SCHEDULED,
    2: NBAGameStatus.LIVE,
    3: NBAGameStatus.FINAL,
}


@dataclass(frozen=True, slots=True)
class ParsedScoreboardGame:
    game_id: str
    source_date: date
    home_team: TeamGameInfo
    away_team: TeamGameInfo
    status: NBAGameStatus | None = None


def looks_like_scoreboard_v3_payload(payload: object) -> bool:
    if not isinstance(payload, Mapping):
        return False
    scoreboard = payload.get("scoreboard")
    if not isinstance(scoreboard, Mapping):
        return False
    games = scoreboard.get("games")
    return isinstance(games, list)


def parse_scoreboard_payload(
    payload: Mapping[str, object], *, expected_date: date
) -> list[ParsedScoreboardGame]:
    parsed_v3_games = _parse_scoreboard_v3_payload(payload, expected_date=expected_date)
    if parsed_v3_games is not None:
        return parsed_v3_games
    return _parse_scoreboard_v2_payload(payload, expected_date=expected_date)


def _parse_scoreboard_v3_payload(
    payload: Mapping[str, object],
    *,
    expected_date: date,
) -> list[ParsedScoreboardGame] | None:
    scoreboard = payload.get("scoreboard")
    if scoreboard is None:
        return None
    if not isinstance(scoreboard, Mapping):
        raise ValueError("Malformed scoreboard payload: expected mapping at payload['scoreboard'].")

    games = scoreboard.get("games")
    if not isinstance(games, list):
        raise ValueError(
            "Malformed scoreboard payload: expected list at payload['scoreboard']['games']."
        )

    parsed_games: list[ParsedScoreboardGame] = []
    for raw_game in games:
        if not isinstance(raw_game, Mapping):
            raise ValueError("Malformed scoreboard payload: expected mapping for each game entry.")
        game_id = _require_str(raw_game.get("gameId"), field="scoreboard.games[].gameId")
        source_date = _parse_date_field(
            raw_game.get("gameDate") or raw_game.get("gameDateEst"),
            field="scoreboard.games[].gameDate",
            fallback=expected_date,
        )
        home_raw = _require_mapping(raw_game.get("homeTeam"), field="scoreboard.games[].homeTeam")
        away_raw = _require_mapping(raw_game.get("awayTeam"), field="scoreboard.games[].awayTeam")
        status = parse_game_status(
            status_code=raw_game.get("gameStatus"),
            status_text=_optional_str(raw_game.get("gameStatusText")),
        )

        parsed_games.append(
            ParsedScoreboardGame(
                game_id=game_id,
                source_date=source_date,
                home_team=_parse_team(
                    home_raw,
                    field="scoreboard.games[].homeTeam",
                    abbreviation_value=_first_value(home_raw, ("teamTricode", "teamAbbreviation")),
                    abbreviation_error_field="scoreboard.games[].homeTeam.abbreviation",
                    score_value=home_raw.get("score"),
                ),
                away_team=_parse_team(
                    away_raw,
                    field="scoreboard.games[].awayTeam",
                    abbreviation_value=_first_value(away_raw, ("teamTricode", "teamAbbreviation")),
                    abbreviation_error_field="scoreboard.games[].awayTeam.abbreviation",
                    score_value=away_raw.get("score"),
                ),
                status=status,
            )
        )
    return parsed_games


def _parse_scoreboard_v2_payload(
    payload: Mapping[str, object],
    *,
    expected_date: date,
) -> list[ParsedScoreboardGame]:
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

    parsed_games: list[ParsedScoreboardGame] = []
    for row in game_headers:
        game_id = _require_str(row.get("GAME_ID"), field="resultSets.GameHeader.GAME_ID")
        source_date = _parse_date_field(
            row.get("GAME_DATE_EST"),
            field="resultSets.GameHeader.GAME_DATE_EST",
            fallback=expected_date,
        )
        home_team_id = _require_str(
            row.get("HOME_TEAM_ID"), field="resultSets.GameHeader.HOME_TEAM_ID"
        )
        away_team_id = _require_str(
            row.get("VISITOR_TEAM_ID"),
            field="resultSets.GameHeader.VISITOR_TEAM_ID",
        )
        home_abbrev = tricode_by_game_and_team.get((game_id, home_team_id), "UNK")
        away_abbrev = tricode_by_game_and_team.get((game_id, away_team_id), "UNK")
        status = parse_game_status(
            status_code=row.get("GAME_STATUS_ID"),
            status_text=_optional_str(row.get("GAME_STATUS_TEXT")),
        )

        parsed_games.append(
            ParsedScoreboardGame(
                game_id=game_id,
                source_date=source_date,
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
                status=status,
            )
        )
    return parsed_games


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
                raise ValueError(
                    f"Malformed payload: expected list rows in resultSets.{set_name}.rowSet."
                )
            parsed_rows.append(
                dict(zip([str(header) for header in headers], raw_row, strict=False))
            )
        return parsed_rows
    if optional:
        return []
    raise ValueError(f"Malformed payload: missing result set '{set_name}'.")


def parse_nba_game_payload(
    payload: Mapping[str, object],
    *,
    expected_game_id: str,
    source_date_fallback: date | None = None,
) -> NBAGame:
    if "boxScoreTraditional" in payload:
        box = _require_mapping(
            payload.get("boxScoreTraditional"), field="payload['boxScoreTraditional']"
        )
        return _parse_nba_game_v3_payload(
            box,
            expected_game_id=expected_game_id,
            source_date_fallback=source_date_fallback,
        )

    if "resultSets" in payload:
        return _parse_nba_game_v2_payload(
            payload,
            expected_game_id=expected_game_id,
            source_date_fallback=source_date_fallback,
        )

    raise ValueError("Malformed boxscore payload: expected V3 or V2 structure.")


def _parse_nba_game_v3_payload(
    box: Mapping[str, object],
    *,
    expected_game_id: str,
    source_date_fallback: date | None,
) -> NBAGame:
    game_id = _optional_str(box.get("gameId"))
    if not game_id:
        game_meta = box.get("game")
        if isinstance(game_meta, Mapping):
            game_id = _optional_str(game_meta.get("gameId"))
    if not game_id or game_id != expected_game_id:
        raise LookupError(f"Game id '{expected_game_id}' not found in boxscore payload.")

    source_date = _parse_date_field(
        box.get("gameDate") or box.get("gameDateEst"),
        field="boxScoreTraditional.gameDate",
        fallback=source_date_fallback,
    )
    home_raw = _require_mapping(box.get("homeTeam"), field="boxScoreTraditional.homeTeam")
    away_raw = _require_mapping(box.get("awayTeam"), field="boxScoreTraditional.awayTeam")

    home_team = _parse_team(
        home_raw,
        field="boxScoreTraditional.homeTeam",
        abbreviation_value=home_raw.get("teamTricode") or home_raw.get("teamAbbreviation"),
        abbreviation_error_field="boxScoreTraditional.homeTeam.teamTricode",
        score_value=_v3_boxscore_team_score(home_raw),
    )
    away_team = _parse_team(
        away_raw,
        field="boxScoreTraditional.awayTeam",
        abbreviation_value=away_raw.get("teamTricode") or away_raw.get("teamAbbreviation"),
        abbreviation_error_field="boxScoreTraditional.awayTeam.teamTricode",
        score_value=_v3_boxscore_team_score(away_raw),
    )

    flat_player_rows_raw = box.get("playersStats") or box.get("playerStats")
    if flat_player_rows_raw is None:
        player_lines = _parse_v3_nested_player_rows(
            home_raw, team=home_team, field="boxScoreTraditional.homeTeam.players"
        ) + _parse_v3_nested_player_rows(
            away_raw, team=away_team, field="boxScoreTraditional.awayTeam.players"
        )
    else:
        player_lines = _parse_player_rows(
            _require_list(flat_player_rows_raw, field="boxScoreTraditional.playersStats"),
            field="boxScoreTraditional.playersStats",
        )
    _require_eligible_player_lines(player_lines, field="boxScoreTraditional")
    return NBAGame(
        game_id=game_id,
        source_date=source_date,
        home_team=home_team,
        away_team=away_team,
        player_lines=tuple(player_lines),
    )


def _parse_nba_game_v2_payload(
    payload: Mapping[str, object],
    *,
    expected_game_id: str,
    source_date_fallback: date | None,
) -> NBAGame:
    result_sets = _require_list(payload.get("resultSets"), field="payload['resultSets']")
    game_headers = _parse_v2_result_set(result_sets, set_name="GameSummary", optional=True)
    team_rows = _parse_v2_result_set(result_sets, set_name="TeamStats")
    player_rows = _parse_v2_result_set(result_sets, set_name="PlayerStats")

    target_header = _find_v2_game_summary(game_headers, expected_game_id=expected_game_id)
    source_date = _parse_v2_source_date(target_header, source_date_fallback=source_date_fallback)
    home_team_id = (
        _optional_str(target_header.get("HOME_TEAM_ID")) if target_header is not None else None
    )
    away_team_id = (
        _optional_str(target_header.get("VISITOR_TEAM_ID")) if target_header is not None else None
    )

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
            name=_optional_str(row.get("TEAM_NAME"))
            or _require_str(
                row.get("TEAM_ABBREVIATION"),
                field="TeamStats.TEAM_ABBREVIATION",
            ),
            abbreviation=_require_str(
                row.get("TEAM_ABBREVIATION"), field="TeamStats.TEAM_ABBREVIATION"
            ),
            score=_optional_int(row.get("PTS")),
        )

    home_team, away_team = _resolve_v2_teams(
        teams_by_id=teams_by_id,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
    )
    if home_team is None or away_team is None:
        raise ValueError(
            "Malformed boxscore payload: missing TeamStats rows for home or away team."
        )

    player_lines = _parse_player_rows(
        [
            row
            for row in player_rows
            if (_optional_str(row.get("GAME_ID")) or expected_game_id) == expected_game_id
        ],
        field="PlayerStats",
    )
    _require_eligible_player_lines(player_lines, field="PlayerStats")
    return NBAGame(
        game_id=expected_game_id,
        source_date=source_date,
        home_team=home_team,
        away_team=away_team,
        player_lines=tuple(player_lines),
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


def _parse_v2_source_date(
    target_header: Mapping[str, object] | None,
    *,
    source_date_fallback: date | None,
) -> date:
    if target_header is None:
        if source_date_fallback is None:
            raise ValueError("Malformed boxscore payload: missing GameSummary and date fallback.")
        return source_date_fallback
    return _parse_date_field(
        target_header.get("GAME_DATE_EST"),
        field="GameSummary.GAME_DATE_EST",
        fallback=source_date_fallback,
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
    abbreviation_value: object,
    abbreviation_error_field: str,
    score_value: object,
) -> TeamGameInfo:
    team_id = _require_str(payload.get("teamId"), field=f"{field}.teamId")
    abbreviation = _require_str(abbreviation_value, field=abbreviation_error_field)
    name = _optional_str(payload.get("teamName")) or abbreviation
    score = _optional_int(score_value)
    return TeamGameInfo(team_id=team_id, name=name, abbreviation=abbreviation, score=score)


def _v3_boxscore_team_score(payload: Mapping[str, object]) -> object:
    score = payload.get("score")
    if score is not None:
        return score
    statistics = payload.get("statistics")
    if isinstance(statistics, Mapping):
        return statistics.get("points")
    return None


def _parse_v3_nested_player_rows(
    team_payload: Mapping[str, object],
    *,
    team: TeamGameInfo,
    field: str,
) -> list[PlayerLine]:
    raw_player_rows = _require_list(team_payload.get("players"), field=field)
    flattened_player_rows: list[Mapping[str, object]] = []
    for raw_player_row in raw_player_rows:
        if not isinstance(raw_player_row, Mapping):
            raise ValueError(f"Malformed payload: expected mapping rows for {field}.")
        statistics = raw_player_row.get("statistics")
        stats = statistics if isinstance(statistics, Mapping) else {}
        flattened_player_rows.append({**raw_player_row, **stats})
    return _parse_player_rows(flattened_player_rows, field=field, team=team)


def _parse_player_rows(
    rows: Sequence[object],
    *,
    field: str,
    team: TeamGameInfo | None = None,
) -> list[PlayerLine]:
    player_lines: list[PlayerLine] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError(f"Malformed payload: expected mapping rows for {field}.")
        player_id = _optional_str(row.get("personId") or row.get("PLAYER_ID"))
        if not player_id:
            continue

        player_name = _parse_player_name(row)
        if not player_name:
            raise ValueError(f"Malformed payload: missing player name in {field}.")

        team_id = _optional_str(row.get("teamId") or row.get("TEAM_ID")) or (
            team.team_id if team else None
        )
        team_abbreviation = _optional_str(
            row.get("teamTricode") or row.get("teamAbbreviation") or row.get("TEAM_ABBREVIATION")
        ) or (team.abbreviation if team else None)
        points = _int_or_zero(row.get("points") if "points" in row else row.get("PTS"))
        minutes = _parse_minutes(row.get("minutes") if "minutes" in row else row.get("MIN"))

        player_lines.append(
            PlayerLine(
                player_id=player_id,
                player_name=player_name,
                team_id=_require_str(team_id, field=f"{field}.teamId"),
                team_abbreviation=_require_str(
                    team_abbreviation, field=f"{field}.teamAbbreviation"
                ),
                points=points,
                minutes=minutes,
            )
        )
    return player_lines


def _parse_player_name(row: Mapping[str, object]) -> str | None:
    explicit_name = _optional_str(
        row.get("name") or row.get("playerName") or row.get("PLAYER_NAME")
    )
    if explicit_name:
        return explicit_name
    first_name = _optional_str(row.get("firstName"))
    family_name = _optional_str(row.get("familyName"))
    if first_name and family_name:
        return f"{first_name} {family_name}"
    return first_name or family_name or _optional_str(row.get("nameI"))


def _require_eligible_player_lines(player_lines: Sequence[PlayerLine], *, field: str) -> None:
    if any(player_line.is_eligible for player_line in player_lines):
        return
    raise LookupError(f"Boxscore stats are unavailable in {field}.")


def parse_game_status(*, status_code: object, status_text: str | None) -> NBAGameStatus | None:
    """Classify an NBA game's status as final, live, or scheduled.

    Both supported scoreboard payload shapes (V3's ``gameStatus`` and V2's
    ``GAME_STATUS_ID``) reliably provide a numeric status code, so that code
    is authoritative whenever it is present. Status text is only consulted
    as a fallback for detecting "final" when no numeric code is given —
    text alone cannot reliably distinguish "live" from "scheduled", so any
    other non-empty text is classified conservatively as live (excluded from
    Playable NBA Games either way).

    Returns ``None`` only when the payload carries no status information at
    all, so that historical behavior (treat as final) can be preserved by
    the caller. A status code or text that is present but unrecognized is
    classified conservatively as live, so games with statuses this parser
    does not understand are never treated as playable.
    """
    if status_code is not None:
        try:
            numeric_code = int(status_code)
        except (TypeError, ValueError):
            numeric_code = None
        else:
            mapped_status = _STATUS_BY_NUMERIC_CODE.get(numeric_code)
            if mapped_status is not None:
                return mapped_status

    lowered = (status_text or "").strip().lower()
    if lowered:
        return NBAGameStatus.FINAL if "final" in lowered else NBAGameStatus.LIVE
    return None if status_code is None else NBAGameStatus.LIVE


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
