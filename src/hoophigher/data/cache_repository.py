from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date

from sqlmodel import Session

from hoophigher.data.schema import CachedGameRecord, CachedGameStatsRecord
from hoophigher.domain.models import NBAGame, PlayerLine, TeamGameInfo


class CacheRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_games_by_date(self, source_date: date) -> list[NBAGame] | None:
        record = self.session.get(CachedGameRecord, source_date)
        if record is None:
            return None
        return _deserialize_game_list(record.payload_json)

    def set_games_by_date(self, source_date: date, games: Sequence[NBAGame]) -> CachedGameRecord:
        # NOTE: CachedGameRecord.game_date is the persisted column name; kept as-is so
        # existing cached rows continue to load unchanged. Only the Python-facing
        # attribute name (NBAGame.source_date) follows the glossary.
        record = CachedGameRecord(game_date=source_date, payload_json=_serialize_game_list(games))
        record = self.session.merge(record)
        self.session.flush()
        self.session.refresh(record)
        return record

    def get_nba_game(self, game_id: str) -> NBAGame | None:
        record = self.session.get(CachedGameStatsRecord, game_id)
        if record is None:
            return None
        return _deserialize_nba_game(record.payload_json)

    def set_nba_game(self, game: NBAGame) -> CachedGameStatsRecord:
        record = CachedGameStatsRecord(game_id=game.game_id, payload_json=_serialize_nba_game(game))
        record = self.session.merge(record)
        self.session.flush()
        self.session.refresh(record)
        return record


# Version 2 payloads mark the cached day as complete with final games only.
# Version 1 payloads (a bare JSON list) predate final-game filtering and may
# contain live or scheduled games, so they cannot be trusted as complete.
_GAME_LIST_PAYLOAD_VERSION = 2


def _serialize_game_list(games: Sequence[NBAGame]) -> str:
    payload = {
        "version": _GAME_LIST_PAYLOAD_VERSION,
        "games": [_nba_game_to_dict(game) for game in games],
    }
    return json.dumps(payload, separators=(",", ":"))


def _deserialize_game_list(payload_json: str) -> list[NBAGame] | None:
    payload = json.loads(payload_json)
    if not isinstance(payload, dict) or payload.get("version") != _GAME_LIST_PAYLOAD_VERSION:
        return None
    return [_nba_game_from_dict(item) for item in payload["games"]]


def _serialize_nba_game(game: NBAGame) -> str:
    return json.dumps(_nba_game_to_dict(game), separators=(",", ":"))


def _deserialize_nba_game(payload_json: str) -> NBAGame:
    payload = json.loads(payload_json)
    return _nba_game_from_dict(payload)


def _nba_game_to_dict(game: NBAGame) -> dict[str, object]:
    # NOTE: the "game_date" key is the persisted cache payload format; kept as-is so
    # existing cached JSON blobs continue to deserialize unchanged.
    return {
        "game_id": game.game_id,
        "game_date": game.source_date.isoformat(),
        "home_team": _team_to_dict(game.home_team),
        "away_team": _team_to_dict(game.away_team),
        "player_lines": [_player_line_to_dict(player) for player in game.player_lines],
    }


def _nba_game_from_dict(payload: dict[str, object]) -> NBAGame:
    return NBAGame(
        game_id=str(payload["game_id"]),
        source_date=date.fromisoformat(str(payload["game_date"])),
        home_team=_team_from_dict(payload["home_team"]),
        away_team=_team_from_dict(payload["away_team"]),
        player_lines=tuple(_player_line_from_dict(player) for player in payload["player_lines"]),
    )


def _team_to_dict(team: TeamGameInfo) -> dict[str, object]:
    return {
        "team_id": team.team_id,
        "name": team.name,
        "abbreviation": team.abbreviation,
        "score": team.score,
    }


def _team_from_dict(payload: object) -> TeamGameInfo:
    data = payload if isinstance(payload, dict) else {}
    return TeamGameInfo(
        team_id=str(data["team_id"]),
        name=str(data["name"]),
        abbreviation=str(data["abbreviation"]),
        score=data.get("score"),
    )


def _player_line_to_dict(player: PlayerLine) -> dict[str, object]:
    return {
        "player_id": player.player_id,
        "player_name": player.player_name,
        "team_id": player.team_id,
        "team_abbreviation": player.team_abbreviation,
        "points": player.points,
        "minutes": player.minutes,
    }


def _player_line_from_dict(payload: object) -> PlayerLine:
    data = payload if isinstance(payload, dict) else {}
    return PlayerLine(
        player_id=str(data["player_id"]),
        player_name=str(data["player_name"]),
        team_id=str(data["team_id"]),
        team_abbreviation=str(data["team_abbreviation"]),
        points=int(data["points"]),
        minutes=int(data["minutes"]),
    )
