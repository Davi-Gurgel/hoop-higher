from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import Engine

from hoophigher.data.db import session_scope
from hoophigher.data.repositories import StatsRepository
from hoophigher.domain.enums import GameMode


@dataclass(frozen=True, slots=True)
class ModeStatsRow:
    mode: GameMode
    count: int

    @property
    def mode_label(self) -> str:
        return self.mode.value.replace("_", " ").title()


@dataclass(frozen=True, slots=True)
class StatsResult:
    total_runs: int
    total_answered_questions: int
    total_correct_answers: int
    accuracy_rate: float
    best_score: int
    best_streak: int
    mode_distribution: tuple[ModeStatsRow, ...]


class StatsService:
    def __init__(self, *, engine: Engine) -> None:
        self._engine = engine

    def get_stats(self) -> StatsResult:
        with session_scope(self._engine) as session:
            repository = StatsRepository(session)
            total_runs = repository.count_runs()
            total_answered_questions = repository.count_questions()
            total_correct_answers = repository.count_correct_questions()
            repository_best_score = repository.best_score()
            best_score = 0 if repository_best_score is None else repository_best_score
            best_streak = repository.best_streak() or 0
            mode_distribution = tuple(
                ModeStatsRow(mode=GameMode(mode), count=count)
                for mode, count in repository.mode_distribution().items()
            )

        accuracy_rate = (
            total_correct_answers / total_answered_questions
            if total_answered_questions > 0
            else 0.0
        )
        return StatsResult(
            total_runs=total_runs,
            total_answered_questions=total_answered_questions,
            total_correct_answers=total_correct_answers,
            accuracy_rate=accuracy_rate,
            best_score=best_score,
            best_streak=best_streak,
            mode_distribution=mode_distribution,
        )
