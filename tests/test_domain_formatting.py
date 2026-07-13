from __future__ import annotations

from datetime import date

from hoophigher.domain.formatting import (
    format_source_date,
    player_first_name,
    player_last_name,
)


def test_format_source_date_renders_date_or_placeholder() -> None:
    assert format_source_date(date(2025, 4, 12)) == "12-04-2025"
    assert format_source_date(None) == "--"


def test_player_name_tokens() -> None:
    assert player_first_name("LeBron James") == "LeBron"
    assert player_last_name("LeBron James") == "James"
    assert player_last_name("Shai Gilgeous-Alexander") == "Gilgeous-Alexander"


def test_player_name_tokens_fall_back_to_the_full_string() -> None:
    assert player_first_name("Nene") == "Nene"
    assert player_last_name("Nene") == "Nene"
    assert player_last_name("") == ""
