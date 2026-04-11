from __future__ import annotations

from sqlmodel import Session, select

from hoophigher.data.schema import QuestionRecord


class QuestionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, question_record: QuestionRecord) -> QuestionRecord:
        self.session.add(question_record)
        self.session.flush()
        return question_record

    def update(self, question_record: QuestionRecord) -> QuestionRecord:
        self.session.add(question_record)
        self.session.flush()
        return question_record

    def list_by_round(self, round_id: int) -> list[QuestionRecord]:
        statement = select(QuestionRecord).where(QuestionRecord.round_id == round_id).order_by(
            QuestionRecord.question_index.asc()
        )
        return list(self.session.exec(statement))

    def list_by_run(self, run_id: int) -> list[QuestionRecord]:
        statement = select(QuestionRecord).where(QuestionRecord.run_id == run_id).order_by(
            QuestionRecord.created_at.asc()
        )
        return list(self.session.exec(statement))
