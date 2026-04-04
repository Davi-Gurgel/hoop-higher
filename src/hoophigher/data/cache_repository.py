from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date

from sqlmodel import Session

from hoophigher.data.schema import CachedGameRecord, CachedGameStatsRecord
from hoophigher.domain.models import GameBoxScore, PlayerLine, TeamGameInfo


class CacheRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_games_by_date(self, game_date: date) -> list[GameBoxScore] | None:
        record = self.session.get(CachedGameRecord, game_date)
        if record is None:
            return None
        return _deserialize_game_list(record.payload_json)

    def set_games_by_date(self, game_date: date, games: Sequence[GameBoxScore]) -> CachedGameRecord:
        record = CachedGameRecord(game_date=game_date, payload_json=_serialize_game_list(games))
        record = self.session.merge(record)
        self.session.flush()
        self.session.refresh(record)
        return record

    def get_game_boxscore(self, game_id: str) -> GameBoxScore | None:
        record = self.session.get(CachedGameStatsRecord, game_id)
        if record is None:
            return None
        return _deserialize_game_boxscore(record.payload_json)

    def set_game_boxscore(self, game: GameBoxScore) -> CachedGameStatsRecord:
        record = CachedGameStatsRecord(game_id=game.game_id, payload_json=_serialize_game_boxscore(game))
        record = self.session.merge(record)
        self.session.flush()
        self.session.refresh(record)
        return record


def _serialize_game_list(games: Sequence[GameBoxScore]) -> str:
    return json.dumps([_game_boxscore_to_dict(game) for game in games], separators=(",", ":"))


def _deserialize_game_list(payload_json: str) -> list[GameBoxScore]:
    payload = json.loads(payload_json)
    return [_game_boxscore_from_dict(item) for item in payload]


def _serialize_game_boxscore(game: GameBoxScore) -> str:
    return json.dumps(_game_boxscore_to_dict(game), separators=(",", ":"))


def _deserialize_game_boxscore(payload_json: str) -> GameBoxScore:
    payload = json.loads(payload_json)
    return _game_boxscore_from_dict(payload)


def _game_boxscore_to_dict(game: GameBoxScore) -> dict[str, object]:
    return {
        "game_id": game.game_id,
        "game_date": game.game_date.isoformat(),
        "home_team": _team_to_dict(game.home_team),
        "away_team": _team_to_dict(game.away_team),
        "player_lines": [_player_line_to_dict(player) for player in game.player_lines],
    }


def _game_boxscore_from_dict(payload: dict[str, object]) -> GameBoxScore:
    return GameBoxScore(
        game_id=str(payload["game_id"]),
        game_date=date.fromisoformat(str(payload["game_date"])),
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
