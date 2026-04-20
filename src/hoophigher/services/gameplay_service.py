from __future__ import annotations

import asyncio
import calendar
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from random import Random
from typing import Sequence

from sqlalchemy.engine import Engine

from hoophigher.data.api import StatsProvider
from hoophigher.data.db import session_scope
from hoophigher.data.repositories import QuestionRepository, RoundRepository, RunRepository
from hoophigher.data.schema import QuestionRecord, RoundRecord, RunRecord
from hoophigher.domain.enums import GameMode, GuessDirection, RunEndReason
from hoophigher.domain.models import GameBoxScore, Question, QuestionResult, RoundProgress, RunState
from hoophigher.domain.round_generator import generate_round
from hoophigher.domain.scoring import calculate_score_delta, get_run_end_reason_for_answer, is_guess_correct

MIN_HISTORICAL_GAMES = 5
DEFAULT_HISTORICAL_START_YEAR = 2010
DEFAULT_HISTORICAL_END_YEAR = 2020
DEFAULT_HISTORICAL_ROUNDS = 5
DEFAULT_HISTORICAL_MAX_DATE_PROBES = 10
DEFAULT_PLAYABLE_GAME_FETCH_CONCURRENCY = 5
DEFAULT_NON_HISTORICAL_STARTUP_GAMES = 5

# NBA regular season months where games are almost guaranteed.
_NBA_SEASON_MONTHS = (10, 11, 12, 1, 2, 3, 4)

HistoricalEligibleDatesFetcher = Callable[[int, int, int], Awaitable[Sequence[date]]]


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
    current_game: GameBoxScore
    games_today: tuple[GameBoxScore, ...]
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
    games: tuple[GameBoxScore, ...]
    next_game_index: int
    total_questions: int
    rounds_started: int


class GameplayService:
    def __init__(
        self,
        *,
        engine: Engine,
        provider: StatsProvider,
        rng: Random | None = None,
        historical_start_year: int = DEFAULT_HISTORICAL_START_YEAR,
        historical_end_year: int = DEFAULT_HISTORICAL_END_YEAR,
        historical_rounds: int = DEFAULT_HISTORICAL_ROUNDS,
        historical_max_date_probes: int = DEFAULT_HISTORICAL_MAX_DATE_PROBES,
        playable_game_fetch_concurrency: int = DEFAULT_PLAYABLE_GAME_FETCH_CONCURRENCY,
        non_historical_startup_games: int = DEFAULT_NON_HISTORICAL_STARTUP_GAMES,
        historical_eligible_dates_fetcher: HistoricalEligibleDatesFetcher | None = None,
    ) -> None:
        if historical_start_year > historical_end_year:
            raise ValueError("historical_start_year must be less than or equal to historical_end_year.")
        if historical_rounds < 1:
            raise ValueError("historical_rounds must be at least 1.")
        if historical_max_date_probes < 1:
            raise ValueError("historical_max_date_probes must be at least 1.")
        if playable_game_fetch_concurrency < 1:
            raise ValueError("playable_game_fetch_concurrency must be at least 1.")
        if non_historical_startup_games < 1:
            raise ValueError("non_historical_startup_games must be at least 1.")
        self._engine = engine
        self._provider = provider
        self._rng = rng or Random()
        self._historical_start_year = historical_start_year
        self._historical_end_year = historical_end_year
        self._historical_rounds = historical_rounds
        self._historical_max_date_probes = historical_max_date_probes
        self._playable_game_fetch_concurrency = playable_game_fetch_concurrency
        self._non_historical_startup_games = non_historical_startup_games
        self._historical_eligible_dates_fetcher = historical_eligible_dates_fetcher
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

        selected_date, games = await self._resolve_games(
            mode=mode,
            source_date=source_date,
            candidate_dates=candidate_dates,
            total_questions=total_questions,
        )
        selected_index = 0
        selected_game = games[selected_index]
        run_state = RunState(mode=mode, source_date=selected_date)
        round_definition = generate_round(selected_game, total_questions=total_questions)
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
                    game_date=selected_game.game_date,
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

    async def submit_answer(
        self,
        guess: GuessDirection,
        *,
        response_time_ms: int | None = None,
    ) -> QuestionResult:
        active_run = self._require_active_run()
        if active_run.run_state.is_finished:
            raise ValueError("Cannot answer a finished run.")

        round_progress = active_run.run_state.current_round
        if round_progress is None:
            raise ValueError("No active round in current run.")

        question_index = round_progress.current_index
        question = round_progress.current_question
        if question is None:
            raise ValueError("No pending question in current round.")

        is_correct = is_guess_correct(question, guess)
        score_delta = calculate_score_delta(active_run.run_state.mode, is_correct=is_correct)
        end_reason = get_run_end_reason_for_answer(active_run.run_state.mode, is_correct=is_correct)
        result = QuestionResult(
            question=question,
            guess=guess,
            is_correct=is_correct,
            score_delta=score_delta,
            revealed_points=question.player_b.points,
            response_time_ms=response_time_ms,
        )
        active_run.run_state.apply_result(result, end_reason=end_reason)
        self._persist_answer(
            active_run=active_run,
            result=result,
            question_index=question_index,
            round_progress=round_progress,
        )

        if round_progress.is_complete and not active_run.run_state.is_finished:
            if self._should_end_historical_run(active_run):
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
        game = round_progress.round_definition.game

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

    def _persist_answer(
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
        round_definition = generate_round(game, total_questions=active_run.total_questions)
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
                    game_date=game.game_date,
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

    async def _resolve_games(
        self,
        *,
        mode: GameMode,
        source_date: date | None,
        candidate_dates: Sequence[date] | None,
        total_questions: int,
    ) -> tuple[date, tuple[GameBoxScore, ...]]:
        if source_date is not None:
            return await self._resolve_games_for_date(
                mode=mode,
                source_date=source_date,
                total_questions=total_questions,
            )

        if candidate_dates is None:
            if mode is GameMode.HISTORICAL:
                return await self._resolve_historical_games(
                    total_questions=total_questions,
                )
            raise ValueError("candidate_dates is required when source_date is not provided.")

        return await self._resolve_games_from_candidates(
            mode=mode,
            candidate_dates=candidate_dates,
            total_questions=total_questions,
        )

    async def _resolve_games_for_date(
        self,
        *,
        mode: GameMode,
        source_date: date,
        total_questions: int,
    ) -> tuple[date, tuple[GameBoxScore, ...]]:
        """Resolve games for a specific date, fetching boxscores on demand."""
        game_shells = tuple(
            sorted(
                await self._provider.get_games_by_date(source_date),
                key=lambda g: g.game_id,
            )
        )
        if not game_shells:
            raise LookupError(f"No games found for source date: {source_date.isoformat()}")

        full_games = await self._fetch_playable_games(
            game_shells,
            total_questions=total_questions,
            max_games=(
                self._historical_rounds
                if mode is GameMode.HISTORICAL
                else self._non_historical_startup_games
            ),
        )
        if not full_games:
            raise LookupError(
                f"No playable games found for source date: {source_date.isoformat()}"
            )
        if mode is GameMode.HISTORICAL:
            return source_date, self._sample_historical_games(source_date, full_games)
        return source_date, full_games

    async def _resolve_games_from_candidates(
        self,
        *,
        mode: GameMode,
        candidate_dates: Sequence[date],
        total_questions: int,
    ) -> tuple[date, tuple[GameBoxScore, ...]]:
        """Iterate candidate dates, stop at the first one with playable games."""
        last_error: Exception | None = None
        saw_games = False
        max_games = (
            self._historical_rounds
            if mode is GameMode.HISTORICAL
            else self._non_historical_startup_games
        )

        for current_date in candidate_dates:
            try:
                game_shells = tuple(await self._provider.get_games_by_date(current_date))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_error = exc
                continue
            if game_shells:
                saw_games = True

            full_games = await self._fetch_playable_games(
                tuple(sorted(game_shells, key=lambda g: g.game_id)),
                total_questions=total_questions,
                max_games=max_games,
            )
            if full_games:
                if mode is GameMode.HISTORICAL:
                    return current_date, self._sample_historical_games(current_date, full_games)
                return current_date, full_games

        if saw_games:
            raise LookupError("No playable games found for provided candidate dates.")
        if last_error is not None:
            raise LookupError("No games found for provided candidate dates.") from last_error
        raise LookupError("No games found for provided candidate dates.")

    async def _resolve_historical_games(
        self,
        *,
        total_questions: int,
    ) -> tuple[date, tuple[GameBoxScore, ...]]:
        """Resolve historical games from an indexed date source or bounded random probes."""
        if self._historical_eligible_dates_fetcher is not None:
            eligible_dates = tuple(
                await self._historical_eligible_dates_fetcher(
                    self._historical_start_year,
                    self._historical_end_year,
                    self._required_historical_games,
                )
            )
            if not eligible_dates:
                raise LookupError("No historical date with playable games was found.")
            shuffled = list(eligible_dates)
            self._rng.shuffle(shuffled)
            probe_dates: Sequence[date] = shuffled[: self._historical_max_date_probes]
            # Pre-validated dates: accept even if fewer games than configured rounds.
            enforce_min_games = False
        else:
            probe_dates = self._generate_random_season_dates(
                start_year=self._historical_start_year,
                end_year=self._historical_end_year,
                count=self._historical_max_date_probes,
            )
            # Random probes: skip dates with too few games to avoid wasting API calls.
            enforce_min_games = True

        last_error: Exception | None = None
        for candidate_date in probe_dates:
            try:
                game_shells = tuple(
                    sorted(
                        await self._provider.get_games_by_date(candidate_date),
                        key=lambda g: g.game_id,
                    )
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_error = exc
                continue

            if enforce_min_games and len(game_shells) < self._required_historical_games:
                continue

            full_games = await self._fetch_playable_games(
                game_shells,
                total_questions=total_questions,
                max_games=self._historical_rounds,
            )
            if full_games:
                return candidate_date, self._sample_historical_games(candidate_date, full_games)

        error = LookupError(
            f"No historical date with playable games was found after {len(probe_dates)} probes."
        )
        if last_error is not None:
            raise error from last_error
        raise error

    async def _fetch_playable_games(
        self,
        game_shells: Sequence[GameBoxScore],
        *,
        total_questions: int,
        max_games: int | None = None,
    ) -> tuple[GameBoxScore, ...]:
        """Fetch full boxscores on demand, stopping once enough playable games are found.

        Games that already have player lines (from cache) are checked first.
        Shells without player lines are fetched in small concurrent batches.
        """
        playable: list[GameBoxScore] = []
        needs_fetch: list[GameBoxScore] = []

        # First pass: check games that already have full data.
        for game in game_shells:
            if game.player_lines:
                if self._can_generate_round(game, total_questions=total_questions):
                    playable.append(game)
                    if max_games is not None and len(playable) >= max_games:
                        return tuple(playable)
            else:
                needs_fetch.append(game)

        # Second pass: fetch boxscores on demand for shells without data.
        # Shuffle so we don't always probe the same games first.
        self._rng.shuffle(needs_fetch)
        step = self._playable_game_fetch_concurrency
        next_fetch_index = 0
        while next_fetch_index < len(needs_fetch):
            remaining_games = None if max_games is None else max_games - len(playable)
            if remaining_games is not None and remaining_games <= 0:
                return tuple(playable)
            chunk_size = step if remaining_games is None else min(step, remaining_games)
            chunk = needs_fetch[next_fetch_index : next_fetch_index + chunk_size]
            next_fetch_index += chunk_size
            fetched_games = await asyncio.gather(
                *(
                    self._fetch_playable_game(
                        game_shell,
                        total_questions=total_questions,
                    )
                    for game_shell in chunk
                )
            )
            for full_game in fetched_games:
                if full_game is None:
                    continue
                playable.append(full_game)
                if max_games is not None and len(playable) >= max_games:
                    return tuple(playable)

        return tuple(playable)

    async def _fetch_playable_game(
        self,
        game_shell: GameBoxScore,
        *,
        total_questions: int,
    ) -> GameBoxScore | None:
        try:
            full_game = await self._provider.get_game_boxscore(
                game_shell.game_id,
                game_date_fallback=game_shell.game_date,
            )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            return None

        if self._can_generate_round(full_game, total_questions=total_questions):
            return full_game
        return None

    def _generate_random_season_dates(
        self,
        *,
        start_year: int,
        end_year: int,
        count: int,
    ) -> tuple[date, ...]:
        """Generate random dates during NBA season months within the year window."""
        candidates: list[date] = []
        attempts = 0
        max_attempts = count * 3  # guard against infinite loop
        seen: set[date] = set()
        while len(candidates) < count and attempts < max_attempts:
            attempts += 1
            year = self._rng.randint(start_year, end_year)
            month = self._rng.choice(_NBA_SEASON_MONTHS)
            max_day = calendar.monthrange(year, month)[1]
            day = self._rng.randint(1, max_day)
            candidate = date(year, month, day)
            if candidate not in seen:
                seen.add(candidate)
                candidates.append(candidate)
        return tuple(candidates)

    def _require_active_run(self) -> _ActiveRun:
        if self._active_run is None:
            raise ValueError("No active run. Start a run before answering.")
        return self._active_run

    @property
    def _required_historical_games(self) -> int:
        return max(MIN_HISTORICAL_GAMES, self._historical_rounds)

    def _sample_historical_games(
        self,
        selected_date: date,
        games_for_date: tuple[GameBoxScore, ...],
    ) -> tuple[GameBoxScore, ...]:
        total_games = len(games_for_date)
        if total_games < 1:
            raise LookupError(
                f"Historical date {selected_date.isoformat()} has no playable games."
            )

        sampled_games = self._rng.sample(
            games_for_date,
            k=min(self._historical_rounds, total_games),
        )
        return tuple(sorted(sampled_games, key=lambda g: g.game_id))

    def _can_generate_round(self, game: GameBoxScore, *, total_questions: int) -> bool:
        try:
            generate_round(game, total_questions=total_questions)
        except ValueError:
            return False
        return True

    def _should_end_historical_run(self, active_run: _ActiveRun) -> bool:
        return (
            active_run.run_state.mode is GameMode.HISTORICAL
            and active_run.rounds_started >= len(active_run.games)
        )
