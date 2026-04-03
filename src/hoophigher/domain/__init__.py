"""Domain layer for pure game rules and models."""

from hoophigher.domain.enums import Difficulty, GameMode, GuessDirection, RunEndReason
from hoophigher.domain.models import (
    GameBoxScore,
    PlayerLine,
    Question,
    QuestionResult,
    RoundDefinition,
    RoundProgress,
    RunState,
    TeamGameInfo,
)
from hoophigher.domain.scoring import (
    ARCADE_CORRECT_POINTS,
    ENDLESS_CORRECT_POINTS,
    ENDLESS_WRONG_POINTS,
    calculate_score_delta,
    get_run_end_reason_for_answer,
    is_guess_correct,
)

__all__ = [
    "Difficulty",
    "GameBoxScore",
    "GameMode",
    "GuessDirection",
    "is_guess_correct",
    "PlayerLine",
    "Question",
    "QuestionResult",
    "RoundDefinition",
    "RoundProgress",
    "RunEndReason",
    "RunState",
    "TeamGameInfo",
    "ARCADE_CORRECT_POINTS",
    "ENDLESS_CORRECT_POINTS",
    "ENDLESS_WRONG_POINTS",
    "calculate_score_delta",
    "get_run_end_reason_for_answer",
]
