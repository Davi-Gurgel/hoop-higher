import pytest

from hoophigher.domain import Difficulty, classify_question_difficulty, pick_target_difficulty


@pytest.mark.parametrize(
    ("points_a", "points_b", "expected"),
    [
        (10, 20, Difficulty.EASY),
        (20, 11, Difficulty.MEDIUM),
        (20, 17, Difficulty.HARD),
        (20, 20, Difficulty.HARD),
    ],
)
def test_classify_question_difficulty(points_a: int, points_b: int, expected: Difficulty) -> None:
    assert classify_question_difficulty(points_a, points_b) is expected


def test_pick_target_difficulty_progression() -> None:
    assert pick_target_difficulty(0, 6) is Difficulty.EASY
    assert pick_target_difficulty(1, 6) is Difficulty.EASY
    assert pick_target_difficulty(2, 6) is Difficulty.MEDIUM
    assert pick_target_difficulty(3, 6) is Difficulty.MEDIUM
    assert pick_target_difficulty(4, 6) is Difficulty.HARD
    assert pick_target_difficulty(5, 6) is Difficulty.HARD


def test_pick_target_difficulty_validates_bounds() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        pick_target_difficulty(0, 0)

    with pytest.raises(ValueError, match="within the round bounds"):
        pick_target_difficulty(5, 5)
