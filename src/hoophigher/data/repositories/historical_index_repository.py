from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import delete
from sqlmodel import Session, select

from hoophigher.data.schema import HistoricalEligibleDateRecord


class HistoricalIndexRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_window(
        self,
        *,
        start_year: int,
        end_year: int,
        min_games: int,
        rows: Sequence[tuple[date, int]],
    ) -> None:
        for game_date, game_count in rows:
            if game_count < min_games:
                raise ValueError(
                    "historical eligible date row has game_count below min_games "
                    f"(date={game_date}, game_count={game_count}, min_games={min_games})"
                )

        delete_statement = delete(HistoricalEligibleDateRecord).where(
            HistoricalEligibleDateRecord.start_year == start_year,
            HistoricalEligibleDateRecord.end_year == end_year,
            HistoricalEligibleDateRecord.min_games == min_games,
        )
        self.session.exec(delete_statement)

        for game_date, game_count in rows:
            self.session.add(
                HistoricalEligibleDateRecord(
                    game_date=game_date,
                    start_year=start_year,
                    end_year=end_year,
                    min_games=min_games,
                    game_count=game_count,
                )
            )

        self.session.flush()

    def list_window_dates(self, *, start_year: int, end_year: int, min_games: int) -> list[date]:
        statement = (
            select(HistoricalEligibleDateRecord)
            .where(
                HistoricalEligibleDateRecord.start_year == start_year,
                HistoricalEligibleDateRecord.end_year == end_year,
                HistoricalEligibleDateRecord.min_games == min_games,
            )
            .order_by(HistoricalEligibleDateRecord.game_date.asc())
        )
        rows = self.session.exec(statement)
        return [row.game_date for row in rows]
