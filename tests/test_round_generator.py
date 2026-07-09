from datetime import date
from random import Random

import pytest

from hoophigher.domain import (
    Difficulty,
    NBAGame,
    PlayerLine,
    RoundDefinition,
    TeamGameInfo,
    generate_round,
)


def make_player(player_id: str, points: int, minutes: int = 24) -> PlayerLine:
    return PlayerLine(
        player_id=player_id,
        player_name=f"Player {player_id}",
        team_id=f"team-{player_id}",
        team_abbreviation=player_id.upper(),
        points=points,
        minutes=minutes,
    )


def make_game(players: tuple[PlayerLine, ...]) -> NBAGame:
    return NBAGame(
        game_id="game-42",
        source_date=date(2025, 2, 1),
        home_team=TeamGameInfo(team_id="home", name="Home", abbreviation="HOM", score=110),
        away_team=TeamGameInfo(team_id="away", name="Away", abbreviation="AWY", score=104),
        player_lines=players,
    )


def test_generate_round_keeps_previous_hidden_player_on_left_without_reusing_hidden_targets() -> (
    None
):
    game = make_game(
        (
            make_player("a", 30),
            make_player("b", 18),
            make_player("c", 24),
            make_player("d", 11),
            make_player("e", 28),
            make_player("f", 16),
        )
    )

    round_definition = generate_round(game, total_questions=5)

    assert isinstance(round_definition, RoundDefinition)
    assert len(round_definition.questions) == 5
    seen_matchups: set[frozenset[str]] = set()
    seen_players: set[str] = set()

    for index, question in enumerate(round_definition.questions):
        assert question.player_a.player_id != question.player_b.player_id
        assert question.player_a.points != question.player_b.points
        assert question.player_b.player_id not in seen_players
        matchup_key = frozenset((question.player_a.player_id, question.player_b.player_id))
        assert matchup_key not in seen_matchups
        seen_matchups.add(matchup_key)
        if index > 0:
            assert (
                question.player_a.player_id
                == round_definition.questions[index - 1].player_b.player_id
            )
        seen_players.update((question.player_a.player_id, question.player_b.player_id))


def test_generate_round_prefers_high_minute_players() -> None:
    high_minute_players = tuple(
        make_player(str(index), 10 + index, minutes=40 - index) for index in range(10)
    )
    low_minute_players = (
        make_player("low-a", 40, minutes=4),
        make_player("low-b", 1, minutes=3),
    )
    game = make_game(high_minute_players + low_minute_players)

    round_definition = generate_round(game, total_questions=5)

    player_ids = {question.player_a.player_id for question in round_definition.questions} | {
        question.player_b.player_id for question in round_definition.questions
    }
    assert "low-a" not in player_ids
    assert "low-b" not in player_ids


def test_generate_round_uses_only_eligible_players() -> None:
    active_players = (
        make_player("a", 30),
        make_player("b", 22),
        make_player("c", 18),
        make_player("d", 14),
        make_player("e", 9),
        make_player("f", 5),
    )
    benched_player = make_player("z", 40, minutes=0)
    game = make_game(active_players + (benched_player,))

    round_definition = generate_round(game, total_questions=5)

    player_ids = {question.player_a.player_id for question in round_definition.questions} | {
        question.player_b.player_id for question in round_definition.questions
    }
    assert "z" not in player_ids


def test_generate_round_falls_back_when_target_difficulty_is_missing() -> None:
    game = make_game(
        (
            make_player("a", 40),
            make_player("b", 28),
            make_player("c", 16),
            make_player("d", 4),
            make_player("e", 34),
            make_player("f", 10),
        )
    )

    round_definition = generate_round(game, total_questions=5)

    assert len(round_definition.questions) == 5
    assert any(question.difficulty is Difficulty.EASY for question in round_definition.questions)


def test_generate_round_rejects_invalid_question_count() -> None:
    game = make_game(tuple(make_player(str(index), 10 + index) for index in range(6)))

    with pytest.raises(ValueError, match="between 5 and 10"):
        generate_round(game, total_questions=4)


def test_generate_round_requires_enough_pair_capacity() -> None:
    game = make_game((make_player("a", 10), make_player("b", 14)))

    with pytest.raises(ValueError, match="Not enough valid player pairs"):
        generate_round(game, total_questions=5)


def test_generate_round_ignores_tied_pairs_and_can_fail_when_only_ties_remain() -> None:
    game = make_game(
        (
            make_player("a", 20),
            make_player("b", 20),
            make_player("c", 19),
            make_player("d", 19),
        )
    )

    with pytest.raises(ValueError, match="Not enough valid player pairs|Unable to generate"):
        generate_round(game, total_questions=5)


def _make_variety_game() -> NBAGame:
    # Equal minutes across all players removes the high-minute tiebreaker's
    # influence, leaving plenty of equally-preferable candidates whose
    # ordering can vary between seeds.
    points = (40, 35, 30, 26, 22, 19, 16, 13, 10, 7)
    players = tuple(
        make_player(str(index), player_points, minutes=24)
        for index, player_points in enumerate(points)
    )
    return make_game(players)


def _matchup_sequence(round_definition: RoundDefinition) -> tuple[frozenset[str], ...]:
    return tuple(
        frozenset((question.player_a.player_id, question.player_b.player_id))
        for question in round_definition.questions
    )


def _assert_round_is_valid(round_definition: RoundDefinition, total_questions: int) -> None:
    assert len(round_definition.questions) == total_questions
    seen_matchups: set[frozenset[str]] = set()
    seen_players: set[str] = set()
    for index, question in enumerate(round_definition.questions):
        assert question.player_a.player_id != question.player_b.player_id
        assert question.player_a.points != question.player_b.points
        assert question.player_b.player_id not in seen_players
        matchup_key = frozenset((question.player_a.player_id, question.player_b.player_id))
        assert matchup_key not in seen_matchups
        seen_matchups.add(matchup_key)
        if index > 0:
            assert (
                question.player_a.player_id
                == round_definition.questions[index - 1].player_b.player_id
            )
        seen_players.update((question.player_a.player_id, question.player_b.player_id))


def test_generate_round_is_deterministic_without_rng() -> None:
    game = _make_variety_game()

    first = generate_round(game, total_questions=5)
    second = generate_round(game, total_questions=5)

    assert _matchup_sequence(first) == _matchup_sequence(second)


def test_generate_round_with_same_seed_is_reproducible() -> None:
    game = _make_variety_game()

    first = generate_round(game, total_questions=5, rng=Random(1234))
    second = generate_round(game, total_questions=5, rng=Random(1234))

    assert _matchup_sequence(first) == _matchup_sequence(second)


def test_generate_round_with_different_seeds_can_vary_while_staying_valid() -> None:
    game = _make_variety_game()

    outcomes = {
        _matchup_sequence(generate_round(game, total_questions=5, rng=Random(seed)))
        for seed in range(20)
    }
    for round_definition in (
        generate_round(game, total_questions=5, rng=Random(seed)) for seed in range(20)
    ):
        _assert_round_is_valid(round_definition, total_questions=5)

    assert len(outcomes) > 1


def test_generate_round_with_rng_still_respects_matchup_and_repeat_constraints() -> None:
    game = _make_variety_game()

    for seed in range(20):
        round_definition = generate_round(game, total_questions=5, rng=Random(seed))
        _assert_round_is_valid(round_definition, total_questions=5)
