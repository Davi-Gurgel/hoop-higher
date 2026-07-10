from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.engine import Engine

from hoophigher.data.db import session_scope
from hoophigher.data.repositories import QuestionRepository, RoundRepository, RunRepository
from hoophigher.data.schema import QuestionRecord, RoundRecord, RunRecord
from hoophigher.domain.enums import GameMode


@dataclass(frozen=True, slots=True)
class RunHistoryRow:
    run_id: int
    mode: GameMode
    score: int
    best_streak: int
    correct_answers: int
    wrong_answers: int
    source_date: date | None


@dataclass(frozen=True, slots=True)
class QuestionHistory:
    question_index: int
    player_a_name: str
    player_a_team_abbreviation: str
    player_a_points: int
    player_b_name: str
    player_b_team_abbreviation: str
    revealed_points: int
    guess: str | None
    is_correct: bool
    score_delta: int


@dataclass(frozen=True, slots=True)
class RoundHistory:
    round_index: int
    game_id: str
    game_date: date
    correct_answers: int
    wrong_answers: int
    score_delta: int
    questions: tuple[QuestionHistory, ...]


@dataclass(frozen=True, slots=True)
class RunHistoryDetail:
    run: RunHistoryRow
    rounds: tuple[RoundHistory, ...]


class RunHistoryService:
    """Read locally persisted Runs and their completed Question Results."""

    def __init__(self, *, engine: Engine) -> None:
        self._engine = engine

    def list_runs(self) -> tuple[RunHistoryRow, ...]:
        with session_scope(self._engine) as session:
            runs = RunRepository(session).list()
            return tuple(self._to_run_row(run) for run in runs)

    def get_run(self, run_id: int) -> RunHistoryDetail | None:
        with session_scope(self._engine) as session:
            run = RunRepository(session).get(run_id)
            if run is None:
                return None

            run_row = self._to_run_row(run)
            question_repository = QuestionRepository(session)
            rounds = tuple(
                self._to_round_history(round_record, question_repository)
                for round_record in RoundRepository(session).list_by_run(run_row.run_id)
            )
            return RunHistoryDetail(run=run_row, rounds=rounds)

    @staticmethod
    def _to_run_row(run: RunRecord) -> RunHistoryRow:
        assert run.id is not None
        return RunHistoryRow(
            run_id=run.id,
            mode=GameMode(run.mode),
            score=run.final_score,
            best_streak=run.best_streak,
            correct_answers=run.correct_answers,
            wrong_answers=run.wrong_answers,
            source_date=run.source_date,
        )

    @staticmethod
    def _to_round_history(
        round_record: RoundRecord,
        question_repository: QuestionRepository,
    ) -> RoundHistory:
        assert round_record.id is not None
        return RoundHistory(
            round_index=round_record.round_index,
            game_id=round_record.game_id,
            game_date=round_record.game_date,
            correct_answers=round_record.correct_answers,
            wrong_answers=round_record.wrong_answers,
            score_delta=round_record.score_delta,
            questions=tuple(
                RunHistoryService._to_question_history(question)
                for question in question_repository.list_by_round(round_record.id)
            ),
        )

    @staticmethod
    def _to_question_history(question: QuestionRecord) -> QuestionHistory:
        return QuestionHistory(
            question_index=question.question_index,
            player_a_name=question.player_a_name,
            player_a_team_abbreviation=question.player_a_team_abbreviation,
            player_a_points=question.player_a_points,
            player_b_name=question.player_b_name,
            player_b_team_abbreviation=question.player_b_team_abbreviation,
            revealed_points=question.revealed_points,
            guess=question.guess,
            is_correct=question.is_correct,
            score_delta=question.score_delta,
        )
