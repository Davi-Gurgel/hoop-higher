from __future__ import annotations

from sqlmodel import Session, select

from hoophigher.data.schema import RoundRecord


class RoundRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, round_record: RoundRecord) -> RoundRecord:
        self.session.add(round_record)
        self.session.flush()
        self.session.refresh(round_record)
        return round_record

    def update(self, round_record: RoundRecord) -> RoundRecord:
        round_record = self.session.merge(round_record)
        self.session.flush()
        self.session.refresh(round_record)
        return round_record

    def get(self, round_id: int) -> RoundRecord | None:
        return self.session.get(RoundRecord, round_id)

    def list_by_run(self, run_id: int) -> list[RoundRecord]:
        statement = select(RoundRecord).where(RoundRecord.run_id == run_id).order_by(RoundRecord.round_index.asc())
        return list(self.session.exec(statement))
