from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.engine import Engine

from hoophigher.data.db import session_scope
from hoophigher.data.repositories import StatsRepository
from hoophigher.domain.enums import GameMode


@dataclass(frozen=True, slots=True)
class LeaderboardRow:
    rank: int
    mode: GameMode
    score: int
    best_streak: int
    correct_answers: int
    source_date: date | None
    created_at: datetime

    @property
    def source_date_label(self) -> str:
        return self.source_date.isoformat() if self.source_date is not None else "--"


@dataclass(frozen=True, slots=True)
class LeaderboardResult:
    rows: tuple[LeaderboardRow, ...]

    @property
    def is_empty(self) -> bool:
        return len(self.rows) == 0


class LeaderboardService:
    def __init__(self, *, engine: Engine) -> None:
        self._engine = engine

    def get_leaderboard(self, *, limit: int = 10) -> LeaderboardResult:
        if limit <= 0:
            raise ValueError("limit must be a positive integer.")
        with session_scope(self._engine) as session:
            records = StatsRepository(session).leaderboard(limit=limit)
            rows = tuple(
                LeaderboardRow(
                    rank=index,
                    mode=GameMode(record.mode),
                    score=record.final_score,
                    best_streak=record.best_streak,
                    correct_answers=record.correct_answers,
                    source_date=record.source_date,
                    created_at=record.created_at,
                )
                for index, record in enumerate(records, start=1)
            )
        return LeaderboardResult(rows=rows)
