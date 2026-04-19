import asyncio
import types
import sys
from contextlib import contextmanager
from datetime import date

import pytest

from hoophigher.data import CacheRepository, create_sqlite_engine, init_db, session_scope
from hoophigher.data.api.nba_api_provider import NBAApiProvider, _default_boxscore_fetch, _default_scoreboard_fetch
from hoophigher.domain.models import GameBoxScore, PlayerLine, TeamGameInfo


def _make_game(game_id: str, game_date: date) -> GameBoxScore:
    return GameBoxScore(
        game_id=game_id,
        game_date=game_date,
        home_team=TeamGameInfo(team_id="1610612737", name="Hawks", abbreviation="ATL", score=110),
        away_team=TeamGameInfo(team_id="1610612738", name="Celtics", abbreviation="BOS", score=108),
        player_lines=(
            PlayerLine(
                player_id=f"{game_id}-1",
                player_name="Player One",
                team_id="1610612737",
                team_abbreviation="ATL",
                points=20,
                minutes=30,
            ),
        ),
    )


def _make_cache_factory(engine):
    @contextmanager
    def factory():
        with session_scope(engine) as session:
            yield CacheRepository(session)

    return factory


def test_get_games_by_date_uses_cache_before_fetchers(tmp_path) -> None:
    target_date = date(2025, 2, 10)
    cached_game = _make_game("0022500001", target_date)
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)
    with session_scope(engine) as session:
        CacheRepository(session).set_games_by_date(target_date, [cached_game])

    scoreboard_calls = 0
    boxscore_calls = 0

    def scoreboard_fetch(_game_date: date, _timeout_seconds: int):
        nonlocal scoreboard_calls
        scoreboard_calls += 1
        return {}

    def boxscore_fetch(_game_id: str, _timeout_seconds: int):
        nonlocal boxscore_calls
        boxscore_calls += 1
        return {}

    provider = NBAApiProvider(
        cache_repository_factory=_make_cache_factory(engine),
        scoreboard_fetch=scoreboard_fetch,
        boxscore_fetch=boxscore_fetch,
        timeout_seconds=5,
    )

    games = asyncio.run(provider.get_games_by_date(target_date))

    assert games == [cached_game]
    assert scoreboard_calls == 0
    assert boxscore_calls == 0


def test_get_game_boxscore_caches_miss_then_hits_cache(tmp_path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)
    calls = 0

    def boxscore_fetch(game_id: str, _timeout_seconds: int):
        nonlocal calls
        calls += 1
        return {
            "boxScoreTraditional": {
                "gameId": game_id,
                "gameDate": "2025-02-10",
                "homeTeam": {
                    "teamId": "1610612737",
                    "teamName": "Hawks",
                    "teamTricode": "ATL",
                    "score": "110",
                },
                "awayTeam": {
                    "teamId": "1610612738",
                    "teamName": "Celtics",
                    "teamTricode": "BOS",
                    "score": "108",
                },
                "playersStats": [
                    {
                        "personId": "1",
                        "name": "Player One",
                        "teamId": "1610612737",
                        "teamTricode": "ATL",
                        "minutes": "12:34",
                        "points": "22",
                    }
                ],
            }
        }

    provider = NBAApiProvider(
        cache_repository_factory=_make_cache_factory(engine),
        boxscore_fetch=boxscore_fetch,
        timeout_seconds=5,
    )

    first = asyncio.run(provider.get_game_boxscore("0022500002"))
    second = asyncio.run(provider.get_game_boxscore("0022500002"))

    assert calls == 1
    assert first == second
    assert first.player_lines[0].minutes == 12


def test_get_games_by_date_caches_date_list_after_fetch(tmp_path) -> None:
    target_date = date(2025, 2, 10)
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)
    scoreboard_calls = 0
    boxscore_calls = 0

    def scoreboard_fetch(game_date: date, _timeout_seconds: int):
        nonlocal scoreboard_calls
        scoreboard_calls += 1
        return {
            "scoreboard": {
                "games": [
                    {
                        "gameId": "0022500003",
                        "gameDate": game_date.isoformat(),
                        "homeTeam": {
                            "teamId": "1610612737",
                            "teamName": "Hawks",
                            "teamTricode": "ATL",
                            "score": "115",
                        },
                        "awayTeam": {
                            "teamId": "1610612738",
                            "teamName": "Celtics",
                            "teamTricode": "BOS",
                            "score": "114",
                        },
                    }
                ]
            }
        }

    def boxscore_fetch(game_id: str, _timeout_seconds: int):
        nonlocal boxscore_calls
        boxscore_calls += 1
        return {
            "boxScoreTraditional": {
                "gameId": game_id,
                "gameDate": "2025-02-10",
                "homeTeam": {
                    "teamId": "1610612737",
                    "teamName": "Hawks",
                    "teamTricode": "ATL",
                    "score": "115",
                },
                "awayTeam": {
                    "teamId": "1610612738",
                    "teamName": "Celtics",
                    "teamTricode": "BOS",
                    "score": "114",
                },
                "playersStats": [
                    {
                        "personId": "2",
                        "name": "Player Two",
                        "teamId": "1610612737",
                        "teamTricode": "ATL",
                        "minutes": "34:11",
                        "points": "31",
                    }
                ],
            }
        }

    provider = NBAApiProvider(
        cache_repository_factory=_make_cache_factory(engine),
        scoreboard_fetch=scoreboard_fetch,
        boxscore_fetch=boxscore_fetch,
        timeout_seconds=5,
    )

    first = asyncio.run(provider.get_games_by_date(target_date))
    second = asyncio.run(provider.get_games_by_date(target_date))

    assert len(first) == 1
    assert first == second
    assert scoreboard_calls == 1
    assert boxscore_calls == 1

    with session_scope(engine) as session:
        cached = CacheRepository(session).get_games_by_date(target_date)
    assert cached == first


def test_mapping_parses_minutes_and_skips_blank_player_ids(tmp_path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)

    def boxscore_fetch(game_id: str, _timeout_seconds: int):
        return {
            "boxScoreTraditional": {
                "gameId": game_id,
                "gameDate": "2025-02-10",
                "homeTeam": {
                    "teamId": "1610612737",
                    "teamName": "Hawks",
                    "teamTricode": "ATL",
                    "score": "111",
                },
                "awayTeam": {
                    "teamId": "1610612738",
                    "teamName": "Celtics",
                    "teamTricode": "BOS",
                    "score": "109",
                },
                "playersStats": [
                    {
                        "personId": "11",
                        "name": "A",
                        "teamId": "1610612737",
                        "teamTricode": "ATL",
                        "minutes": "12:34",
                        "points": "17",
                    },
                    {
                        "personId": "12",
                        "name": "B",
                        "teamId": "1610612738",
                        "teamTricode": "BOS",
                        "minutes": "",
                        "points": None,
                    },
                    {
                        "personId": " ",
                        "name": "C",
                        "teamId": "1610612738",
                        "teamTricode": "BOS",
                        "minutes": "09:00",
                        "points": "8",
                    },
                ],
            }
        }

    provider = NBAApiProvider(
        cache_repository_factory=_make_cache_factory(engine),
        boxscore_fetch=boxscore_fetch,
        timeout_seconds=5,
    )

    game = asyncio.run(provider.get_game_boxscore("0022500004"))

    assert len(game.player_lines) == 2
    assert [player.minutes for player in game.player_lines] == [12, 0]
    assert [player.points for player in game.player_lines] == [17, 0]


def test_get_games_by_date_parses_nested_v3_boxscore_shape(tmp_path) -> None:
    target_date = date(2025, 2, 10)
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)

    def scoreboard_fetch(game_date: date, _timeout_seconds: int):
        return {
            "scoreboard": {
                "games": [
                    {
                        "gameId": "0022500104",
                        "gameDate": game_date.isoformat(),
                        "homeTeam": {
                            "teamId": "1610612737",
                            "teamName": "Hawks",
                            "teamTricode": "ATL",
                            "score": "111",
                        },
                        "awayTeam": {
                            "teamId": "1610612738",
                            "teamName": "Celtics",
                            "teamTricode": "BOS",
                            "score": "109",
                        },
                    }
                ]
            }
        }

    def boxscore_fetch(game_id: str, _timeout_seconds: int):
        return {
            "boxScoreTraditional": {
                "gameId": game_id,
                "homeTeam": {
                    "teamId": "1610612737",
                    "teamName": "Hawks",
                    "teamTricode": "ATL",
                    "statistics": {"points": "111"},
                    "players": [
                        {
                            "personId": "11",
                            "firstName": "Player",
                            "familyName": "One",
                            "statistics": {
                                "minutes": "PT12M34.00S",
                                "points": "17",
                            },
                        }
                    ],
                },
                "awayTeam": {
                    "teamId": "1610612738",
                    "teamName": "Celtics",
                    "teamTricode": "BOS",
                    "statistics": {"points": "109"},
                    "players": [
                        {
                            "personId": "12",
                            "firstName": "Player",
                            "familyName": "Two",
                            "statistics": {
                                "minutes": "PT09M00.00S",
                                "points": "8",
                            },
                        }
                    ],
                },
            }
        }

    provider = NBAApiProvider(
        cache_repository_factory=_make_cache_factory(engine),
        scoreboard_fetch=scoreboard_fetch,
        boxscore_fetch=boxscore_fetch,
        timeout_seconds=5,
    )

    games = asyncio.run(provider.get_games_by_date(target_date))

    assert len(games) == 1
    game = games[0]
    assert game.game_date == target_date
    assert game.home_team.score == 111
    assert game.away_team.score == 109
    assert [(player.player_name, player.team_abbreviation, player.minutes, player.points) for player in game.player_lines] == [
        ("Player One", "ATL", 12, 17),
        ("Player Two", "BOS", 9, 8),
    ]


def test_get_games_by_date_parses_v2_boxscore_without_game_summary(tmp_path) -> None:
    target_date = date(2025, 2, 10)
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)

    def scoreboard_fetch(game_date: date, _timeout_seconds: int):
        return {
            "scoreboard": {
                "games": [
                    {
                        "gameId": "0022500105",
                        "gameDate": game_date.isoformat(),
                        "homeTeam": {
                            "teamId": "1610612737",
                            "teamName": "Hawks",
                            "teamTricode": "ATL",
                            "score": "111",
                        },
                        "awayTeam": {
                            "teamId": "1610612738",
                            "teamName": "Celtics",
                            "teamTricode": "BOS",
                            "score": "109",
                        },
                    }
                ]
            }
        }

    def boxscore_fetch(game_id: str, _timeout_seconds: int):
        return {
            "resultSets": [
                {
                    "name": "PlayerStats",
                    "headers": [
                        "GAME_ID",
                        "TEAM_ID",
                        "TEAM_ABBREVIATION",
                        "PLAYER_ID",
                        "PLAYER_NAME",
                        "MIN",
                        "PTS",
                    ],
                    "rowSet": [
                        [game_id, "1610612737", "ATL", "11", "Player One", "12:34", 17],
                        [game_id, "1610612738", "BOS", "12", "Player Two", "9:00", 8],
                    ],
                },
                {
                    "name": "TeamStats",
                    "headers": ["GAME_ID", "TEAM_ID", "TEAM_NAME", "TEAM_ABBREVIATION", "PTS"],
                    "rowSet": [
                        [game_id, "1610612737", "Hawks", "ATL", 111],
                        [game_id, "1610612738", "Celtics", "BOS", 109],
                    ],
                },
            ]
        }

    provider = NBAApiProvider(
        cache_repository_factory=_make_cache_factory(engine),
        scoreboard_fetch=scoreboard_fetch,
        boxscore_fetch=boxscore_fetch,
        timeout_seconds=5,
    )

    games = asyncio.run(provider.get_games_by_date(target_date))

    assert len(games) == 1
    game = games[0]
    assert game.game_date == target_date
    assert game.home_team.abbreviation == "ATL"
    assert game.away_team.abbreviation == "BOS"
    assert [(player.player_name, player.team_abbreviation, player.minutes, player.points) for player in game.player_lines] == [
        ("Player One", "ATL", 12, 17),
        ("Player Two", "BOS", 9, 8),
    ]


def test_malformed_payload_raises_explicit_error(tmp_path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)

    def malformed_boxscore_fetch(game_id: str, _timeout_seconds: int):
        return {
            "boxScoreTraditional": {
                "gameId": game_id,
                "gameDate": "2025-02-10",
                "awayTeam": {
                    "teamId": "1610612738",
                    "teamName": "Celtics",
                    "teamTricode": "BOS",
                    "score": "108",
                },
                "playersStats": [],
            }
        }

    provider = NBAApiProvider(
        cache_repository_factory=_make_cache_factory(engine),
        boxscore_fetch=malformed_boxscore_fetch,
        timeout_seconds=5,
    )

    with pytest.raises(ValueError, match="Malformed payload"):
        asyncio.run(provider.get_game_boxscore("0022500005"))


def test_get_game_boxscore_retries_transient_fetch_error_then_succeeds(tmp_path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)
    calls = 0

    def flaky_boxscore_fetch(game_id: str, _timeout_seconds: int):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError("temporary upstream failure")
        return {
            "boxScoreTraditional": {
                "gameId": game_id,
                "gameDate": "2025-02-10",
                "homeTeam": {
                    "teamId": "1610612737",
                    "teamName": "Hawks",
                    "teamTricode": "ATL",
                    "score": "111",
                },
                "awayTeam": {
                    "teamId": "1610612738",
                    "teamName": "Celtics",
                    "teamTricode": "BOS",
                    "score": "109",
                },
                "playersStats": [
                    {
                        "personId": "1",
                        "name": "Retry Player",
                        "teamId": "1610612737",
                        "teamTricode": "ATL",
                        "minutes": "10:00",
                        "points": "5",
                    }
                ],
            }
        }

    provider = NBAApiProvider(
        cache_repository_factory=_make_cache_factory(engine),
        boxscore_fetch=flaky_boxscore_fetch,
        timeout_seconds=5,
        max_retries=2,
    )

    game = asyncio.run(provider.get_game_boxscore("0022500101"))

    assert game.game_id == "0022500101"
    assert calls == 3


def test_get_games_by_date_retries_transient_scoreboard_error_then_succeeds(tmp_path) -> None:
    target_date = date(2025, 2, 10)
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)
    scoreboard_calls = 0

    def flaky_scoreboard_fetch(game_date: date, _timeout_seconds: int):
        nonlocal scoreboard_calls
        scoreboard_calls += 1
        if scoreboard_calls < 3:
            raise TimeoutError("scoreboard timeout")
        return {
            "scoreboard": {
                "games": [
                    {
                        "gameId": "0022500102",
                        "gameDate": game_date.isoformat(),
                        "homeTeam": {
                            "teamId": "1610612737",
                            "teamName": "Hawks",
                            "teamTricode": "ATL",
                            "score": "115",
                        },
                        "awayTeam": {
                            "teamId": "1610612738",
                            "teamName": "Celtics",
                            "teamTricode": "BOS",
                            "score": "114",
                        },
                    }
                ]
            }
        }

    def boxscore_fetch(game_id: str, _timeout_seconds: int):
        return {
            "boxScoreTraditional": {
                "gameId": game_id,
                "gameDate": "2025-02-10",
                "homeTeam": {
                    "teamId": "1610612737",
                    "teamName": "Hawks",
                    "teamTricode": "ATL",
                    "score": "115",
                },
                "awayTeam": {
                    "teamId": "1610612738",
                    "teamName": "Celtics",
                    "teamTricode": "BOS",
                    "score": "114",
                },
                "playersStats": [
                    {
                        "personId": "2",
                        "name": "Retry Date Player",
                        "teamId": "1610612737",
                        "teamTricode": "ATL",
                        "minutes": "11:00",
                        "points": "7",
                    }
                ],
            }
        }

    provider = NBAApiProvider(
        cache_repository_factory=_make_cache_factory(engine),
        scoreboard_fetch=flaky_scoreboard_fetch,
        boxscore_fetch=boxscore_fetch,
        timeout_seconds=5,
        max_retries=2,
    )

    games = asyncio.run(provider.get_games_by_date(target_date))

    assert [game.game_id for game in games] == ["0022500102"]
    assert scoreboard_calls == 3


def test_get_games_by_date_raises_lookup_error_when_transient_errors_exhausted(tmp_path) -> None:
    target_date = date(2025, 2, 10)
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)
    calls = 0

    def always_failing_scoreboard_fetch(_game_date: date, _timeout_seconds: int):
        nonlocal calls
        calls += 1
        raise ConnectionError("upstream unavailable")

    provider = NBAApiProvider(
        cache_repository_factory=_make_cache_factory(engine),
        scoreboard_fetch=always_failing_scoreboard_fetch,
        timeout_seconds=5,
        max_retries=2,
    )

    with pytest.raises(LookupError, match="Failed to fetch scoreboard"):
        asyncio.run(provider.get_games_by_date(target_date))

    assert calls == 3


def test_get_game_boxscore_raises_lookup_error_when_transient_errors_exhausted(tmp_path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)
    calls = 0

    def always_failing_boxscore_fetch(_game_id: str, _timeout_seconds: int):
        nonlocal calls
        calls += 1
        raise TimeoutError("boxscore timeout")

    provider = NBAApiProvider(
        cache_repository_factory=_make_cache_factory(engine),
        boxscore_fetch=always_failing_boxscore_fetch,
        timeout_seconds=5,
        max_retries=2,
    )

    with pytest.raises(LookupError, match="Failed to fetch boxscore"):
        asyncio.run(provider.get_game_boxscore("0022500103"))

    assert calls == 3


def test_timeout_seconds_below_one_raises_value_error(tmp_path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)

    with pytest.raises(ValueError, match="at least 1"):
        NBAApiProvider(
            cache_repository_factory=_make_cache_factory(engine),
            timeout_seconds=0,
        )


def test_max_retries_below_zero_raises_value_error(tmp_path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)

    with pytest.raises(ValueError, match="max_retries"):
        NBAApiProvider(
            cache_repository_factory=_make_cache_factory(engine),
            max_retries=-1,
        )


def test_get_game_boxscore_raises_lookup_error_for_missing_expected_game_id(tmp_path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)

    def boxscore_fetch(_game_id: str, _timeout_seconds: int):
        return {
            "boxScoreTraditional": {
                "gameId": "0022509999",
                "gameDate": "2025-02-10",
                "homeTeam": {
                    "teamId": "1610612737",
                    "teamName": "Hawks",
                    "teamTricode": "ATL",
                    "score": "111",
                },
                "awayTeam": {
                    "teamId": "1610612738",
                    "teamName": "Celtics",
                    "teamTricode": "BOS",
                    "score": "109",
                },
                "playersStats": [],
            }
        }

    provider = NBAApiProvider(
        cache_repository_factory=_make_cache_factory(engine),
        boxscore_fetch=boxscore_fetch,
        timeout_seconds=5,
    )

    with pytest.raises(LookupError, match="not found"):
        asyncio.run(provider.get_game_boxscore("0022500006"))


def test_get_games_by_date_returns_games_sorted_by_game_id(tmp_path) -> None:
    target_date = date(2025, 2, 10)
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)

    def scoreboard_fetch(game_date: date, _timeout_seconds: int):
        return {
            "scoreboard": {
                "games": [
                    {
                        "gameId": "0022500009",
                        "gameDate": game_date.isoformat(),
                        "homeTeam": {
                            "teamId": "1610612737",
                            "teamName": "Hawks",
                            "teamTricode": "ATL",
                            "score": "110",
                        },
                        "awayTeam": {
                            "teamId": "1610612738",
                            "teamName": "Celtics",
                            "teamTricode": "BOS",
                            "score": "108",
                        },
                    },
                    {
                        "gameId": "0022500001",
                        "gameDate": game_date.isoformat(),
                        "homeTeam": {
                            "teamId": "1610612739",
                            "teamName": "Cavaliers",
                            "teamTricode": "CLE",
                            "score": "99",
                        },
                        "awayTeam": {
                            "teamId": "1610612740",
                            "teamName": "Pelicans",
                            "teamTricode": "NOP",
                            "score": "101",
                        },
                    },
                ]
            }
        }

    def boxscore_fetch(game_id: str, _timeout_seconds: int):
        if game_id == "0022500001":
            home_team = {
                "teamId": "1610612739",
                "teamName": "Cavaliers",
                "teamTricode": "CLE",
                "score": "99",
            }
            away_team = {
                "teamId": "1610612740",
                "teamName": "Pelicans",
                "teamTricode": "NOP",
                "score": "101",
            }
        else:
            home_team = {
                "teamId": "1610612737",
                "teamName": "Hawks",
                "teamTricode": "ATL",
                "score": "110",
            }
            away_team = {
                "teamId": "1610612738",
                "teamName": "Celtics",
                "teamTricode": "BOS",
                "score": "108",
            }

        return {
            "boxScoreTraditional": {
                "gameId": game_id,
                "gameDate": "2025-02-10",
                "homeTeam": home_team,
                "awayTeam": away_team,
                "playersStats": [
                    {
                        "personId": f"{game_id}-1",
                        "name": "Sorted Test Player",
                        "teamId": home_team["teamId"],
                        "teamTricode": home_team["teamTricode"],
                        "minutes": "10:00",
                        "points": "5",
                    }
                ],
            }
        }

    provider = NBAApiProvider(
        cache_repository_factory=_make_cache_factory(engine),
        scoreboard_fetch=scoreboard_fetch,
        boxscore_fetch=boxscore_fetch,
        timeout_seconds=5,
    )

    games = asyncio.run(provider.get_games_by_date(target_date))

    assert [game.game_id for game in games] == ["0022500001", "0022500009"]


def test_default_scoreboard_fetch_falls_back_to_v2_for_unsupported_v3_shape(monkeypatch) -> None:
    calls: list[str] = []

    class FakeScoreboardV3:
        def __init__(self, *, game_date: str, timeout: int) -> None:
            assert game_date == "2025-02-10"
            assert timeout == 7

        def get_dict(self) -> dict[str, object]:
            calls.append("v3")
            return {"scoreboard": {"games": "unsupported"}}

    class FakeScoreboardV2:
        def __init__(self, *, game_date: str, timeout: int) -> None:
            assert game_date == "2025-02-10"
            assert timeout == 7

        def get_dict(self) -> dict[str, object]:
            calls.append("v2")
            return {"resultSets": []}

    fake_endpoints = types.ModuleType("nba_api.stats.endpoints")
    fake_endpoints.scoreboardv3 = types.SimpleNamespace(ScoreboardV3=FakeScoreboardV3)
    fake_endpoints.scoreboardv2 = types.SimpleNamespace(ScoreboardV2=FakeScoreboardV2)

    fake_stats = types.ModuleType("nba_api.stats")
    fake_stats.endpoints = fake_endpoints

    fake_nba_api = types.ModuleType("nba_api")
    fake_nba_api.stats = fake_stats

    monkeypatch.setitem(sys.modules, "nba_api", fake_nba_api)
    monkeypatch.setitem(sys.modules, "nba_api.stats", fake_stats)
    monkeypatch.setitem(sys.modules, "nba_api.stats.endpoints", fake_endpoints)

    payload = _default_scoreboard_fetch(date(2025, 2, 10), 7)

    assert payload == {"resultSets": []}
    assert calls == ["v3", "v2"]


def test_default_boxscore_fetch_falls_back_to_v2_when_v3_returns_invalid_payload(monkeypatch) -> None:
    calls: list[str] = []

    class FakeBoxScoreTraditionalV3:
        def __init__(self, *, game_id: str, timeout: int) -> None:
            assert game_id == "0022500106"
            assert timeout == 7
            calls.append("v3")
            raise ValueError("non-json response")

    class FakeBoxScoreTraditionalV2:
        def __init__(self, *, game_id: str, timeout: int) -> None:
            assert game_id == "0022500106"
            assert timeout == 7
            calls.append("v2")

        def get_dict(self) -> dict[str, object]:
            return {"resultSets": []}

    fake_endpoints = types.ModuleType("nba_api.stats.endpoints")
    fake_endpoints.boxscoretraditionalv3 = types.SimpleNamespace(BoxScoreTraditionalV3=FakeBoxScoreTraditionalV3)
    fake_endpoints.boxscoretraditionalv2 = types.SimpleNamespace(BoxScoreTraditionalV2=FakeBoxScoreTraditionalV2)

    fake_stats = types.ModuleType("nba_api.stats")
    fake_stats.endpoints = fake_endpoints

    fake_nba_api = types.ModuleType("nba_api")
    fake_nba_api.stats = fake_stats

    monkeypatch.setitem(sys.modules, "nba_api", fake_nba_api)
    monkeypatch.setitem(sys.modules, "nba_api.stats", fake_stats)
    monkeypatch.setitem(sys.modules, "nba_api.stats.endpoints", fake_endpoints)

    payload = _default_boxscore_fetch("0022500106", 7)

    assert payload == {"resultSets": []}
    assert calls == ["v3", "v2"]
