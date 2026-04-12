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
