from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from hoophigher.domain.enums import Difficulty, GameMode, GuessDirection, RunEndReason


@dataclass(frozen=True, slots=True)
class TeamGameInfo:
    team_id: str
    name: str
    abbreviation: str
    score: int | None = None


@dataclass(frozen=True, slots=True)
class PlayerLine:
    player_id: str
    player_name: str
    team_id: str
    team_abbreviation: str
    points: int
    minutes: int

    @property
    def is_eligible(self) -> bool:
        return self.minutes > 0


@dataclass(frozen=True, slots=True)
class GameBoxScore:
    game_id: str
    game_date: date
    home_team: TeamGameInfo
    away_team: TeamGameInfo
    player_lines: tuple[PlayerLine, ...]

    @property
    def eligible_player_lines(self) -> tuple[PlayerLine, ...]:
        return tuple(player for player in self.player_lines if player.is_eligible)


@dataclass(frozen=True, slots=True)
class Question:
    player_a: PlayerLine
    player_b: PlayerLine
    difficulty: Difficulty

    def __post_init__(self) -> None:
        if self.player_a.player_id == self.player_b.player_id:
            raise ValueError("Question players must be different.")
        if self.player_a.points == self.player_b.points:
            raise ValueError("Question players must not have tied points.")

    @property
    def answer(self) -> GuessDirection:
        if self.player_b.points > self.player_a.points:
            return GuessDirection.HIGHER

        return GuessDirection.LOWER

    @property
    def point_difference(self) -> int:
        return abs(self.player_a.points - self.player_b.points)


@dataclass(frozen=True, slots=True)
class QuestionResult:
    question: Question
    guess: GuessDirection
    is_correct: bool
    score_delta: int
    revealed_points: int
    response_time_ms: int | None = None


@dataclass(frozen=True, slots=True)
class RoundDefinition:
    game: GameBoxScore
    questions: tuple[Question, ...]

    def __post_init__(self) -> None:
        question_count = len(self.questions)
        if question_count < 5 or question_count > 10:
            raise ValueError("RoundDefinition must contain between 5 and 10 questions.")


@dataclass(slots=True)
class RoundProgress:
    round_definition: RoundDefinition
    current_index: int = 0
    results: list[QuestionResult] = field(default_factory=list)

    @property
    def current_question(self) -> Question | None:
        if self.current_index >= len(self.round_definition.questions):
            return None

        return self.round_definition.questions[self.current_index]

    @property
    def is_complete(self) -> bool:
        return self.current_index >= len(self.round_definition.questions)

    def record_result(self, result: QuestionResult) -> None:
        if self.is_complete:
            raise ValueError("Cannot record result for a completed round.")

        expected_question = self.current_question
        if expected_question is None or result.question != expected_question:
            raise ValueError("QuestionResult does not match the current question.")

        self.results.append(result)
        self.current_index += 1


@dataclass(slots=True)
class RunState:
    mode: GameMode
    rounds: list[RoundProgress] = field(default_factory=list)
    score: int = 0
    current_streak: int = 0
    best_streak: int = 0
    correct_answers: int = 0
    wrong_answers: int = 0
    end_reason: RunEndReason | None = None
    source_date: date | None = None

    @property
    def total_answers(self) -> int:
        return self.correct_answers + self.wrong_answers

    @property
    def is_finished(self) -> bool:
        return self.end_reason is not None

    @property
    def current_round(self) -> RoundProgress | None:
        if not self.rounds:
            return None

        return self.rounds[-1]

    def start_round(self, round_definition: RoundDefinition) -> RoundProgress:
        if self.is_finished:
            raise ValueError("Cannot start a round for a finished run.")

        round_progress = RoundProgress(round_definition=round_definition)
        self.rounds.append(round_progress)
        return round_progress

    def apply_result(self, result: QuestionResult, *, end_reason: RunEndReason | None = None) -> None:
        round_progress = self.current_round
        if round_progress is None:
            raise ValueError("Cannot apply a result without an active round.")

        round_progress.record_result(result)
        self.score += result.score_delta

        if result.is_correct:
            self.correct_answers += 1
            self.current_streak += 1
            self.best_streak = max(self.best_streak, self.current_streak)
        else:
            self.wrong_answers += 1
            self.current_streak = 0

        if end_reason is not None:
            self.end_reason = end_reason
