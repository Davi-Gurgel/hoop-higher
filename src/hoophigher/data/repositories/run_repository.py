from __future__ import annotations

from sqlmodel import Session, select

from hoophigher.data.schema import RunRecord


class RunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, run: RunRecord) -> RunRecord:
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def update(self, run: RunRecord) -> RunRecord:
        run = self.session.merge(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def get(self, run_id: int) -> RunRecord | None:
        return self.session.get(RunRecord, run_id)

    def list(self, *, limit: int | None = None) -> list[RunRecord]:
        statement = select(RunRecord).order_by(RunRecord.created_at.desc(), RunRecord.id.desc())
        if limit is not None:
            statement = statement.limit(limit)
        return list(self.session.exec(statement))
