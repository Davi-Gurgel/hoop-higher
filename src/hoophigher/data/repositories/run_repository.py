from __future__ import annotations

from sqlalchemy import update as sql_update
from sqlmodel import Session, select

from hoophigher.data.schema import RunRecord


class RunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, run: RunRecord) -> RunRecord:
        self.session.add(run)
        self.session.flush()
        return run

    def update(self, run: RunRecord) -> RunRecord:
        self.session.add(run)
        self.session.flush()
        return run

    def update_progress(
        self,
        run_id: int,
        *,
        final_score: int,
        correct_answers: int,
        wrong_answers: int,
        best_streak: int,
        end_reason: str | None,
    ) -> None:
        statement = (
            sql_update(RunRecord)
            .where(RunRecord.id == run_id)
            .values(
                final_score=final_score,
                correct_answers=correct_answers,
                wrong_answers=wrong_answers,
                best_streak=best_streak,
                end_reason=end_reason,
            )
        )
        result = self.session.exec(statement)
        self.session.flush()
        if result.rowcount == 0:
            raise RuntimeError(f"Run record not found for update: {run_id}")

    def get(self, run_id: int) -> RunRecord | None:
        return self.session.get(RunRecord, run_id)

    def list(self, *, limit: int | None = None) -> list[RunRecord]:
        statement = select(RunRecord).order_by(RunRecord.created_at.desc(), RunRecord.id.desc())
        if limit is not None:
            statement = statement.limit(limit)
        return list(self.session.exec(statement))
