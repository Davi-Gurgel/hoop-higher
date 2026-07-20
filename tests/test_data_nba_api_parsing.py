from datetime import date

import pytest

from hoophigher.data.stats_sources.nba_api_parsing import (
    NBAGameStatus,
    ParsedScoreboardGame,
    parse_game_status,
    parse_nba_game_payload,
    parse_scoreboard_payload,
)


@pytest.mark.parametrize(
    ("status_code", "status_text", "expected"),
    [
        (1, "7:00 pm ET", NBAGameStatus.SCHEDULED),
        (2, "Q3 5:23", NBAGameStatus.LIVE),
        (3, "Final", NBAGameStatus.FINAL),
        (None, "Final/OT", NBAGameStatus.FINAL),
        (None, "7:00 pm ET", NBAGameStatus.LIVE),
        (None, "Halftime", NBAGameStatus.LIVE),
        (None, None, None),
        (None, "", None),
        (4, None, NBAGameStatus.LIVE),
        (0, "", NBAGameStatus.LIVE),
        ("garbage", None, NBAGameStatus.LIVE),
        (4, "Final", NBAGameStatus.FINAL),
    ],
)
def test_parse_game_status_classifies_numeric_and_text_signals(
    status_code, status_text, expected
) -> None:
    assert parse_game_status(status_code=status_code, status_text=status_text) == expected


def test_parse_scoreboard_payload_preserves_missing_status_as_unknown() -> None:
    source_date = date(2025, 2, 10)
    parsed_games = parse_scoreboard_payload(
        {
            "scoreboard": {
                "games": [
                    {
                        "gameId": "0022500010",
                        "gameDate": source_date.isoformat(),
                        "homeTeam": {
                            "teamId": "1",
                            "teamName": "Home",
                            "teamTricode": "HOM",
                            "score": "110",
                        },
                        "awayTeam": {
                            "teamId": "2",
                            "teamName": "Away",
                            "teamTricode": "AWY",
                            "score": "108",
                        },
                    }
                ]
            }
        },
        expected_date=source_date,
    )

    assert len(parsed_games) == 1
    assert isinstance(parsed_games[0], ParsedScoreboardGame)
    assert parsed_games[0].game_id == "0022500010"
    assert parsed_games[0].status is None


def test_parse_v2_scoreboard_maps_team_scores_and_status() -> None:
    parsed_games = parse_scoreboard_payload(
        {
            "resultSets": [
                {
                    "name": "GameHeader",
                    "headers": [
                        "GAME_ID",
                        "GAME_DATE_EST",
                        "HOME_TEAM_ID",
                        "VISITOR_TEAM_ID",
                        "GAME_STATUS_ID",
                        "GAME_STATUS_TEXT",
                        "PTS_HOME",
                        "PTS_AWAY",
                    ],
                    "rowSet": [["game-1", "2025-02-10", "1", "2", 3, "Final", 111, 109]],
                },
                {
                    "name": "LineScore",
                    "headers": ["GAME_ID", "TEAM_ID", "TEAM_ABBREVIATION"],
                    "rowSet": [["game-1", "1", "ATL"], ["game-1", "2", "BOS"]],
                },
            ]
        },
        expected_date=date(2025, 2, 10),
    )

    assert len(parsed_games) == 1
    assert parsed_games[0].status is NBAGameStatus.FINAL
    assert (parsed_games[0].home_team.abbreviation, parsed_games[0].home_team.score) == (
        "ATL",
        111,
    )
    assert (parsed_games[0].away_team.abbreviation, parsed_games[0].away_team.score) == (
        "BOS",
        109,
    )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"scoreboard": {"games": "invalid"}}, "expected list"),
        ({"resultSets": []}, "missing result set 'GameHeader'"),
    ],
)
def test_parse_scoreboard_rejects_malformed_payloads(payload, message) -> None:
    with pytest.raises(ValueError, match=message):
        parse_scoreboard_payload(payload, expected_date=date(2025, 2, 10))


def test_parse_flat_v3_boxscore_parses_minutes_and_skips_blank_player_ids() -> None:
    game = parse_nba_game_payload(
        {
            "boxScoreTraditional": {
                "gameId": "0022500004",
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
        },
        expected_game_id="0022500004",
    )

    assert [player.player_id for player in game.player_lines] == ["11", "12"]
    assert [player.minutes for player in game.player_lines] == [12, 0]
    assert [player.points for player in game.player_lines] == [17, 0]


def test_parse_nested_v3_boxscore() -> None:
    game = parse_nba_game_payload(
        {
            "boxScoreTraditional": {
                "gameId": "0022500104",
                "gameDate": "2025-02-10",
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
                            "statistics": {"minutes": "PT12M34.00S", "points": "17"},
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
                            "statistics": {"minutes": "PT09M00.00S", "points": "8"},
                        }
                    ],
                },
            }
        },
        expected_game_id="0022500104",
    )

    assert game.home_team.score == 111
    assert game.away_team.score == 109
    assert [
        (player.player_name, player.team_abbreviation, player.minutes, player.points)
        for player in game.player_lines
    ] == [
        ("Player One", "ATL", 12, 17),
        ("Player Two", "BOS", 9, 8),
    ]


def test_parse_v2_boxscore() -> None:
    game_id = "0022500105"
    game = parse_nba_game_payload(
        {
            "resultSets": [
                {
                    "name": "GameSummary",
                    "headers": [
                        "GAME_DATE_EST",
                        "GAME_ID",
                        "HOME_TEAM_ID",
                        "VISITOR_TEAM_ID",
                    ],
                    "rowSet": [["2025-02-10", game_id, "1610612737", "1610612738"]],
                },
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
                    "headers": [
                        "GAME_ID",
                        "TEAM_ID",
                        "TEAM_NAME",
                        "TEAM_ABBREVIATION",
                        "PTS",
                    ],
                    "rowSet": [
                        [game_id, "1610612737", "Hawks", "ATL", 111],
                        [game_id, "1610612738", "Celtics", "BOS", 109],
                    ],
                },
            ]
        },
        expected_game_id=game_id,
    )

    assert game.source_date == date(2025, 2, 10)
    assert game.home_team.abbreviation == "ATL"
    assert game.away_team.abbreviation == "BOS"
    assert [
        (player.player_name, player.team_abbreviation, player.minutes, player.points)
        for player in game.player_lines
    ] == [
        ("Player One", "ATL", 12, 17),
        ("Player Two", "BOS", 9, 8),
    ]


def test_parse_v2_boxscore_uses_date_fallback_without_game_summary() -> None:
    game_id = "0022500105"
    game = parse_nba_game_payload(
        {
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
                        [game_id, "1", "ATL", "11", "Player One", "12:34", 17],
                        [game_id, "2", "BOS", "12", "Player Two", "9:00", 8],
                    ],
                },
                {
                    "name": "TeamStats",
                    "headers": ["GAME_ID", "TEAM_ID", "TEAM_ABBREVIATION", "PTS"],
                    "rowSet": [
                        [game_id, "1", "ATL", 111],
                        [game_id, "2", "BOS", 109],
                    ],
                },
            ]
        },
        expected_game_id=game_id,
        source_date_fallback=date(2025, 2, 10),
    )

    assert game.source_date == date(2025, 2, 10)
    assert game.home_team.abbreviation == "ATL"
    assert game.away_team.abbreviation == "BOS"


@pytest.mark.parametrize(
    ("payload", "error_type", "message"),
    [
        ({}, ValueError, "expected V3 or V2 structure"),
        (
            {
                "boxScoreTraditional": {
                    "gameId": "0022500005",
                    "gameDate": "2025-02-10",
                    "awayTeam": {
                        "teamId": "2",
                        "teamName": "Away",
                        "teamTricode": "AWY",
                    },
                    "playersStats": [
                        {
                            "personId": "11",
                            "name": "Bench Player",
                            "teamId": "1",
                            "teamTricode": "HOM",
                            "minutes": "0:00",
                            "points": 0,
                        }
                    ],
                }
            },
            ValueError,
            "Malformed payload",
        ),
        (
            {
                "boxScoreTraditional": {
                    "gameId": "different-game",
                }
            },
            LookupError,
            "not found",
        ),
        (
            {
                "boxScoreTraditional": {
                    "gameId": "0022500005",
                    "gameDate": "2025-02-10",
                    "homeTeam": {
                        "teamId": "1",
                        "teamName": "Home",
                        "teamTricode": "HOM",
                    },
                    "awayTeam": {
                        "teamId": "2",
                        "teamName": "Away",
                        "teamTricode": "AWY",
                    },
                    "playersStats": [
                        {
                            "personId": "11",
                            "name": "Bench Player",
                            "teamId": "1",
                            "teamTricode": "HOM",
                            "minutes": "0:00",
                            "points": 0,
                        }
                    ],
                }
            },
            LookupError,
            "stats are unavailable",
        ),
    ],
)
def test_parse_boxscore_rejects_malformed_payloads(payload, error_type, message) -> None:
    with pytest.raises(error_type, match=message):
        parse_nba_game_payload(payload, expected_game_id="0022500005")
