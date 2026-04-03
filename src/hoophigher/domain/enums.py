from enum import StrEnum


class GameMode(StrEnum):
    ENDLESS = "endless"
    ARCADE = "arcade"
    HISTORICAL = "historical"
    YESTERDAY = "yesterday"


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class GuessDirection(StrEnum):
    HIGHER = "higher"
    LOWER = "lower"


class RunEndReason(StrEnum):
    USER_EXIT = "user_exit"
    WRONG_ANSWER = "wrong_answer"
    NO_MORE_GAMES = "no_more_games"
    NO_MORE_QUESTIONS = "no_more_questions"
