import pytest

from hoophigher.domain import (
    ARCADE_CORRECT_POINTS,
    ENDLESS_CORRECT_POINTS,
    ENDLESS_WRONG_POINTS,
    Difficulty,
    GameMode,
    GuessDirection,
    PlayerLine,
    Question,
    RunEndReason,
    calculate_score_delta,
    get_run_end_reason_for_answer,
    is_guess_correct,
)


def make_question(*, points_a: int, points_b: int) -> Question:
    return Question(
        player_a=PlayerLine(
            player_id="player-a",
            player_name="Player A",
            team_id="team-a",
            team_abbreviation="TA",
            points=points_a,
            minutes=30,
        ),
        player_b=PlayerLine(
            player_id="player-b",
            player_name="Player B",
            team_id="team-b",
            team_abbreviation="TB",
            points=points_b,
            minutes=32,
        ),
        difficulty=Difficulty.MEDIUM,
    )


def test_is_guess_correct_matches_question_answer() -> None:
    question = make_question(points_a=21, points_b=24)

    assert is_guess_correct(question, GuessDirection.HIGHER) is True
    assert is_guess_correct(question, GuessDirection.LOWER) is False


def test_calculate_score_delta_for_endless_mode() -> None:
    assert calculate_score_delta(GameMode.ENDLESS, is_correct=True) == ENDLESS_CORRECT_POINTS
    assert calculate_score_delta(GameMode.ENDLESS, is_correct=False) == ENDLESS_WRONG_POINTS


def test_calculate_score_delta_for_arcade_mode() -> None:
    assert calculate_score_delta(GameMode.ARCADE, is_correct=True) == ARCADE_CORRECT_POINTS
    assert calculate_score_delta(GameMode.ARCADE, is_correct=False) == 0


def test_get_run_end_reason_for_arcade_wrong_answer() -> None:
    assert get_run_end_reason_for_answer(GameMode.ARCADE, is_correct=False) is RunEndReason.WRONG_ANSWER


def test_get_run_end_reason_for_non_ending_answers() -> None:
    assert get_run_end_reason_for_answer(GameMode.ARCADE, is_correct=True) is None
    assert get_run_end_reason_for_answer(GameMode.ENDLESS, is_correct=True) is None
    assert get_run_end_reason_for_answer(GameMode.ENDLESS, is_correct=False) is None


def test_scoring_raises_for_unsupported_modes() -> None:
    with pytest.raises(ValueError, match="not configured"):
        calculate_score_delta(GameMode.HISTORICAL, is_correct=True)

    with pytest.raises(ValueError, match="not configured"):
        get_run_end_reason_for_answer(GameMode.YESTERDAY, is_correct=True)
