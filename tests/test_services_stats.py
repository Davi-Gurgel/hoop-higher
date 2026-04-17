from __future__ import annotations

from datetime import date, datetime, timezone

from sqlmodel import Session

from hoophigher.data import QuestionRecord, RoundRecord, RunRecord, create_sqlite_engine, init_db
from hoophigher.domain.enums import GameMode
from hoophigher.services.stats_service import StatsService


def _make_engine(tmp_path):
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)
    return engine


def _seed_stats_data(engine) -> None:
    with Session(engine) as session:
        first_run = RunRecord(
            mode=GameMode.ENDLESS,
            source_date=date(2025, 1, 12),
            final_score=340,
            correct_answers=3,
            wrong_answers=1,
            best_streak=3,
            end_reason="user_exit",
            created_at=datetime(2025, 1, 3, 9, 0, tzinfo=timezone.utc),
        )
        second_run = RunRecord(
            mode=GameMode.ARCADE,
            source_date=date(2025, 1, 13),
            final_score=420,
            correct_answers=2,
            wrong_answers=1,
            best_streak=2,
            end_reason="wrong_answer",
            created_at=datetime(2025, 1, 3, 10, 0, tzinfo=timezone.utc),
        )
        session.add_all([first_run, second_run])
        session.flush()

        first_round = RoundRecord(
            run_id=first_run.id or 1,
            round_index=0,
            game_id="game-1",
            game_date=date(2025, 1, 12),
            total_questions=4,
            correct_answers=3,
            wrong_answers=1,
            score_delta=340,
        )
        second_round = RoundRecord(
            run_id=second_run.id or 2,
            round_index=0,
            game_id="game-2",
            game_date=date(2025, 1, 13),
            total_questions=3,
            correct_answers=2,
            wrong_answers=1,
            score_delta=420,
        )
        session.add_all([first_round, second_round])
        session.flush()

        session.add_all(
            [
                QuestionRecord(
                    run_id=first_run.id or 1,
                    round_id=first_round.id or 1,
                    question_index=0,
                    player_a_id="a1",
                    player_a_name="Player A1",
                    player_a_team_id="home",
                    player_a_team_abbreviation="HOM",
                    player_a_points=20,
                    player_a_minutes=30,
                    player_b_id="b1",
                    player_b_name="Player B1",
                    player_b_team_id="away",
                    player_b_team_abbreviation="AWY",
                    player_b_points=24,
                    player_b_minutes=31,
                    difficulty="medium",
                    guess="higher",
                    is_correct=True,
                    score_delta=100,
                    revealed_points=24,
                    response_time_ms=900,
                ),
                QuestionRecord(
                    run_id=first_run.id or 1,
                    round_id=first_round.id or 1,
                    question_index=1,
                    player_a_id="a2",
                    player_a_name="Player A2",
                    player_a_team_id="home",
                    player_a_team_abbreviation="HOM",
                    player_a_points=18,
                    player_a_minutes=28,
                    player_b_id="b2",
                    player_b_name="Player B2",
                    player_b_team_id="away",
                    player_b_team_abbreviation="AWY",
                    player_b_points=12,
                    player_b_minutes=27,
                    difficulty="easy",
                    guess="lower",
                    is_correct=False,
                    score_delta=-60,
                    revealed_points=12,
                    response_time_ms=1100,
                ),
                QuestionRecord(
                    run_id=second_run.id or 2,
                    round_id=second_round.id or 2,
                    question_index=0,
                    player_a_id="a3",
                    player_a_name="Player A3",
                    player_a_team_id="home",
                    player_a_team_abbreviation="HOM",
                    player_a_points=16,
                    player_a_minutes=29,
                    player_b_id="b3",
                    player_b_name="Player B3",
                    player_b_team_id="away",
                    player_b_team_abbreviation="AWY",
                    player_b_points=22,
                    player_b_minutes=33,
                    difficulty="medium",
                    guess="higher",
                    is_correct=True,
                    score_delta=150,
                    revealed_points=22,
                    response_time_ms=800,
                ),
            ]
        )
        session.commit()


def test_stats_service_aggregates_local_metrics(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    _seed_stats_data(engine)

    result = StatsService(engine=engine).get_stats()

    assert result.total_runs == 2
    assert result.total_answered_questions == 3
    assert result.total_correct_answers == 2
    assert result.accuracy_rate == 2 / 3
    assert result.best_score == 420
    assert result.best_streak == 3
    assert [(row.mode, row.count) for row in result.mode_distribution] == [
        (GameMode.ARCADE, 1),
        (GameMode.ENDLESS, 1),
    ]


def test_stats_service_returns_zero_defaults_without_runs(tmp_path) -> None:
    engine = _make_engine(tmp_path)

    result = StatsService(engine=engine).get_stats()

    assert result.total_runs == 0
    assert result.total_answered_questions == 0
    assert result.total_correct_answers == 0
    assert result.accuracy_rate == 0.0
    assert result.best_score == 0
    assert result.best_streak == 0
    assert result.mode_distribution == ()
