from datetime import date

import pytest

from hoophigher.data.stats_sources.nba_api_parsing import (
    GameStatus,
    _parse_game_status,
    _parse_scoreboard_payload,
)


@pytest.mark.parametrize(
    ("status_code", "status_text", "expected"),
    [
        (1, "7:00 pm ET", GameStatus.SCHEDULED),
        (2, "Q3 5:23", GameStatus.LIVE),
        (3, "Final", GameStatus.FINAL),
        (None, "Final/OT", GameStatus.FINAL),
        (None, "7:00 pm ET", GameStatus.LIVE),
        (None, "Halftime", GameStatus.LIVE),
        (None, None, None),
        (None, "", None),
        (4, None, GameStatus.LIVE),
        (0, "", GameStatus.LIVE),
        ("garbage", None, GameStatus.LIVE),
        (4, "Final", GameStatus.FINAL),
    ],
)
def test_parse_game_status_classifies_numeric_and_text_signals(
    status_code, status_text, expected
) -> None:
    assert _parse_game_status(status_code=status_code, status_text=status_text) == expected


def test_parse_scoreboard_payload_preserves_missing_status_as_unknown() -> None:
    source_date = date(2025, 2, 10)
    seeds = _parse_scoreboard_payload(
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

    assert len(seeds) == 1
    assert seeds[0].game_id == "0022500010"
    assert seeds[0].status is None
