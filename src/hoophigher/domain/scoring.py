from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from hoophigher.domain.enums import GameMode, GuessDirection, RunEndReason
from hoophigher.domain.models import Question


@dataclass(frozen=True, slots=True)
class ScoringPolicy:
    correct_score_delta: int
    wrong_score_delta: int
    correct_guess_end_reason: RunEndReason | None = None
    wrong_guess_end_reason: RunEndReason | None = None


SCORING_POLICIES: Mapping[GameMode, ScoringPolicy] = MappingProxyType(
    {
        GameMode.ENDLESS: ScoringPolicy(
            correct_score_delta=100,
            wrong_score_delta=-60,
            correct_guess_end_reason=None,
        ),
        GameMode.ARCADE: ScoringPolicy(
            correct_score_delta=150,
            wrong_score_delta=0,
            correct_guess_end_reason=None,
            wrong_guess_end_reason=RunEndReason.WRONG_GUESS,
        ),
        GameMode.HISTORICAL: ScoringPolicy(
            correct_score_delta=100,
            wrong_score_delta=-60,
            correct_guess_end_reason=None,
        ),
    }
)

# Keep the named values available to callers while deriving them from the policy table.
ENDLESS_CORRECT_POINTS = SCORING_POLICIES[GameMode.ENDLESS].correct_score_delta
ENDLESS_WRONG_POINTS = SCORING_POLICIES[GameMode.ENDLESS].wrong_score_delta
ARCADE_CORRECT_POINTS = SCORING_POLICIES[GameMode.ARCADE].correct_score_delta
HISTORICAL_CORRECT_POINTS = SCORING_POLICIES[GameMode.HISTORICAL].correct_score_delta
HISTORICAL_WRONG_POINTS = SCORING_POLICIES[GameMode.HISTORICAL].wrong_score_delta


def _scoring_policy_for(mode: GameMode) -> ScoringPolicy:
    try:
        return SCORING_POLICIES[mode]
    except KeyError as error:
        raise ValueError(f"Scoring is not configured for mode: {mode.value}") from error


def is_guess_correct(question: Question, guess: GuessDirection) -> bool:
    return guess == question.correct_guess


def calculate_score_delta(mode: GameMode, *, is_correct: bool) -> int:
    policy = _scoring_policy_for(mode)
    return policy.correct_score_delta if is_correct else policy.wrong_score_delta


def get_run_end_reason_for_guess(mode: GameMode, *, is_correct: bool) -> RunEndReason | None:
    policy = _scoring_policy_for(mode)
    return policy.correct_guess_end_reason if is_correct else policy.wrong_guess_end_reason
