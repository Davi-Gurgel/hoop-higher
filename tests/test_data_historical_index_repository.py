from datetime import date

import pytest
from sqlmodel import Session

from hoophigher.data import HistoricalIndexRepository, create_sqlite_engine, init_db


def make_session(tmp_path) -> Session:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)
    return Session(engine)


def test_replace_window_overwrites_existing_entries_for_same_window(tmp_path) -> None:
    session = make_session(tmp_path)
    repository = HistoricalIndexRepository(session)

    repository.replace_window(
        start_year=2022,
        end_year=2024,
        min_games=5,
        rows=[
            (date(2023, 1, 2), 8),
            (date(2023, 1, 5), 9),
        ],
    )
    repository.replace_window(
        start_year=2022,
        end_year=2024,
        min_games=5,
        rows=[
            (date(2023, 2, 10), 7),
        ],
    )

    assert repository.list_window_dates(start_year=2022, end_year=2024, min_games=5) == [
        date(2023, 2, 10)
    ]


def test_list_window_dates_returns_sorted_dates(tmp_path) -> None:
    session = make_session(tmp_path)
    repository = HistoricalIndexRepository(session)

    repository.replace_window(
        start_year=2021,
        end_year=2023,
        min_games=6,
        rows=[
            (date(2023, 3, 12), 6),
            (date(2023, 1, 11), 10),
            (date(2023, 2, 9), 8),
        ],
    )

    assert repository.list_window_dates(start_year=2021, end_year=2023, min_games=6) == [
        date(2023, 1, 11),
        date(2023, 2, 9),
        date(2023, 3, 12),
    ]


def test_replace_window_does_not_remove_other_windows(tmp_path) -> None:
    session = make_session(tmp_path)
    repository = HistoricalIndexRepository(session)

    repository.replace_window(
        start_year=2020,
        end_year=2022,
        min_games=5,
        rows=[
            (date(2021, 12, 20), 5),
            (date(2022, 1, 3), 7),
        ],
    )
    repository.replace_window(
        start_year=2023,
        end_year=2024,
        min_games=5,
        rows=[
            (date(2024, 1, 2), 6),
        ],
    )
    repository.replace_window(
        start_year=2023,
        end_year=2024,
        min_games=5,
        rows=[
            (date(2024, 2, 2), 8),
        ],
    )

    assert repository.list_window_dates(start_year=2020, end_year=2022, min_games=5) == [
        date(2021, 12, 20),
        date(2022, 1, 3),
    ]
    assert repository.list_window_dates(start_year=2023, end_year=2024, min_games=5) == [
        date(2024, 2, 2)
    ]


def test_same_game_date_can_exist_in_different_windows(tmp_path) -> None:
    session = make_session(tmp_path)
    repository = HistoricalIndexRepository(session)

    repository.replace_window(
        start_year=2020,
        end_year=2022,
        min_games=5,
        rows=[
            (date(2022, 1, 3), 7),
        ],
    )
    repository.replace_window(
        start_year=2021,
        end_year=2023,
        min_games=6,
        rows=[
            (date(2022, 1, 3), 9),
        ],
    )

    assert repository.list_window_dates(start_year=2020, end_year=2022, min_games=5) == [
        date(2022, 1, 3)
    ]
    assert repository.list_window_dates(start_year=2021, end_year=2023, min_games=6) == [
        date(2022, 1, 3)
    ]


def test_replace_window_rejects_row_below_min_games(tmp_path) -> None:
    session = make_session(tmp_path)
    repository = HistoricalIndexRepository(session)

    with pytest.raises(ValueError, match="game_count below min_games"):
        repository.replace_window(
            start_year=2022,
            end_year=2024,
            min_games=5,
            rows=[
                (date(2023, 2, 10), 4),
            ],
        )
