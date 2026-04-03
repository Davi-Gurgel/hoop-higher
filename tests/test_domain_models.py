from datetime import date

import pytest

from hoophigher.domain import (
    Difficulty,
    GameBoxScore,
    GameMode,
    GuessDirection,
    PlayerLine,
    Question,
    QuestionResult,
    RoundDefinition,
    RunEndReason,
    RunState,
    TeamGameInfo,
)


def make_player(*, player_id: str, points: int, minutes: int = 30) -> PlayerLine:
    return PlayerLine(
        player_id=player_id,
        player_name=f"Player {player_id}",
        team_id="team-1",
        team_abbreviation="T1",
        points=points,
        minutes=minutes,
    )


def make_game(*, players: tuple[PlayerLine, ...]) -> GameBoxScore:
    return GameBoxScore(
        game_id="game-1",
        game_date=date(2025, 1, 10),
        home_team=TeamGameInfo(team_id="home", name="Home", abbreviation="HOM", score=100),
        away_team=TeamGameInfo(team_id="away", name="Away", abbreviation="AWY", score=98),
        player_lines=players,
    )


def make_round_definition() -> RoundDefinition:
    players = tuple(make_player(player_id=str(index), points=10 + index) for index in range(6))
    game = make_game(players=players)
    questions = tuple(
        Question(player_a=players[index], player_b=players[index + 1], difficulty=Difficulty.MEDIUM)
        for index in range(5)
    )
    return RoundDefinition(game=game, questions=questions)


def test_player_line_eligibility_depends_on_minutes() -> None:
    active_player = make_player(player_id="1", points=20, minutes=18)
    inactive_player = make_player(player_id="2", points=20, minutes=0)

    assert active_player.is_eligible is True
    assert inactive_player.is_eligible is False


def test_game_box_score_filters_eligible_players() -> None:
    eligible_player = make_player(player_id="1", points=18, minutes=24)
    ineligible_player = make_player(player_id="2", points=12, minutes=0)
    game = make_game(players=(eligible_player, ineligible_player))

    assert game.eligible_player_lines == (eligible_player,)


def test_question_answer_is_higher_when_player_b_scores_more() -> None:
    question = Question(
        player_a=make_player(player_id="1", points=20),
        player_b=make_player(player_id="2", points=24),
        difficulty=Difficulty.HARD,
    )

    assert question.answer is GuessDirection.HIGHER
    assert question.point_difference == 4


def test_question_rejects_duplicate_players() -> None:
    player = make_player(player_id="1", points=20)

    with pytest.raises(ValueError, match="different"):
        Question(player_a=player, player_b=player, difficulty=Difficulty.EASY)


def test_question_rejects_tied_scores() -> None:
    with pytest.raises(ValueError, match="tied points"):
        Question(
            player_a=make_player(player_id="1", points=20),
            player_b=make_player(player_id="2", points=20),
            difficulty=Difficulty.HARD,
        )


def test_round_definition_requires_question_count_between_five_and_ten() -> None:
    players = tuple(make_player(player_id=str(index), points=10 + index) for index in range(4))
    game = make_game(players=players)
    questions = tuple(
        Question(player_a=players[0], player_b=players[1], difficulty=Difficulty.EASY)
        for _ in range(4)
    )

    with pytest.raises(ValueError, match="between 5 and 10"):
        RoundDefinition(game=game, questions=questions)


def test_run_state_tracks_score_and_streaks() -> None:
    round_definition = make_round_definition()
    run_state = RunState(mode=GameMode.ENDLESS)
    round_progress = run_state.start_round(round_definition)

    first_question = round_progress.current_question
    assert first_question is not None
    first_result = QuestionResult(
        question=first_question,
        guess=GuessDirection.HIGHER,
        is_correct=True,
        score_delta=100,
        revealed_points=11,
    )
    run_state.apply_result(first_result)

    second_question = round_progress.current_question
    assert second_question is not None
    second_result = QuestionResult(
        question=second_question,
        guess=GuessDirection.LOWER,
        is_correct=False,
        score_delta=-60,
        revealed_points=12,
    )
    run_state.apply_result(second_result, end_reason=RunEndReason.WRONG_ANSWER)

    assert run_state.score == 40
    assert run_state.correct_answers == 1
    assert run_state.wrong_answers == 1
    assert run_state.total_answers == 2
    assert run_state.best_streak == 1
    assert run_state.current_streak == 0
    assert run_state.end_reason is RunEndReason.WRONG_ANSWER


def test_run_state_requires_active_round_before_applying_result() -> None:
    run_state = RunState(mode=GameMode.ARCADE)
    question = Question(
        player_a=make_player(player_id="1", points=10),
        player_b=make_player(player_id="2", points=12),
        difficulty=Difficulty.EASY,
    )
    result = QuestionResult(
        question=question,
        guess=GuessDirection.HIGHER,
        is_correct=True,
        score_delta=150,
        revealed_points=12,
    )

    with pytest.raises(ValueError, match="active round"):
        run_state.apply_result(result)
