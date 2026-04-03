from hoophigher.domain.enums import GameMode, GuessDirection, RunEndReason
from hoophigher.domain.models import Question

ENDLESS_CORRECT_POINTS = 100
ENDLESS_WRONG_POINTS = -60
ARCADE_CORRECT_POINTS = 150


def is_guess_correct(question: Question, guess: GuessDirection) -> bool:
    return guess == question.answer


def calculate_score_delta(mode: GameMode, *, is_correct: bool) -> int:
    if mode is GameMode.ENDLESS:
        return ENDLESS_CORRECT_POINTS if is_correct else ENDLESS_WRONG_POINTS

    if mode is GameMode.ARCADE:
        return ARCADE_CORRECT_POINTS if is_correct else 0

    raise ValueError(f"Scoring is not configured for mode: {mode.value}")


def get_run_end_reason_for_answer(mode: GameMode, *, is_correct: bool) -> RunEndReason | None:
    if mode is GameMode.ARCADE and not is_correct:
        return RunEndReason.WRONG_ANSWER

    if mode is GameMode.ENDLESS:
        return None

    if mode is GameMode.ARCADE:
        return None

    raise ValueError(f"Run end behavior is not configured for mode: {mode.value}")
