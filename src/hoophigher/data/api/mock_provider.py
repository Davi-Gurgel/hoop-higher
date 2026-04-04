from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

from hoophigher.data.api.base import StatsProvider
from hoophigher.domain.models import GameBoxScore, PlayerLine, TeamGameInfo


@dataclass(frozen=True, slots=True)
class _MockDataset:
    games_by_date: dict[date, tuple[GameBoxScore, ...]]
    games_by_id: dict[str, GameBoxScore]


def _make_player(game_id: str, index: int, points: int, minutes: int = 24) -> PlayerLine:
    return PlayerLine(
        player_id=f"{game_id}-p{index}",
        player_name=f"{game_id.upper()} Player {index}",
        team_id=f"{game_id}-team-{index % 2}",
        team_abbreviation=f"T{index % 2}",
        points=points,
        minutes=minutes,
    )


def _make_game(
    *,
    game_id: str,
    game_date: date,
    home_abbreviation: str,
    away_abbreviation: str,
    home_score: int,
    away_score: int,
    player_points: Sequence[int],
) -> GameBoxScore:
    players = tuple(
        _make_player(game_id, index, points) for index, points in enumerate(player_points, start=1)
    )
    return GameBoxScore(
        game_id=game_id,
        game_date=game_date,
        home_team=TeamGameInfo(
            team_id=f"{game_id}-home",
            name=f"{home_abbreviation} Home",
            abbreviation=home_abbreviation,
            score=home_score,
        ),
        away_team=TeamGameInfo(
            team_id=f"{game_id}-away",
            name=f"{away_abbreviation} Away",
            abbreviation=away_abbreviation,
            score=away_score,
        ),
        player_lines=players,
    )


def _build_default_dataset() -> _MockDataset:
    january_12 = date(2025, 1, 12)
    january_13 = date(2025, 1, 13)

    games = (
        _make_game(
            game_id="2025-01-12-lal-bos",
            game_date=january_12,
            home_abbreviation="LAL",
            away_abbreviation="BOS",
            home_score=118,
            away_score=112,
            player_points=(31, 24, 19, 15, 9, 4),
        ),
        _make_game(
            game_id="2025-01-12-den-dal",
            game_date=january_12,
            home_abbreviation="DEN",
            away_abbreviation="DAL",
            home_score=109,
            away_score=105,
            player_points=(28, 21, 17, 13, 8, 2),
        ),
        _make_game(
            game_id="2025-01-12-nyk-mia",
            game_date=january_12,
            home_abbreviation="NYK",
            away_abbreviation="MIA",
            home_score=103,
            away_score=99,
            player_points=(26, 20, 14, 11, 7, 3),
        ),
        _make_game(
            game_id="2025-01-12-sas-phi",
            game_date=january_12,
            home_abbreviation="SAS",
            away_abbreviation="PHI",
            home_score=121,
            away_score=116,
            player_points=(33, 29, 18, 12, 10, 5),
        ),
        _make_game(
            game_id="2025-01-12-phx-gsw",
            game_date=january_12,
            home_abbreviation="PHX",
            away_abbreviation="GSW",
            home_score=115,
            away_score=110,
            player_points=(30, 23, 16, 14, 6, 1),
        ),
        _make_game(
            game_id="2025-01-13-min-okc",
            game_date=january_13,
            home_abbreviation="MIN",
            away_abbreviation="OKC",
            home_score=107,
            away_score=104,
            player_points=(29, 25, 18, 15, 9, 4),
        ),
        _make_game(
            game_id="2025-01-13-hou-sac",
            game_date=january_13,
            home_abbreviation="HOU",
            away_abbreviation="SAC",
            home_score=111,
            away_score=108,
            player_points=(27, 22, 17, 13, 8, 2),
        ),
    )

    games_by_date: dict[date, list[GameBoxScore]] = {}
    games_by_id: dict[str, GameBoxScore] = {}
    for game in games:
        games_by_date.setdefault(game.game_date, []).append(game)
        games_by_id[game.game_id] = game

    return _MockDataset(
        games_by_date={
            game_date: tuple(sorted(games_for_date, key=lambda game: game.game_id))
            for game_date, games_for_date in games_by_date.items()
        },
        games_by_id=games_by_id,
    )


class MockProvider(StatsProvider):
    def __init__(
        self,
        *,
        dataset: _MockDataset | None = None,
    ) -> None:
        self._dataset = dataset or _build_default_dataset()

    async def get_games_by_date(self, game_date: date) -> list[GameBoxScore]:
        return list(self._dataset.games_by_date.get(game_date, ()))

    async def get_game_boxscore(self, game_id: str) -> GameBoxScore:
        try:
            return self._dataset.games_by_id[game_id]
        except KeyError as exc:
            raise LookupError(f"Mock game not found: {game_id}") from exc
