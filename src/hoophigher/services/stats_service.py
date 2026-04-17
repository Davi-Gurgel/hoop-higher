from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import Engine

from hoophigher.data.db import session_scope
from hoophigher.data.repositories import StatsRepository


@dataclass(frozen=True, slots=True)
class LeaderboardEntry:
    rank: int
    mode: str
    score: int
    correct_answers: int
    wrong_answers: int
    best_streak: int


@dataclass(frozen=True, slots=True)
class StatsSummary:
    total_runs: int
    total_answered: int
    total_correct: int
    accuracy_percent: float
    best_score: int
    best_streak: int
    mode_distribution: dict[str, int]


class StatsService:
    def __init__(self, *, engine: Engine) -> None:
        self._engine = engine

    def get_summary(self) -> StatsSummary:
        with session_scope(self._engine) as session:
            stats_repo = StatsRepository(session)
            runs = stats_repo.list_runs()

            total_runs = len(runs)
            total_correct = sum(run.correct_answers for run in runs)
            total_answered = sum(run.correct_answers + run.wrong_answers for run in runs)
            accuracy_percent = 0.0 if total_answered == 0 else round((total_correct / total_answered) * 100, 2)
            best_score = stats_repo.best_score() or 0
            best_streak = stats_repo.best_streak() or 0
            mode_distribution = stats_repo.mode_distribution()

        return StatsSummary(
            total_runs=total_runs,
            total_answered=total_answered,
            total_correct=total_correct,
            accuracy_percent=accuracy_percent,
            best_score=best_score,
            best_streak=best_streak,
            mode_distribution=mode_distribution,
        )

    def get_leaderboard(self, *, limit: int = 10) -> list[LeaderboardEntry]:
        with session_scope(self._engine) as session:
            runs = StatsRepository(session).leaderboard(limit=limit)
            return [
                LeaderboardEntry(
                    rank=index + 1,
                    mode=run.mode,
                    score=run.final_score,
                    correct_answers=run.correct_answers,
                    wrong_answers=run.wrong_answers,
                    best_streak=run.best_streak,
                )
                for index, run in enumerate(runs)
            ]
