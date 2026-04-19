from __future__ import annotations

from datetime import date, datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RunRecord(SQLModel, table=True):
    __tablename__ = "runs"

    id: int | None = Field(default=None, primary_key=True)
    mode: str = Field(index=True)
    source_date: date | None = Field(default=None, index=True)
    final_score: int = Field(default=0, index=True)
    correct_answers: int = Field(default=0)
    wrong_answers: int = Field(default=0)
    best_streak: int = Field(default=0, index=True)
    end_reason: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=_utcnow, index=True)


class RoundRecord(SQLModel, table=True):
    __tablename__ = "rounds"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(index=True, foreign_key="runs.id")
    round_index: int = Field(default=0, index=True)
    game_id: str = Field(index=True)
    game_date: date = Field(index=True)
    total_questions: int = Field(default=0)
    correct_answers: int = Field(default=0)
    wrong_answers: int = Field(default=0)
    score_delta: int = Field(default=0)
    created_at: datetime = Field(default_factory=_utcnow, index=True)


class QuestionRecord(SQLModel, table=True):
    __tablename__ = "questions"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(index=True, foreign_key="runs.id")
    round_id: int = Field(index=True, foreign_key="rounds.id")
    question_index: int = Field(default=0, index=True)
    player_a_id: str = Field(index=True)
    player_a_name: str
    player_a_team_id: str = Field(index=True)
    player_a_team_abbreviation: str
    player_a_points: int
    player_a_minutes: int
    player_b_id: str = Field(index=True)
    player_b_name: str
    player_b_team_id: str = Field(index=True)
    player_b_team_abbreviation: str
    player_b_points: int
    player_b_minutes: int
    difficulty: str = Field(index=True)
    guess: str | None = Field(default=None, index=True)
    is_correct: bool = Field(default=False, index=True)
    score_delta: int = Field(default=0)
    revealed_points: int = Field(default=0)
    response_time_ms: int | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=_utcnow, index=True)


class CachedGameRecord(SQLModel, table=True):
    __tablename__ = "cached_games"

    game_date: date = Field(primary_key=True, index=True)
    payload_json: str
    cached_at: datetime = Field(default_factory=_utcnow, index=True)


class CachedGameStatsRecord(SQLModel, table=True):
    __tablename__ = "cached_game_stats"

    game_id: str = Field(primary_key=True, index=True)
    payload_json: str
    cached_at: datetime = Field(default_factory=_utcnow, index=True)


class HistoricalEligibleDateRecord(SQLModel, table=True):
    __tablename__ = "historical_eligible_dates"

    start_year: int = Field(primary_key=True)
    end_year: int = Field(primary_key=True)
    min_games: int = Field(primary_key=True)
    game_date: date = Field(primary_key=True)
    game_count: int = Field(index=True)
    updated_at: datetime = Field(default_factory=_utcnow, index=True)
