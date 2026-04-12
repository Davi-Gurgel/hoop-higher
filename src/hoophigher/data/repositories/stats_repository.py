from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, select

from hoophigher.data.schema import QuestionRecord, RoundRecord, RunRecord


class StatsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_runs(self) -> list[RunRecord]:
        statement = select(RunRecord).order_by(RunRecord.created_at.desc(), RunRecord.id.desc())
        return list(self.session.exec(statement))

    def count_runs(self) -> int:
        statement = select(func.count(RunRecord.id))
        return int(self.session.exec(statement).one())

    def list_rounds(self) -> list[RoundRecord]:
        statement = select(RoundRecord).order_by(RoundRecord.created_at.asc(), RoundRecord.id.asc())
        return list(self.session.exec(statement))

    def count_rounds(self) -> int:
        statement = select(func.count(RoundRecord.id))
        return int(self.session.exec(statement).one())

    def list_questions(self) -> list[QuestionRecord]:
        statement = select(QuestionRecord).order_by(QuestionRecord.created_at.asc(), QuestionRecord.id.asc())
        return list(self.session.exec(statement))

    def count_questions(self) -> int:
        statement = select(func.count(QuestionRecord.id))
        return int(self.session.exec(statement).one())

    def count_correct_questions(self) -> int:
        statement = select(func.count(QuestionRecord.id)).where(QuestionRecord.is_correct.is_(True))
        return int(self.session.exec(statement).one())

    def count_wrong_questions(self) -> int:
        statement = select(func.count(QuestionRecord.id)).where(QuestionRecord.is_correct.is_(False))
        return int(self.session.exec(statement).one())

    def best_score(self) -> int | None:
        statement = select(func.max(RunRecord.final_score))
        return self.session.exec(statement).one()

    def best_streak(self) -> int | None:
        statement = select(func.max(RunRecord.best_streak))
        return self.session.exec(statement).one()

    def mode_distribution(self) -> dict[str, int]:
        statement = (
            select(RunRecord.mode, func.count(RunRecord.id))
            .group_by(RunRecord.mode)
            .order_by(RunRecord.mode.asc())
        )
        rows = self.session.exec(statement).all()
        return {mode: int(count) for mode, count in rows}

    def leaderboard(self, *, limit: int = 10) -> list[RunRecord]:
        statement = (
            select(RunRecord)
            .order_by(
                RunRecord.final_score.desc(),
                RunRecord.best_streak.desc(),
                RunRecord.correct_answers.desc(),
                RunRecord.created_at.asc(),
                RunRecord.id.asc(),
            )
            .limit(limit)
        )
        return list(self.session.exec(statement))
