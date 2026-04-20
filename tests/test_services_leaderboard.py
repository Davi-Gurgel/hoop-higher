from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlmodel import Session

from hoophigher.data import RunRecord, create_sqlite_engine, init_db
from hoophigher.domain.enums import GameMode
from hoophigher.services.leaderboard_service import LeaderboardService


def _make_engine(tmp_path):
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)
    return engine


def _persist_runs(
    session: Session,
    runs: list[RunRecord],
) -> None:
    session.add_all(runs)
    session.flush()


def test_leaderboard_service_limits_results_to_top_ten(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    with Session(engine) as session:
        _persist_runs(
            session,
            [
                RunRecord(
                    mode=GameMode.ENDLESS,
                    source_date=date(2025, 1, 12),
                    final_score=1000 - (index * 10),
                    correct_answers=5,
                    wrong_answers=0,
                    best_streak=10 - (index % 3),
                    end_reason="user_exit",
                    created_at=datetime(2025, 1, 1, 12, index, tzinfo=timezone.utc),
                )
                for index in range(12)
            ],
        )
        session.commit()

    result = LeaderboardService(engine=engine).get_leaderboard()

    assert result.is_empty is False
    assert len(result.rows) == 10
    assert [row.rank for row in result.rows] == list(range(1, 11))
    assert [row.score for row in result.rows] == [1000, 990, 980, 970, 960, 950, 940, 930, 920, 910]


def test_leaderboard_service_rejects_non_positive_limit(tmp_path) -> None:
    engine = _make_engine(tmp_path)

    service = LeaderboardService(engine=engine)

    for invalid_limit in (0, -1):
        with pytest.raises(ValueError, match="positive integer"):
            service.get_leaderboard(limit=invalid_limit)


def test_leaderboard_service_preserves_repository_ordering_rules(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    with Session(engine) as session:
        _persist_runs(
            session,
            [
                RunRecord(
                    mode=GameMode.ENDLESS,
                    source_date=date(2025, 1, 12),
                    final_score=500,
                    best_streak=4,
                    correct_answers=3,
                    wrong_answers=0,
                    end_reason="user_exit",
                    created_at=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
                ),
                RunRecord(
                    mode=GameMode.ARCADE,
                    source_date=date(2025, 1, 13),
                    final_score=500,
                    best_streak=4,
                    correct_answers=7,
                    wrong_answers=0,
                    end_reason="user_exit",
                    created_at=datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc),
                ),
                RunRecord(
                    mode=GameMode.HISTORICAL,
                    source_date=None,
                    final_score=500,
                    best_streak=4,
                    correct_answers=7,
                    wrong_answers=0,
                    end_reason="user_exit",
                    created_at=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
                ),
            ],
        )
        session.commit()

    result = LeaderboardService(engine=engine).get_leaderboard()

    assert [row.mode for row in result.rows] == [
        GameMode.HISTORICAL,
        GameMode.ARCADE,
        GameMode.ENDLESS,
    ]
    assert all(isinstance(row.mode, GameMode) for row in result.rows)
    assert [row.correct_answers for row in result.rows] == [7, 7, 3]
    assert [row.source_date_label for row in result.rows] == ["--", "13-01-2025", "12-01-2025"]
    assert [row.rank for row in result.rows] == [1, 2, 3]


def test_leaderboard_service_returns_empty_result_when_no_runs_exist(tmp_path) -> None:
    engine = _make_engine(tmp_path)

    result = LeaderboardService(engine=engine).get_leaderboard()

    assert result.is_empty is True
    assert result.rows == ()
