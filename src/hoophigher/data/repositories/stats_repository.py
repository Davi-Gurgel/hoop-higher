from __future__ import annotations

from collections import Counter

from sqlmodel import Session, select

from hoophigher.data.schema import QuestionRecord, RoundRecord, RunRecord


class StatsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_runs(self) -> list[RunRecord]:
        statement = select(RunRecord).order_by(RunRecord.created_at.desc(), RunRecord.id.desc())
        return list(self.session.exec(statement))

    def count_runs(self) -> int:
        return len(self.list_runs())

    def list_rounds(self) -> list[RoundRecord]:
        statement = select(RoundRecord).order_by(RoundRecord.created_at.asc(), RoundRecord.id.asc())
        return list(self.session.exec(statement))

    def count_rounds(self) -> int:
        return len(self.list_rounds())

    def list_questions(self) -> list[QuestionRecord]:
        statement = select(QuestionRecord).order_by(QuestionRecord.created_at.asc(), QuestionRecord.id.asc())
        return list(self.session.exec(statement))

    def count_questions(self) -> int:
        return len(self.list_questions())

    def count_correct_questions(self) -> int:
        return sum(1 for question in self.list_questions() if question.is_correct)

    def count_wrong_questions(self) -> int:
        return sum(1 for question in self.list_questions() if not question.is_correct)

    def best_score(self) -> int | None:
        runs = self.list_runs()
        if not runs:
            return None
        return max(run.final_score for run in runs)

    def best_streak(self) -> int | None:
        runs = self.list_runs()
        if not runs:
            return None
        return max(run.best_streak for run in runs)

    def mode_distribution(self) -> dict[str, int]:
        counter = Counter(run.mode for run in self.list_runs())
        return dict(sorted(counter.items()))

    def leaderboard(self, *, limit: int = 10) -> list[RunRecord]:
        runs = sorted(
            self.list_runs(),
            key=lambda run: (
                -run.final_score,
                -run.best_streak,
                -run.correct_answers,
                run.created_at,
                run.id or 0,
            ),
        )
        return runs[:limit]
