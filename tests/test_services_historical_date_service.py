import asyncio
from datetime import date, datetime

import pytest
from sqlmodel import Session

from hoophigher.data import HistoricalIndexRepository, create_sqlite_engine, init_db
from hoophigher.services import HistoricalDateService


def _make_session(tmp_path) -> Session:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)
    return Session(engine)


def test_builds_and_persists_eligible_dates_from_fetched_rows(tmp_path) -> None:
    session = _make_session(tmp_path)
    repository = HistoricalIndexRepository(session)

    rows_by_key: dict[tuple[str, str], tuple[dict[str, object], ...]] = {
        (
            "2019-20",
            "Regular Season",
        ): (
            {"GAME_ID": "0001", "GAME_DATE": "2020-01-15"},
            {"GAME_ID": "0001", "GAME_DATE": "2020-01-15"},
            {"GAME_ID": "0002", "GAME_DATE": "2020-01-15"},
            {"GAME_ID": "9991", "GAME_DATE": "2019-12-01"},
            {"GAME_ID": "9992", "GAME_DATE": "2019-12-01"},
        ),
        (
            "2021-22",
            "Playoffs",
        ): (
            {"GAME_ID": "0101", "GAME_DATE": "2021-12-25"},
            {"GAME_ID": "0101", "GAME_DATE": "2021-12-25"},
            {"GAME_ID": "0102", "GAME_DATE": "2021-12-25"},
            {"GAME_ID": "0103", "GAME_DATE": "2021-12-25"},
        ),
    }
    fetch_calls: list[tuple[str, str, int]] = []

    async def fake_fetcher(season: str, season_type: str, timeout_seconds: int):
        fetch_calls.append((season, season_type, timeout_seconds))
        return rows_by_key.get((season, season_type), ())

    service = HistoricalDateService(
        index_repository=repository,
        fetcher=fake_fetcher,
        timeout_seconds=17,
    )

    result = asyncio.run(
        service.get_or_build_eligible_dates(start_year=2020, end_year=2021, min_games=2)
    )

    assert result == (date(2020, 1, 15), date(2021, 12, 25))
    assert repository.list_window_dates(start_year=2020, end_year=2021, min_games=2) == [
        date(2020, 1, 15),
        date(2021, 12, 25),
    ]
    assert fetch_calls


def test_reuses_existing_index_without_rebuild(tmp_path) -> None:
    session = _make_session(tmp_path)
    repository = HistoricalIndexRepository(session)
    repository.replace_window(
        start_year=2021,
        end_year=2023,
        min_games=5,
        rows=[
            (date(2022, 2, 3), 7),
        ],
    )

    async def fail_if_called(_season: str, _season_type: str, _timeout_seconds: int):
        raise AssertionError("fetcher should not run when index already exists")

    service = HistoricalDateService(index_repository=repository, fetcher=fail_if_called)

    result = asyncio.run(
        service.get_or_build_eligible_dates(start_year=2021, end_year=2023, min_games=5)
    )

    assert result == (date(2022, 2, 3),)


def test_skips_failed_season_type_fetches_when_other_rows_are_eligible(tmp_path) -> None:
    session = _make_session(tmp_path)
    repository = HistoricalIndexRepository(session)

    async def flaky_fetcher(season: str, season_type: str, _timeout_seconds: int):
        if season_type == "Pre Season":
            raise ConnectionError("upstream returned non-json")
        if season == "2021-22" and season_type == "Regular Season":
            return (
                {"GAME_ID": "0101", "GAME_DATE": "2021-12-25"},
                {"GAME_ID": "0102", "GAME_DATE": "2021-12-25"},
                {"GAME_ID": "0103", "GAME_DATE": "2021-12-25"},
            )
        return ()

    service = HistoricalDateService(index_repository=repository, fetcher=flaky_fetcher)

    result = asyncio.run(
        service.get_or_build_eligible_dates(start_year=2021, end_year=2021, min_games=3)
    )

    assert result == (date(2021, 12, 25),)


def test_skips_malformed_game_date_rows_when_other_rows_are_eligible(tmp_path) -> None:
    session = _make_session(tmp_path)
    repository = HistoricalIndexRepository(session)

    async def fake_fetcher(_season: str, season_type: str, _timeout_seconds: int):
        if season_type != "Regular Season":
            return ()
        return (
            {"GAME_ID": "bad-date", "GAME_DATE": "not a date"},
            {"GAME_ID": "0101", "GAME_DATE": "2021-12-25"},
            {"GAME_ID": "0102", "GAME_DATE": "2021-12-25"},
        )

    service = HistoricalDateService(index_repository=repository, fetcher=fake_fetcher)

    result = asyncio.run(
        service.get_or_build_eligible_dates(start_year=2021, end_year=2021, min_games=2)
    )

    assert result == (date(2021, 12, 25),)


def test_propagates_cancellation_during_eligible_date_build(tmp_path) -> None:
    session = _make_session(tmp_path)
    repository = HistoricalIndexRepository(session)

    async def cancelling_fetcher(_season: str, _season_type: str, _timeout_seconds: int):
        raise asyncio.CancelledError

    service = HistoricalDateService(index_repository=repository, fetcher=cancelling_fetcher)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            service.get_or_build_eligible_dates(start_year=2021, end_year=2021, min_games=2)
        )


def test_raises_lookup_error_when_no_eligible_dates(tmp_path) -> None:
    session = _make_session(tmp_path)
    repository = HistoricalIndexRepository(session)

    async def fake_fetcher(_season: str, _season_type: str, _timeout_seconds: int):
        return (
            {"GAME_ID": "0001", "GAME_DATE": "2021-01-10"},
            {"GAME_ID": "0002", "GAME_DATE": "2021-01-10"},
        )

    service = HistoricalDateService(index_repository=repository, fetcher=fake_fetcher)

    with pytest.raises(LookupError, match="No eligible historical dates found"):
        asyncio.run(
            service.get_or_build_eligible_dates(start_year=2023, end_year=2023, min_games=5)
        )


def test_normalizes_datetime_game_date_and_keeps_grouping_counts(tmp_path) -> None:
    session = _make_session(tmp_path)
    repository = HistoricalIndexRepository(session)

    async def fake_fetcher(_season: str, _season_type: str, _timeout_seconds: int):
        return (
            {
                "GAME_ID": "0001",
                "GAME_DATE": datetime(2021, 12, 25, 22, 30, 0),
            },
            {
                "GAME_ID": "0002",
                "GAME_DATE": datetime(2021, 12, 25, 9, 15, 0),
            },
            {
                "GAME_ID": "0003",
                "GAME_DATE": date(2021, 12, 25),
            },
        )

    service = HistoricalDateService(index_repository=repository, fetcher=fake_fetcher)

    result = asyncio.run(
        service.get_or_build_eligible_dates(start_year=2021, end_year=2021, min_games=3)
    )

    assert result == (date(2021, 12, 25),)
    assert repository.list_window_dates(start_year=2021, end_year=2021, min_games=3) == [
        date(2021, 12, 25),
    ]


def test_validates_get_or_build_eligible_dates_input_window(tmp_path) -> None:
    session = _make_session(tmp_path)
    repository = HistoricalIndexRepository(session)
    service = HistoricalDateService(index_repository=repository)

    with pytest.raises(ValueError, match="start_year"):
        asyncio.run(
            service.get_or_build_eligible_dates(start_year=2024, end_year=2023, min_games=1)
        )


def test_validates_get_or_build_eligible_dates_min_games(tmp_path) -> None:
    session = _make_session(tmp_path)
    repository = HistoricalIndexRepository(session)
    service = HistoricalDateService(index_repository=repository)

    with pytest.raises(ValueError, match="min_games"):
        asyncio.run(
            service.get_or_build_eligible_dates(start_year=2023, end_year=2023, min_games=0)
        )


def test_raises_value_error_on_malformed_league_game_log_payload(tmp_path) -> None:
    session = _make_session(tmp_path)
    repository = HistoricalIndexRepository(session)
    service = HistoricalDateService(index_repository=repository)

    with pytest.raises(ValueError, match="Malformed LeagueGameLog payload"):
        service._parse_league_game_log_payload(
            {"resultSets": [{"headers": "bad", "rowSet": []}]},
            season="2021-22",
            season_type="Regular Season",
        )
