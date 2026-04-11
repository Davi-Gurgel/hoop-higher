from __future__ import annotations

from sqlalchemy import update as sql_update
from sqlmodel import Session, select

from hoophigher.data.schema import RoundRecord


class RoundRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, round_record: RoundRecord) -> RoundRecord:
        self.session.add(round_record)
        self.session.flush()
        return round_record

    def update(self, round_record: RoundRecord) -> RoundRecord:
        self.session.add(round_record)
        self.session.flush()
        return round_record

    def update_progress(
        self,
        round_id: int,
        *,
        correct_answers: int,
        wrong_answers: int,
        score_delta: int,
    ) -> None:
        statement = (
            sql_update(RoundRecord)
            .where(RoundRecord.id == round_id)
            .values(
                correct_answers=correct_answers,
                wrong_answers=wrong_answers,
                score_delta=score_delta,
            )
        )
        result = self.session.exec(statement)
        self.session.flush()
        if result.rowcount == 0:
            raise RuntimeError(f"Round record not found for update: {round_id}")

    def get(self, round_id: int) -> RoundRecord | None:
        return self.session.get(RoundRecord, round_id)

    def list_by_run(self, run_id: int) -> list[RoundRecord]:
        statement = select(RoundRecord).where(RoundRecord.run_id == run_id).order_by(RoundRecord.round_index.asc())
        return list(self.session.exec(statement))
