from hoophigher.domain.enums import Difficulty


def classify_question_difficulty(points_a: int, points_b: int) -> Difficulty:
    difference = abs(points_a - points_b)

    if difference >= 10:
        return Difficulty.EASY

    if difference >= 5:
        return Difficulty.MEDIUM

    # A tie is still a valid comparison in the current domain model and should be
    # treated as the hardest bucket available.
    return Difficulty.HARD


def pick_target_difficulty(question_index: int, total_questions: int) -> Difficulty:
    if total_questions < 1:
        raise ValueError("total_questions must be at least 1.")

    if question_index < 0 or question_index >= total_questions:
        raise ValueError("question_index must be within the round bounds.")

    progress = question_index / total_questions
    if progress < (1 / 3):
        return Difficulty.EASY
    if progress < (2 / 3):
        return Difficulty.MEDIUM
    return Difficulty.HARD
