from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from hoophigher.domain.difficulty import classify_question_difficulty, pick_target_difficulty
from hoophigher.domain.enums import Difficulty
from hoophigher.domain.models import GameBoxScore, PlayerLine, Question, RoundDefinition


@dataclass(frozen=True, slots=True)
class QuestionCandidate:
    question: Question
    source_id: str
    target_id: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.source_id, self.target_id)


_DIFFICULTY_ORDER = {
    Difficulty.EASY: 0,
    Difficulty.MEDIUM: 1,
    Difficulty.HARD: 2,
}


def generate_round(game: GameBoxScore, *, total_questions: int = 5) -> RoundDefinition:
    if total_questions < 5 or total_questions > 10:
        raise ValueError("Rounds must request between 5 and 10 questions.")

    eligible_players = tuple(sorted(game.eligible_player_lines, key=lambda player: player.player_id))
    if len(eligible_players) < 2:
        raise ValueError("At least two eligible players are required to generate a round.")

    candidates = _build_question_candidates(eligible_players)
    if len(candidates) < total_questions:
        raise ValueError("Not enough valid player pairs to generate the requested round.")

    by_source = _group_candidates_by_source(candidates)
    questions = _search_question_path(
        by_source=by_source,
        total_questions=total_questions,
    )
    if questions is None:
        raise ValueError("Unable to generate a valid round with the available players.")

    return RoundDefinition(game=game, questions=questions)


def _build_question_candidates(players: tuple[PlayerLine, ...]) -> tuple[QuestionCandidate, ...]:
    candidates: list[QuestionCandidate] = []
    for player_a in players:
        for player_b in players:
            if player_a.player_id == player_b.player_id:
                continue

            candidates.append(
                QuestionCandidate(
                    question=Question(
                        player_a=player_a,
                        player_b=player_b,
                        difficulty=classify_question_difficulty(player_a.points, player_b.points),
                    ),
                    source_id=player_a.player_id,
                    target_id=player_b.player_id,
                )
            )

    return tuple(candidates)


def _group_candidates_by_source(
    candidates: tuple[QuestionCandidate, ...],
) -> dict[str, tuple[QuestionCandidate, ...]]:
    grouped: dict[str, list[QuestionCandidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.source_id].append(candidate)

    return {
        player_id: tuple(player_candidates)
        for player_id, player_candidates in grouped.items()
    }


def _search_question_path(
    *,
    by_source: dict[str, tuple[QuestionCandidate, ...]],
    total_questions: int,
) -> tuple[Question, ...] | None:
    all_candidates = tuple(candidate for candidates in by_source.values() for candidate in candidates)

    for starting_candidate in _sort_candidates_for_target(
        all_candidates,
        target=pick_target_difficulty(0, total_questions),
    ):
        result = _search_from_candidate(
            current_candidate=starting_candidate,
            by_source=by_source,
            total_questions=total_questions,
            used_edges={starting_candidate.key},
            selected_questions=[starting_candidate.question],
        )
        if result is not None:
            return tuple(result)

    return None


def _search_from_candidate(
    *,
    current_candidate: QuestionCandidate,
    by_source: dict[str, tuple[QuestionCandidate, ...]],
    total_questions: int,
    used_edges: set[tuple[str, str]],
    selected_questions: list[Question],
) -> list[Question] | None:
    if len(selected_questions) == total_questions:
        return selected_questions.copy()

    next_source_id = current_candidate.target_id
    next_target_difficulty = pick_target_difficulty(len(selected_questions), total_questions)
    next_candidates = tuple(
        candidate
        for candidate in by_source.get(next_source_id, ())
        if candidate.key not in used_edges
    )

    for next_candidate in _sort_candidates_for_target(next_candidates, target=next_target_difficulty):
        used_edges.add(next_candidate.key)
        selected_questions.append(next_candidate.question)

        result = _search_from_candidate(
            current_candidate=next_candidate,
            by_source=by_source,
            total_questions=total_questions,
            used_edges=used_edges,
            selected_questions=selected_questions,
        )
        if result is not None:
            return result

        selected_questions.pop()
        used_edges.remove(next_candidate.key)

    return None


def _sort_candidates_for_target(
    candidates: tuple[QuestionCandidate, ...],
    *,
    target: Difficulty,
) -> tuple[QuestionCandidate, ...]:
    target_rank = _DIFFICULTY_ORDER[target]

    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                abs(_DIFFICULTY_ORDER[candidate.question.difficulty] - target_rank),
                _DIFFICULTY_ORDER[candidate.question.difficulty],
                candidate.question.point_difference,
                candidate.source_id,
                candidate.target_id,
            ),
        )
    )
