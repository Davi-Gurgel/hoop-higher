from enum import StrEnum


def _title_label(value: str) -> str:
    return value.replace("_", " ").title()


class GameMode(StrEnum):
    ENDLESS = "endless"
    ARCADE = "arcade"
    HISTORICAL = "historical"

    @property
    def label(self) -> str:
        return _title_label(self.value)


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class GuessDirection(StrEnum):
    HIGHER = "higher"
    LOWER = "lower"


class RunEndReason(StrEnum):
    USER_EXIT = "user_exit"
    # The "wrong_answer" string value is persisted in runs.end_reason; keep it
    # for existing databases while the Python identifier follows the glossary.
    WRONG_GUESS = "wrong_answer"
    NO_MORE_GAMES = "no_more_games"

    @property
    def label(self) -> str:
        return _title_label(self.value)
