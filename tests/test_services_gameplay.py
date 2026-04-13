import asyncio
from datetime import date
from random import Random

import pytest
from sqlmodel import Session

from hoophigher.data import (
    QuestionRepository,
    RoundRepository,
    RunRepository,
    create_sqlite_engine,
    init_db,
)
from hoophigher.data.api import MockProvider
from hoophigher.domain.enums import GameMode, GuessDirection, RunEndReason
from hoophigher.domain.models import GameBoxScore
from hoophigher.services import GameplayService


def _make_engine(tmp_path):
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)
    return engine


def _opposite_guess(guess: GuessDirection) -> GuessDirection:
    return GuessDirection.LOWER if guess is GuessDirection.HIGHER else GuessDirection.HIGHER


def test_endless_continues_after_wrong_answer_and_persists_progress(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = GameplayService(engine=engine, provider=MockProvider(), rng=Random(7))

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.ENDLESS,
            source_date=date(2025, 1, 12),
            total_questions=5,
        )
    )
    question = start_snapshot.current_question
    assert question is not None

    wrong_guess = _opposite_guess(question.answer)
    result = asyncio.run(service.submit_answer(wrong_guess, response_time_ms=900))
    snapshot = service.snapshot()

    assert result.is_correct is False
    assert snapshot.is_finished is False
    assert snapshot.wrong_answers == 1
    assert snapshot.score == -60

    with Session(engine) as session:
        run_record = RunRepository(session).get(start_snapshot.run_id)
        round_record = RoundRepository(session).get(start_snapshot.round_id)
        questions = QuestionRepository(session).list_by_run(start_snapshot.run_id)

    assert run_record is not None
    assert run_record.final_score == -60
    assert run_record.wrong_answers == 1
    assert run_record.end_reason is None
    assert round_record is not None
    assert round_record.wrong_answers == 1
    assert len(questions) == 1
    assert questions[0].is_correct is False


def test_service_requires_active_run_for_snapshot_submit_and_end_run(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = GameplayService(engine=engine, provider=MockProvider(), rng=Random(1))

    with pytest.raises(ValueError, match="No active run"):
        service.snapshot()

    with pytest.raises(ValueError, match="No active run"):
        asyncio.run(service.submit_answer(GuessDirection.HIGHER))

    with pytest.raises(ValueError, match="No active run"):
        service.end_run()


def test_arcade_ends_on_first_error(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = GameplayService(engine=engine, provider=MockProvider(), rng=Random(3))

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.ARCADE,
            source_date=date(2025, 1, 12),
            total_questions=5,
        )
    )
    question = start_snapshot.current_question
    assert question is not None

    wrong_guess = _opposite_guess(question.answer)
    asyncio.run(service.submit_answer(wrong_guess))
    snapshot = service.snapshot()

    assert snapshot.is_finished is True
    assert snapshot.end_reason is RunEndReason.WRONG_ANSWER
    assert snapshot.score == 0


def test_submit_answer_rejects_finished_run(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = GameplayService(engine=engine, provider=MockProvider(), rng=Random(3))

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.ARCADE,
            source_date=date(2025, 1, 12),
            total_questions=5,
        )
    )
    question = start_snapshot.current_question
    assert question is not None

    asyncio.run(service.submit_answer(_opposite_guess(question.answer)))

    with pytest.raises(ValueError, match="finished run"):
        asyncio.run(service.submit_answer(GuessDirection.HIGHER))


def test_start_run_requires_candidate_dates_without_source_date(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = GameplayService(engine=engine, provider=MockProvider(), rng=Random(1))

    with pytest.raises(ValueError, match="candidate_dates is required"):
        asyncio.run(service.start_run(GameMode.ENDLESS))


def test_start_run_raises_when_source_date_has_no_games(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = GameplayService(engine=engine, provider=MockProvider(), rng=Random(1))

    with pytest.raises(LookupError, match="No games found for source date"):
        asyncio.run(
            service.start_run(
                GameMode.ENDLESS,
                source_date=date(2025, 1, 14),
                total_questions=5,
            )
        )


def test_non_historical_start_run_raises_when_candidate_dates_have_no_games(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = GameplayService(engine=engine, provider=MockProvider(), rng=Random(1))

    with pytest.raises(LookupError, match="No games found for provided candidate dates"):
        asyncio.run(
            service.start_run(
                GameMode.ENDLESS,
                candidate_dates=[date(2025, 1, 14)],
                total_questions=5,
            )
        )


def test_historical_start_run_raises_when_no_candidate_date_has_enough_games(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = GameplayService(engine=engine, provider=MockProvider(), rng=Random(1))

    with pytest.raises(LookupError, match="No historical date with enough games was found"):
        asyncio.run(
            service.start_run(
                GameMode.HISTORICAL,
                candidate_dates=[date(2025, 1, 13)],
                total_questions=5,
            )
        )


def test_endless_starts_next_round_after_perfect_round_and_persists_rounds(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = GameplayService(engine=engine, provider=MockProvider(), rng=Random(1))

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.ENDLESS,
            source_date=date(2025, 1, 12),
            total_questions=5,
        )
    )

    for _ in range(start_snapshot.total_questions):
        question = service.snapshot().current_question
        assert question is not None
        asyncio.run(service.submit_answer(question.answer))

    snapshot = service.snapshot()

    assert snapshot.is_finished is False
    assert snapshot.round_index == 1
    assert snapshot.current_question is not None
    assert snapshot.score == 500

    with Session(engine) as session:
        run_record = RunRepository(session).get(start_snapshot.run_id)
        rounds = RoundRepository(session).list_by_run(start_snapshot.run_id)

    assert run_record is not None
    assert run_record.final_score == 500
    assert run_record.correct_answers == 5
    assert [round_record.round_index for round_record in rounds] == [0, 1]
    assert [round_record.total_questions for round_record in rounds] == [5, 5]


def test_arcade_starts_next_round_after_perfect_round_and_persists_rounds(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = GameplayService(engine=engine, provider=MockProvider(), rng=Random(1))

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.ARCADE,
            source_date=date(2025, 1, 12),
            total_questions=5,
        )
    )

    for _ in range(start_snapshot.total_questions):
        question = service.snapshot().current_question
        assert question is not None
        asyncio.run(service.submit_answer(question.answer))

    snapshot = service.snapshot()

    assert snapshot.is_finished is False
    assert snapshot.round_index == 1
    assert snapshot.current_question is not None
    assert snapshot.score == 750

    with Session(engine) as session:
        run_record = RunRepository(session).get(start_snapshot.run_id)
        rounds = RoundRepository(session).list_by_run(start_snapshot.run_id)

    assert run_record is not None
    assert run_record.final_score == 750
    assert run_record.correct_answers == 5
    assert [round_record.round_index for round_record in rounds] == [0, 1]
    assert [round_record.total_questions for round_record in rounds] == [5, 5]


def test_end_run_persists_user_exit_and_is_idempotent(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = GameplayService(engine=engine, provider=MockProvider(), rng=Random(1))

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.ENDLESS,
            source_date=date(2025, 1, 12),
            total_questions=5,
        )
    )

    first_snapshot = service.end_run()
    second_snapshot = service.end_run()

    assert first_snapshot.run_id == start_snapshot.run_id
    assert first_snapshot.end_reason is RunEndReason.USER_EXIT
    assert second_snapshot.end_reason is RunEndReason.USER_EXIT
    assert second_snapshot.score == first_snapshot.score

    with Session(engine) as session:
        run_record = RunRepository(session).get(start_snapshot.run_id)

    assert run_record is not None
    assert run_record.end_reason == RunEndReason.USER_EXIT.value


def test_historical_uses_only_eligible_dates(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = GameplayService(engine=engine, provider=MockProvider(), rng=Random(1))

    snapshot = asyncio.run(
        service.start_run(
            GameMode.HISTORICAL,
            candidate_dates=[date(2025, 1, 13), date(2025, 1, 12)],
            total_questions=5,
        )
    )

    assert snapshot.source_date == date(2025, 1, 12)


def test_historical_carries_configured_total_questions_into_next_round(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = GameplayService(engine=engine, provider=MockProvider(), rng=Random(1))

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.HISTORICAL,
            source_date=date(2025, 1, 12),
            total_questions=6,
        )
    )

    for _ in range(start_snapshot.total_questions):
        question = service.snapshot().current_question
        assert question is not None
        asyncio.run(service.submit_answer(question.answer))

    snapshot = service.snapshot()

    assert snapshot.round_index == 1
    assert snapshot.total_questions == 6
    assert snapshot.current_question is not None

    with Session(engine) as session:
        rounds = RoundRepository(session).list_by_run(start_snapshot.run_id)

    assert [round_record.total_questions for round_record in rounds[:2]] == [6, 6]


def test_historical_wrong_answer_keeps_run_active_and_applies_score(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = GameplayService(engine=engine, provider=MockProvider(), rng=Random(5))

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.HISTORICAL,
            source_date=date(2025, 1, 12),
            total_questions=5,
        )
    )
    question = start_snapshot.current_question
    assert question is not None

    wrong_guess = _opposite_guess(question.answer)
    result = asyncio.run(service.submit_answer(wrong_guess, response_time_ms=700))
    snapshot = service.snapshot()

    assert result.is_correct is False
    assert snapshot.is_finished is False
    assert snapshot.wrong_answers == 1
    assert snapshot.score == -60


def test_historical_advances_to_next_game_after_round_completion(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = GameplayService(engine=engine, provider=MockProvider(), rng=Random(1))

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.HISTORICAL,
            source_date=date(2025, 1, 12),
            total_questions=5,
        )
    )
    initial_game_id = start_snapshot.game_id

    for _ in range(start_snapshot.total_questions):
        question = service.snapshot().current_question
        assert question is not None
        asyncio.run(service.submit_answer(question.answer))

    snapshot = service.snapshot()

    assert snapshot.is_finished is False
    assert snapshot.round_index == 1
    assert snapshot.game_id != initial_game_id


def test_historical_ends_after_all_games_for_date_are_consumed(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = GameplayService(engine=engine, provider=MockProvider(), rng=Random(1))

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.HISTORICAL,
            source_date=date(2025, 1, 12),
            total_questions=5,
        )
    )
    total_rounds = len(start_snapshot.games_today)

    for _ in range(total_rounds):
        round_snapshot = service.snapshot()
        for _ in range(round_snapshot.total_questions):
            question = service.snapshot().current_question
            assert question is not None
            asyncio.run(service.submit_answer(question.answer))

    snapshot = service.snapshot()

    assert snapshot.is_finished is True
    assert snapshot.end_reason is RunEndReason.NO_MORE_GAMES
    assert snapshot.round_index == total_rounds - 1
    assert snapshot.current_question is None

    with Session(engine) as session:
        run_record = RunRepository(session).get(start_snapshot.run_id)

    assert run_record is not None
    assert run_record.end_reason == RunEndReason.NO_MORE_GAMES.value


class _TrackingProvider(MockProvider):
    def __init__(self) -> None:
        super().__init__()
        self.in_flight = 0
        self.max_in_flight = 0

    async def get_games_by_date(self, game_date: date) -> list[GameBoxScore]:
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0.001)
            return await super().get_games_by_date(game_date)
        finally:
            self.in_flight -= 1


def test_historical_fetches_are_bounded_by_configured_concurrency(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    provider = _TrackingProvider()
    service = GameplayService(
        engine=engine,
        provider=provider,
        rng=Random(1),
        historical_fetch_concurrency=2,
    )

    snapshot = asyncio.run(
        service.start_run(
            GameMode.HISTORICAL,
            candidate_dates=[
                date(2025, 1, 13),
                date(2025, 1, 13),
                date(2025, 1, 13),
                date(2025, 1, 12),
            ],
            total_questions=5,
        )
    )

    assert snapshot.source_date == date(2025, 1, 12)
    assert provider.max_in_flight <= 2


def test_historical_fetch_concurrency_must_be_positive(tmp_path) -> None:
    engine = _make_engine(tmp_path)

    with pytest.raises(ValueError, match="historical_fetch_concurrency"):
        GameplayService(
            engine=engine,
            provider=MockProvider(),
            historical_fetch_concurrency=0,
        )
