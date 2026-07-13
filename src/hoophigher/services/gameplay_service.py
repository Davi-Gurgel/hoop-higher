from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from random import Random

from sqlalchemy.engine import Engine

from hoophigher.data.stats_sources import StatsSource
from hoophigher.data.db import session_scope
from hoophigher.data.repositories import QuestionRepository, RoundRepository, RunRepository
from hoophigher.data.schema import QuestionRecord, RoundRecord, RunRecord
from hoophigher.domain.enums import GameMode, GuessDirection, RunEndReason
from hoophigher.domain.models import NBAGame, Question, QuestionResult, RoundProgress, RunState
from hoophigher.domain.round_generator import generate_round
from hoophigher.domain.scoring import (
    calculate_score_delta,
    get_run_end_reason_for_guess,
    is_guess_correct,
)
from hoophigher.services.playable_nba_game_resolver import (
    DEFAULT_HISTORICAL_END_YEAR,
    DEFAULT_HISTORICAL_MAX_DATE_PROBES,
    DEFAULT_HISTORICAL_ROUNDS,
    DEFAULT_HISTORICAL_START_YEAR,
    DEFAULT_NON_HISTORICAL_STARTUP_GAMES,
    DEFAULT_PLAYABLE_GAME_FETCH_CONCURRENCY,
    HistoricalEligibleSourceDatesFetcher,
    PlayableNBAGameResolver,
)


@dataclass(frozen=True, slots=True)
class GameplaySnapshot:
    run_id: int
    round_id: int
    mode: GameMode
    source_date: date | None
    score: int
    current_streak: int
    best_streak: int
    correct_answers: int
    wrong_answers: int
    end_reason: RunEndReason | None
    game_id: str
    current_game: NBAGame
    games_today: tuple[NBAGame, ...]
    round_index: int
    question_index: int
    total_questions: int
    current_question: Question | None

    @property
    def is_finished(self) -> bool:
        return self.end_reason is not None


@dataclass(slots=True)
class _ActiveRun:
    run_state: RunState
    run_id: int
    round_id: int
    games: tuple[NBAGame, ...]
    next_game_index: int
    total_questions: int
    rounds_started: int


class GameplayService:
    def __init__(
        self,
        *,
        engine: Engine,
        stats_source: StatsSource,
        rng: Random | None = None,
        nba_game_resolver: PlayableNBAGameResolver | None = None,
        historical_start_year: int = DEFAULT_HISTORICAL_START_YEAR,
        historical_end_year: int = DEFAULT_HISTORICAL_END_YEAR,
        historical_rounds: int = DEFAULT_HISTORICAL_ROUNDS,
        historical_max_date_probes: int = DEFAULT_HISTORICAL_MAX_DATE_PROBES,
        playable_game_fetch_concurrency: int = DEFAULT_PLAYABLE_GAME_FETCH_CONCURRENCY,
        non_historical_startup_games: int = DEFAULT_NON_HISTORICAL_STARTUP_GAMES,
        historical_eligible_dates_fetcher: HistoricalEligibleSourceDatesFetcher | None = None,
    ) -> None:
        self._engine = engine
        self._rng = rng or Random()
        self._nba_game_resolver = nba_game_resolver or PlayableNBAGameResolver(
            stats_source=stats_source,
            rng=self._rng,
            historical_start_year=historical_start_year,
            historical_end_year=historical_end_year,
            historical_rounds=historical_rounds,
            historical_max_date_probes=historical_max_date_probes,
            playable_game_fetch_concurrency=playable_game_fetch_concurrency,
            non_historical_startup_games=non_historical_startup_games,
            historical_eligible_source_dates_fetcher=historical_eligible_dates_fetcher,
        )
        self._active_run: _ActiveRun | None = None

    async def start_run(
        self,
        mode: GameMode,
        *,
        total_questions: int = 5,
        source_date: date | None = None,
        candidate_dates: Sequence[date] | None = None,
    ) -> GameplaySnapshot:
        if total_questions < 5 or total_questions > 10:
            raise ValueError("Rounds must request between 5 and 10 questions.")

        selected_date, games = await self._nba_game_resolver.resolve(
            mode=mode,
            source_date=source_date,
            candidate_dates=candidate_dates,
            total_questions=total_questions,
        )
        selected_index = 0
        selected_game = games[selected_index]
        run_state = RunState(mode=mode, source_date=selected_date)
        round_definition = generate_round(
            selected_game,
            total_questions=total_questions,
            rng=self._rng,
        )
        run_state.start_round(round_definition)

        with session_scope(self._engine) as session:
            run_repo = RunRepository(session)
            round_repo = RoundRepository(session)
            run_record = run_repo.create(
                RunRecord(
                    mode=mode.value,
                    source_date=selected_date,
                    final_score=run_state.score,
                    correct_answers=run_state.correct_answers,
                    wrong_answers=run_state.wrong_answers,
                    best_streak=run_state.best_streak,
                    end_reason=None,
                )
            )
            round_record = round_repo.create(
                RoundRecord(
                    run_id=run_record.id or 0,
                    round_index=0,
                    game_id=selected_game.game_id,
                    game_date=selected_game.source_date,
                    total_questions=len(round_definition.questions),
                    correct_answers=0,
                    wrong_answers=0,
                    score_delta=0,
                )
            )
            run_id = run_record.id
            round_id = round_record.id

        if run_id is None or round_id is None:
            raise RuntimeError("Persisted records are missing primary keys.")

        self._active_run = _ActiveRun(
            run_state=run_state,
            run_id=run_id,
            round_id=round_id,
            games=games,
            next_game_index=(selected_index + 1) % len(games),
            total_questions=total_questions,
            rounds_started=1,
        )
        return self.snapshot()

    async def submit_guess(
        self,
        guess: GuessDirection,
        *,
        response_time_ms: int | None = None,
    ) -> QuestionResult:
        active_run = self._require_active_run()
        if active_run.run_state.is_finished:
            raise ValueError("Cannot submit a guess for a finished run.")

        round_progress = active_run.run_state.current_round
        if round_progress is None:
            raise ValueError("No active round in current run.")

        question_index = round_progress.current_index
        question = round_progress.current_question
        if question is None:
            raise ValueError("No pending question in current round.")

        is_correct = is_guess_correct(question, guess)
        score_delta = calculate_score_delta(active_run.run_state.mode, is_correct=is_correct)
        end_reason = get_run_end_reason_for_guess(active_run.run_state.mode, is_correct=is_correct)
        result = QuestionResult(
            question=question,
            guess=guess,
            is_correct=is_correct,
            score_delta=score_delta,
            revealed_points=question.player_b.points,
            response_time_ms=response_time_ms,
        )
        active_run.run_state.apply_result(result, end_reason=end_reason)
        self._persist_guess(
            active_run=active_run,
            result=result,
            question_index=question_index,
            round_progress=round_progress,
        )

        if round_progress.is_complete and not active_run.run_state.is_finished:
            if self._should_end_run(active_run):
                active_run.run_state.end_reason = RunEndReason.NO_MORE_GAMES
                self._persist_run_state(active_run)
            else:
                await self._start_next_round(active_run)

        return result

    def snapshot(self) -> GameplaySnapshot:
        active_run = self._require_active_run()
        round_progress = active_run.run_state.current_round
        if round_progress is None:
            raise ValueError("No active round in current run.")
        current_question = round_progress.current_question
        game = round_progress.round_definition.nba_game

        return GameplaySnapshot(
            run_id=active_run.run_id,
            round_id=active_run.round_id,
            mode=active_run.run_state.mode,
            source_date=active_run.run_state.source_date,
            score=active_run.run_state.score,
            current_streak=active_run.run_state.current_streak,
            best_streak=active_run.run_state.best_streak,
            correct_answers=active_run.run_state.correct_answers,
            wrong_answers=active_run.run_state.wrong_answers,
            end_reason=active_run.run_state.end_reason,
            game_id=game.game_id,
            current_game=game,
            games_today=active_run.games,
            round_index=len(active_run.run_state.rounds) - 1,
            question_index=round_progress.current_index,
            total_questions=len(round_progress.round_definition.questions),
            current_question=current_question,
        )

    def end_run(self, end_reason: RunEndReason = RunEndReason.USER_EXIT) -> GameplaySnapshot:
        active_run = self._require_active_run()
        if active_run.run_state.end_reason is None:
            active_run.run_state.end_reason = end_reason
            self._persist_run_state(active_run)
        return self.snapshot()

    def _persist_guess(
        self,
        *,
        active_run: _ActiveRun,
        result: QuestionResult,
        question_index: int,
        round_progress: RoundProgress,
    ) -> None:
        with session_scope(self._engine) as session:
            run_repo = RunRepository(session)
            round_repo = RoundRepository(session)
            question_repo = QuestionRepository(session)

            question_repo.create(
                QuestionRecord(
                    run_id=active_run.run_id,
                    round_id=active_run.round_id,
                    question_index=question_index,
                    player_a_id=result.question.player_a.player_id,
                    player_a_name=result.question.player_a.player_name,
                    player_a_team_id=result.question.player_a.team_id,
                    player_a_team_abbreviation=result.question.player_a.team_abbreviation,
                    player_a_points=result.question.player_a.points,
                    player_a_minutes=result.question.player_a.minutes,
                    player_b_id=result.question.player_b.player_id,
                    player_b_name=result.question.player_b.player_name,
                    player_b_team_id=result.question.player_b.team_id,
                    player_b_team_abbreviation=result.question.player_b.team_abbreviation,
                    player_b_points=result.question.player_b.points,
                    player_b_minutes=result.question.player_b.minutes,
                    difficulty=result.question.difficulty.value,
                    guess=result.guess.value,
                    is_correct=result.is_correct,
                    score_delta=result.score_delta,
                    revealed_points=result.revealed_points,
                    response_time_ms=result.response_time_ms,
                )
            )

            round_repo.update_progress(
                active_run.round_id,
                correct_answers=sum(1 for item in round_progress.results if item.is_correct),
                wrong_answers=sum(1 for item in round_progress.results if not item.is_correct),
                score_delta=sum(item.score_delta for item in round_progress.results),
            )
            self._update_run_record(run_repo, active_run.run_id, active_run.run_state)

    def _persist_run_state(self, active_run: _ActiveRun) -> None:
        with session_scope(self._engine) as session:
            run_repo = RunRepository(session)
            self._update_run_record(run_repo, active_run.run_id, active_run.run_state)

    def _update_run_record(
        self,
        run_repo: RunRepository,
        run_id: int,
        run_state: RunState,
    ) -> None:
        run_repo.update_progress(
            run_id,
            final_score=run_state.score,
            correct_answers=run_state.correct_answers,
            wrong_answers=run_state.wrong_answers,
            best_streak=run_state.best_streak,
            end_reason=run_state.end_reason.value if run_state.end_reason is not None else None,
        )

    async def _start_next_round(self, active_run: _ActiveRun) -> None:
        game = active_run.games[active_run.next_game_index]
        active_run.next_game_index = (active_run.next_game_index + 1) % len(active_run.games)
        round_definition = generate_round(
            game,
            total_questions=active_run.total_questions,
            rng=self._rng,
        )
        active_run.run_state.start_round(round_definition)
        active_run.rounds_started += 1
        round_index = len(active_run.run_state.rounds) - 1

        with session_scope(self._engine) as session:
            round_repo = RoundRepository(session)
            round_record = round_repo.create(
                RoundRecord(
                    run_id=active_run.run_id,
                    round_index=round_index,
                    game_id=game.game_id,
                    game_date=game.source_date,
                    total_questions=len(round_definition.questions),
                    correct_answers=0,
                    wrong_answers=0,
                    score_delta=0,
                )
            )
            round_id = round_record.id
        if round_id is None:
            raise RuntimeError("Persisted round record is missing primary key.")
        active_run.round_id = round_id

    def _require_active_run(self) -> _ActiveRun:
        if self._active_run is None:
            raise ValueError("No active run. Start a run before guessing.")
        return self._active_run

    def _should_end_run(self, active_run: _ActiveRun) -> bool:
        return active_run.rounds_started >= len(active_run.games)
