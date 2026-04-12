from datetime import date

import pytest
from sqlalchemy import text
from sqlmodel import Session, select
from hoophigher.data import (
    CacheRepository,
    QuestionRecord,
    QuestionRepository,
    RoundRecord,
    RoundRepository,
    RunRecord,
    RunRepository,
    StatsRepository,
    create_sqlite_engine,
    init_db,
    session_scope,
)
from hoophigher.domain.models import GameBoxScore, PlayerLine, TeamGameInfo


def make_game(game_id: str, game_date: date, home_score: int, away_score: int) -> GameBoxScore:
    return GameBoxScore(
        game_id=game_id,
        game_date=game_date,
        home_team=TeamGameInfo(team_id="home", name="Home", abbreviation="HOM", score=home_score),
        away_team=TeamGameInfo(team_id="away", name="Away", abbreviation="AWY", score=away_score),
        player_lines=(
            PlayerLine(
                player_id=f"{game_id}-a",
                player_name="Player A",
                team_id="home",
                team_abbreviation="HOM",
                points=home_score // 2,
                minutes=32,
            ),
            PlayerLine(
                player_id=f"{game_id}-b",
                player_name="Player B",
                team_id="away",
                team_abbreviation="AWY",
                points=away_score // 2,
                minutes=28,
            ),
        ),
    )


def make_session(tmp_path) -> Session:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)
    return Session(engine)


def test_init_db_creates_expected_tables(tmp_path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)

    from sqlalchemy import inspect

    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == {
        "cached_game_stats",
        "cached_games",
        "questions",
        "rounds",
        "runs",
    }


def test_run_round_question_repositories_persist_records(tmp_path) -> None:
    session = make_session(tmp_path)
    run_repo = RunRepository(session)
    round_repo = RoundRepository(session)
    question_repo = QuestionRepository(session)

    run = run_repo.create(
        RunRecord(
            mode="endless",
            source_date=date(2025, 2, 1),
            final_score=340,
            correct_answers=4,
            wrong_answers=1,
            best_streak=4,
            end_reason="user_exit",
        )
    )
    round_record = round_repo.create(
        RoundRecord(
            run_id=run.id or 1,
            round_index=0,
            game_id="game-1",
            game_date=date(2025, 2, 1),
            total_questions=5,
            correct_answers=4,
            wrong_answers=1,
            score_delta=340,
        )
    )
    question = question_repo.create(
        QuestionRecord(
            run_id=run.id or 1,
            round_id=round_record.id or 1,
            question_index=0,
            player_a_id="player-a",
            player_a_name="Player A",
            player_a_team_id="home",
            player_a_team_abbreviation="HOM",
            player_a_points=20,
            player_a_minutes=32,
            player_b_id="player-b",
            player_b_name="Player B",
            player_b_team_id="away",
            player_b_team_abbreviation="AWY",
            player_b_points=24,
            player_b_minutes=28,
            difficulty="medium",
            guess="higher",
            is_correct=True,
            score_delta=100,
            revealed_points=24,
            response_time_ms=1200,
        )
    )

    assert run.id is not None
    assert round_record.id is not None
    assert question.id is not None
    assert run_repo.get(run.id) == run
    assert round_repo.list_by_run(run.id) == [round_record]
    assert question_repo.list_by_round(round_record.id) == [question]


def test_stats_repository_computes_summary_and_leaderboard(tmp_path) -> None:
    session = make_session(tmp_path)
    run_repo = RunRepository(session)
    round_repo = RoundRepository(session)
    question_repo = QuestionRepository(session)
    stats_repo = StatsRepository(session)

    first_run = run_repo.create(
        RunRecord(
            mode="endless",
            source_date=date(2025, 2, 1),
            final_score=220,
            correct_answers=3,
            wrong_answers=1,
            best_streak=3,
            end_reason="user_exit",
        )
    )
    second_run = run_repo.create(
        RunRecord(
            mode="arcade",
            source_date=date(2025, 2, 2),
            final_score=400,
            correct_answers=4,
            wrong_answers=0,
            best_streak=4,
            end_reason="wrong_answer",
        )
    )

    first_round = round_repo.create(
        RoundRecord(
            run_id=first_run.id or 1,
            round_index=0,
            game_id="game-1",
            game_date=date(2025, 2, 1),
            total_questions=5,
            correct_answers=3,
            wrong_answers=1,
            score_delta=220,
        )
    )
    second_round = round_repo.create(
        RoundRecord(
            run_id=second_run.id or 2,
            round_index=0,
            game_id="game-2",
            game_date=date(2025, 2, 2),
            total_questions=5,
            correct_answers=4,
            wrong_answers=0,
            score_delta=400,
        )
    )

    question_repo.create(
        QuestionRecord(
            run_id=first_run.id or 1,
            round_id=first_round.id or 1,
            question_index=0,
            player_a_id="player-a",
            player_a_name="Player A",
            player_a_team_id="home",
            player_a_team_abbreviation="HOM",
            player_a_points=20,
            player_a_minutes=32,
            player_b_id="player-b",
            player_b_name="Player B",
            player_b_team_id="away",
            player_b_team_abbreviation="AWY",
            player_b_points=24,
            player_b_minutes=28,
            difficulty="medium",
            guess="higher",
            is_correct=True,
            score_delta=100,
            revealed_points=24,
            response_time_ms=900,
        )
    )
    question_repo.create(
        QuestionRecord(
            run_id=first_run.id or 1,
            round_id=first_round.id or 1,
            question_index=1,
            player_a_id="player-c",
            player_a_name="Player C",
            player_a_team_id="home",
            player_a_team_abbreviation="HOM",
            player_a_points=18,
            player_a_minutes=30,
            player_b_id="player-d",
            player_b_name="Player D",
            player_b_team_id="away",
            player_b_team_abbreviation="AWY",
            player_b_points=12,
            player_b_minutes=26,
            difficulty="easy",
            guess="lower",
            is_correct=False,
            score_delta=-60,
            revealed_points=12,
            response_time_ms=1000,
        )
    )
    question_repo.create(
        QuestionRecord(
            run_id=second_run.id or 2,
            round_id=second_round.id or 2,
            question_index=0,
            player_a_id="player-e",
            player_a_name="Player E",
            player_a_team_id="home",
            player_a_team_abbreviation="HOM",
            player_a_points=22,
            player_a_minutes=33,
            player_b_id="player-f",
            player_b_name="Player F",
            player_b_team_id="away",
            player_b_team_abbreviation="AWY",
            player_b_points=30,
            player_b_minutes=29,
            difficulty="medium",
            guess="higher",
            is_correct=True,
            score_delta=150,
            revealed_points=30,
            response_time_ms=800,
        )
    )

    assert stats_repo.count_runs() == 2
    assert stats_repo.count_rounds() == 2
    assert stats_repo.count_questions() == 3
    assert stats_repo.count_correct_questions() == 2
    assert stats_repo.count_wrong_questions() == 1
    assert stats_repo.best_score() == 400
    assert stats_repo.best_streak() == 4
    assert stats_repo.mode_distribution() == {"arcade": 1, "endless": 1}
    assert stats_repo.leaderboard(limit=1)[0] == second_run


def test_cache_repository_round_trips_game_payloads(tmp_path) -> None:
    session = make_session(tmp_path)
    cache_repo = CacheRepository(session)
    game_one = make_game("game-1", date(2025, 2, 1), 110, 104)
    game_two = make_game("game-2", date(2025, 2, 1), 101, 99)

    cache_repo.set_games_by_date(date(2025, 2, 1), [game_one, game_two])
    cache_repo.set_game_boxscore(game_one)

    assert cache_repo.get_games_by_date(date(2025, 2, 1)) == [game_one, game_two]
    assert cache_repo.get_game_boxscore("game-1") == game_one
    assert cache_repo.get_game_boxscore("missing") is None


def test_session_scope_commits_on_success(tmp_path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)

    with session_scope(engine) as session:
        repo = RunRepository(session)
        created = repo.create(
            RunRecord(
                mode="endless",
                source_date=date(2025, 2, 3),
                final_score=100,
                correct_answers=1,
                wrong_answers=0,
                best_streak=1,
            )
        )
        assert created.id is not None
        created_id = created.id

    with Session(engine) as verification_session:
        persisted = verification_session.get(RunRecord, created_id)
        assert persisted is not None
        assert persisted.final_score == 100


def test_session_scope_rolls_back_on_error(tmp_path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)

    with pytest.raises(RuntimeError, match="boom"):
        with session_scope(engine) as session:
            repo = RunRepository(session)
            repo.create(
                RunRecord(
                    mode="arcade",
                    source_date=date(2025, 2, 4),
                    final_score=150,
                    correct_answers=1,
                    wrong_answers=1,
                    best_streak=1,
                )
            )
            raise RuntimeError("boom")

    with Session(engine) as verification_session:
        assert verification_session.exec(select(RunRecord)).all() == []


def test_create_sqlite_engine_applies_configured_busy_timeout_for_file_db(tmp_path) -> None:
    engine = create_sqlite_engine(
        f"sqlite:///{tmp_path / 'hoophigher.db'}",
        sqlite_busy_timeout_ms=1234,
    )
    with engine.connect() as conn:
        timeout_ms = conn.execute(text("PRAGMA busy_timeout")).scalar_one()
    assert timeout_ms == 1234


def test_create_sqlite_engine_creates_parent_directory_for_file_db(tmp_path) -> None:
    database_path = tmp_path / "nested" / "hoophigher.db"

    create_sqlite_engine(f"sqlite:///{database_path}")

    assert database_path.parent == tmp_path / "nested"
    assert database_path.parent.exists()
    assert database_path.parent.is_dir()


def test_create_sqlite_engine_does_not_apply_file_pragmas_to_memory_db() -> None:
    engine_with_override = create_sqlite_engine(
        "sqlite:///:memory:",
        sqlite_busy_timeout_ms=1234,
    )
    default_engine = create_sqlite_engine("sqlite:///:memory:")
    with engine_with_override.connect() as conn:
        timeout_with_override = conn.execute(text("PRAGMA busy_timeout")).scalar_one()
    with default_engine.connect() as conn:
        timeout_default = conn.execute(text("PRAGMA busy_timeout")).scalar_one()
    assert timeout_with_override == timeout_default


def test_create_sqlite_engine_rejects_invalid_journal_mode(tmp_path) -> None:
    with pytest.raises(ValueError, match="sqlite_journal_mode must be one of"):
        create_sqlite_engine(
            f"sqlite:///{tmp_path / 'hoophigher.db'}",
            sqlite_journal_mode="invalid",
        )


def test_create_sqlite_engine_rejects_invalid_synchronous_value(tmp_path) -> None:
    with pytest.raises(ValueError, match="sqlite_synchronous must be one of"):
        create_sqlite_engine(
            f"sqlite:///{tmp_path / 'hoophigher.db'}",
            sqlite_synchronous="invalid",
        )


def test_create_sqlite_engine_rejects_negative_busy_timeout(tmp_path) -> None:
    with pytest.raises(ValueError, match="sqlite_busy_timeout_ms must be >= 0"):
        create_sqlite_engine(
            f"sqlite:///{tmp_path / 'hoophigher.db'}",
            sqlite_busy_timeout_ms=-1,
        )
