from __future__ import annotations

from datetime import date, datetime, timezone

from sqlmodel import Session

from hoophigher.data import QuestionRecord, RoundRecord, RunRecord, create_sqlite_engine, init_db
from hoophigher.domain.enums import GameMode
from hoophigher.services import RunHistoryService


def _make_engine(tmp_path):
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)
    return engine


def test_run_history_service_lists_runs_newest_first_and_loads_nested_details(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    with Session(engine) as session:
        older_run = RunRecord(
            mode=GameMode.ENDLESS,
            source_date=date(2025, 1, 12),
            final_score=340,
            correct_answers=3,
            wrong_answers=1,
            best_streak=3,
            created_at=datetime(2025, 1, 3, 9, 0, tzinfo=timezone.utc),
        )
        newer_run = RunRecord(
            mode=GameMode.ARCADE,
            source_date=date(2025, 1, 13),
            final_score=420,
            correct_answers=2,
            wrong_answers=1,
            best_streak=2,
            created_at=datetime(2025, 1, 3, 10, 0, tzinfo=timezone.utc),
        )
        session.add_all([older_run, newer_run])
        session.flush()
        older_run_id = older_run.id or 0

        first_round = RoundRecord(
            run_id=older_run_id,
            round_index=0,
            game_id="game-1",
            game_date=date(2025, 1, 12),
            correct_answers=1,
            wrong_answers=1,
            score_delta=40,
        )
        second_round = RoundRecord(
            run_id=older_run_id,
            round_index=1,
            game_id="game-2",
            game_date=date(2025, 1, 13),
            correct_answers=1,
            wrong_answers=0,
            score_delta=300,
        )
        session.add_all([first_round, second_round])
        session.flush()
        session.add_all(
            [
                QuestionRecord(
                    run_id=older_run_id,
                    round_id=first_round.id or 0,
                    question_index=0,
                    player_a_name="Player A",
                    player_a_team_abbreviation="HOM",
                    player_a_points=20,
                    player_b_name="Player B",
                    player_b_team_abbreviation="AWY",
                    player_b_points=24,
                    difficulty="medium",
                    guess="higher",
                    is_correct=True,
                    score_delta=100,
                ),
                QuestionRecord(
                    run_id=older_run_id,
                    round_id=first_round.id or 0,
                    question_index=1,
                    player_a_name="Player C",
                    player_a_team_abbreviation="HOM",
                    player_a_points=18,
                    player_b_name="Player D",
                    player_b_team_abbreviation="AWY",
                    player_b_points=12,
                    difficulty="easy",
                    guess="lower",
                    is_correct=False,
                    score_delta=-60,
                ),
            ]
        )
        session.commit()

    service = RunHistoryService(engine=engine)

    rows = service.list_runs()
    assert [(row.mode, row.score) for row in rows] == [
        (GameMode.ARCADE, 420),
        (GameMode.ENDLESS, 340),
    ]
    assert rows[1].source_date == date(2025, 1, 12)

    detail = service.get_run(older_run_id)
    assert detail is not None
    assert [round_history.game_id for round_history in detail.rounds] == ["game-1", "game-2"]
    first_question, second_question = detail.rounds[0].questions
    assert (
        first_question.player_a_name,
        first_question.player_b_points,
        first_question.is_correct,
    ) == (
        "Player A",
        24,
        True,
    )
    assert (second_question.player_b_name, second_question.guess, second_question.score_delta) == (
        "Player D",
        "lower",
        -60,
    )


def test_run_history_service_returns_empty_or_missing_results(tmp_path) -> None:
    service = RunHistoryService(engine=_make_engine(tmp_path))

    assert service.list_runs() == ()
    assert service.get_run(999) is None
