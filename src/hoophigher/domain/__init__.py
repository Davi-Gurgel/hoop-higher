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
from hoophigher.domain.difficulty import classify_question_difficulty, pick_target_difficulty
from hoophigher.domain.round_generator import generate_round
from hoophigher.domain.scoring import (
    ARCADE_CORRECT_POINTS,
    ENDLESS_CORRECT_POINTS,
    ENDLESS_WRONG_POINTS,
    HISTORICAL_CORRECT_POINTS,
    HISTORICAL_WRONG_POINTS,
    calculate_score_delta,
    get_run_end_reason_for_answer,
    is_guess_correct,
)

__all__ = [
    "Difficulty",
    "GameBoxScore",
    "GameMode",
    "generate_round",
    "GuessDirection",
    "is_guess_correct",
    "PlayerLine",
    "pick_target_difficulty",
    "Question",
    "QuestionResult",
    "RoundDefinition",
    "RoundProgress",
    "RunEndReason",
    "RunState",
    "TeamGameInfo",
    "classify_question_difficulty",
    "ARCADE_CORRECT_POINTS",
    "ENDLESS_CORRECT_POINTS",
    "ENDLESS_WRONG_POINTS",
    "HISTORICAL_CORRECT_POINTS",
    "HISTORICAL_WRONG_POINTS",
    "calculate_score_delta",
    "get_run_end_reason_for_answer",
]
