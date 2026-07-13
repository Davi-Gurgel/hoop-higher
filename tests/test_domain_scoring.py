import pytest

from hoophigher.domain import (
    Difficulty,
    GameMode,
    GuessDirection,
    PlayerLine,
    Question,
    RunEndReason,
    SCORING_POLICIES,
    calculate_score_delta,
    get_run_end_reason_for_guess,
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


def test_is_guess_correct_matches_question_correct_guess() -> None:
    question = make_question(points_a=21, points_b=24)

    assert is_guess_correct(question, GuessDirection.HIGHER) is True
    assert is_guess_correct(question, GuessDirection.LOWER) is False


@pytest.mark.parametrize(
    ("mode", "is_correct", "expected_delta"),
    [
        (GameMode.ENDLESS, True, 100),
        (GameMode.ENDLESS, False, -60),
        (GameMode.ARCADE, True, 150),
        (GameMode.ARCADE, False, 0),
        (GameMode.HISTORICAL, True, 100),
        (GameMode.HISTORICAL, False, -60),
    ],
)
def test_calculate_score_delta_for_each_mode(mode, is_correct, expected_delta) -> None:
    assert calculate_score_delta(mode, is_correct=is_correct) == expected_delta


@pytest.mark.parametrize(
    ("mode", "is_correct", "expected_end_reason"),
    [
        (GameMode.ENDLESS, True, None),
        (GameMode.ENDLESS, False, None),
        (GameMode.ARCADE, True, None),
        (GameMode.ARCADE, False, RunEndReason.WRONG_GUESS),
        (GameMode.HISTORICAL, True, None),
        (GameMode.HISTORICAL, False, None),
    ],
)
def test_get_run_end_reason_for_each_mode(mode, is_correct, expected_end_reason) -> None:
    assert get_run_end_reason_for_guess(mode, is_correct=is_correct) is expected_end_reason


def test_scoring_policy_table_covers_every_mode() -> None:
    assert set(SCORING_POLICIES) == set(GameMode)
