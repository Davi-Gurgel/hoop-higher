from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

from hoophigher.data.api.base import StatsSource
from hoophigher.domain.models import NBAGame, PlayerLine, TeamGameInfo

_MOCK_PLAYER_NAMES = (
    "Jalen Hart",
    "Marcus Reed",
    "Tyrese Cole",
    "Devin Brooks",
    "Malik Hayes",
    "Isaiah Price",
    "Noah Foster",
    "Miles Bell",
    "Andre Lewis",
    "Caleb Shaw",
    "Jordan Wells",
    "Avery Scott",
)


@dataclass(frozen=True, slots=True)
class _MockDataset:
    games_by_date: dict[date, tuple[NBAGame, ...]]
    games_by_id: dict[str, NBAGame]


def _player_name_for(game_id: str, index: int) -> str:
    seed = sum(ord(char) for char in game_id)
    return _MOCK_PLAYER_NAMES[(seed + index - 1) % len(_MOCK_PLAYER_NAMES)]


def _make_player(
    *,
    game_id: str,
    index: int,
    points: int,
    team_id: str,
    team_abbreviation: str,
    minutes: int,
) -> PlayerLine:
    return PlayerLine(
        player_id=f"{game_id}-p{index}",
        player_name=_player_name_for(game_id, index),
        team_id=team_id,
        team_abbreviation=team_abbreviation,
        points=points,
        minutes=minutes,
    )


def _make_game(
    *,
    game_id: str,
    source_date: date,
    home_abbreviation: str,
    away_abbreviation: str,
    home_score: int,
    away_score: int,
    player_points: Sequence[int],
) -> NBAGame:
    home_team_id = f"{game_id}-home"
    away_team_id = f"{game_id}-away"
    split_index = len(player_points) // 2
    players = []
    for index, points in enumerate(player_points, start=1):
        is_away_player = index <= split_index
        team_id = away_team_id if is_away_player else home_team_id
        team_abbreviation = away_abbreviation if is_away_player else home_abbreviation
        players.append(
            _make_player(
                game_id=game_id,
                index=index,
                points=points,
                team_id=team_id,
                team_abbreviation=team_abbreviation,
                minutes=max(18, 36 - (index * 2)),
            )
        )
    return NBAGame(
        game_id=game_id,
        source_date=source_date,
        home_team=TeamGameInfo(
            team_id=home_team_id,
            name=f"{home_abbreviation} Home",
            abbreviation=home_abbreviation,
            score=home_score,
        ),
        away_team=TeamGameInfo(
            team_id=away_team_id,
            name=f"{away_abbreviation} Away",
            abbreviation=away_abbreviation,
            score=away_score,
        ),
        player_lines=tuple(players),
    )


def _build_default_dataset() -> _MockDataset:
    january_12 = date(2025, 1, 12)
    january_13 = date(2025, 1, 13)

    games = (
        _make_game(
            game_id="2025-01-12-lal-bos",
            source_date=january_12,
            home_abbreviation="LAL",
            away_abbreviation="BOS",
            home_score=118,
            away_score=112,
            player_points=(31, 24, 19, 15, 12, 9, 7, 4, 3, 1),
        ),
        _make_game(
            game_id="2025-01-12-den-dal",
            source_date=january_12,
            home_abbreviation="DEN",
            away_abbreviation="DAL",
            home_score=109,
            away_score=105,
            player_points=(28, 21, 17, 13, 11, 8, 6, 4, 2, 1),
        ),
        _make_game(
            game_id="2025-01-12-nyk-mia",
            source_date=january_12,
            home_abbreviation="NYK",
            away_abbreviation="MIA",
            home_score=103,
            away_score=99,
            player_points=(26, 20, 16, 14, 11, 7, 5, 3, 2, 1),
        ),
        _make_game(
            game_id="2025-01-12-sas-phi",
            source_date=january_12,
            home_abbreviation="SAS",
            away_abbreviation="PHI",
            home_score=121,
            away_score=116,
            player_points=(33, 29, 21, 18, 12, 10, 8, 5, 3, 2),
        ),
        _make_game(
            game_id="2025-01-12-phx-gsw",
            source_date=january_12,
            home_abbreviation="PHX",
            away_abbreviation="GSW",
            home_score=115,
            away_score=110,
            player_points=(30, 23, 18, 16, 14, 9, 6, 4, 2, 1),
        ),
        _make_game(
            game_id="2025-01-13-min-okc",
            source_date=january_13,
            home_abbreviation="MIN",
            away_abbreviation="OKC",
            home_score=107,
            away_score=104,
            player_points=(29, 25, 20, 18, 15, 9, 7, 4, 2, 1),
        ),
        _make_game(
            game_id="2025-01-13-hou-sac",
            source_date=january_13,
            home_abbreviation="HOU",
            away_abbreviation="SAC",
            home_score=111,
            away_score=108,
            player_points=(27, 22, 19, 17, 13, 8, 6, 4, 2, 1),
        ),
    )

    games_by_date: dict[date, list[NBAGame]] = {}
    games_by_id: dict[str, NBAGame] = {}
    for game in games:
        games_by_date.setdefault(game.source_date, []).append(game)
        games_by_id[game.game_id] = game

    return _MockDataset(
        games_by_date={
            source_date: tuple(sorted(games_for_date, key=lambda game: game.game_id))
            for source_date, games_for_date in games_by_date.items()
        },
        games_by_id=games_by_id,
    )


class MockStatsSource(StatsSource):
    def __init__(
        self,
        *,
        dataset: _MockDataset | None = None,
    ) -> None:
        self._dataset = dataset or _build_default_dataset()

    async def get_games_by_date(self, source_date: date) -> list[NBAGame]:
        return list(self._dataset.games_by_date.get(source_date, ()))

    async def get_nba_game(
        self,
        game_id: str,
        *,
        source_date_fallback: date | None = None,
    ) -> NBAGame:
        try:
            return self._dataset.games_by_id[game_id]
        except KeyError as exc:
            raise LookupError(f"Mock game not found: {game_id}") from exc
