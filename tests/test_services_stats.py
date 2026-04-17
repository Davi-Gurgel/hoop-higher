from __future__ import annotations

from datetime import date

from sqlmodel import Session

from hoophigher.data import RunRecord, RunRepository, create_sqlite_engine, init_db
from hoophigher.services.stats_service import StatsService


def _seed_runs(engine) -> None:
    with Session(engine) as session:
        run_repo = RunRepository(session)
        run_repo.create(
            RunRecord(
                mode="endless",
                source_date=date(2025, 1, 12),
                final_score=320,
                correct_answers=4,
                wrong_answers=1,
                best_streak=3,
                end_reason="user_exit",
            )
        )
        run_repo.create(
            RunRecord(
                mode="arcade",
                source_date=date(2025, 1, 13),
                final_score=450,
                correct_answers=3,
                wrong_answers=0,
                best_streak=3,
                end_reason="wrong_answer",
            )
        )
        run_repo.create(
            RunRecord(
                mode="historical",
                source_date=date(2025, 1, 12),
                final_score=260,
                correct_answers=2,
                wrong_answers=2,
                best_streak=2,
                end_reason="no_more_games",
            )
        )
        session.commit()


def test_stats_service_returns_summary_and_distribution(tmp_path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)
    _seed_runs(engine)
    service = StatsService(engine=engine)

    summary = service.get_summary()

    assert summary.total_runs == 3
    assert summary.total_answered == 12
    assert summary.total_correct == 9
    assert summary.accuracy_percent == 75.0
    assert summary.best_score == 450
    assert summary.best_streak == 3
    assert summary.mode_distribution == {"arcade": 1, "endless": 1, "historical": 1}


def test_stats_service_returns_sorted_leaderboard_entries(tmp_path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)
    _seed_runs(engine)
    service = StatsService(engine=engine)

    leaderboard = service.get_leaderboard(limit=2)

    assert len(leaderboard) == 2
    assert leaderboard[0].score == 450
    assert leaderboard[0].mode == "arcade"
    assert leaderboard[1].score == 320
    assert leaderboard[1].mode == "endless"
