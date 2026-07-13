import asyncio
from datetime import date
from random import Random

import pytest
from sqlmodel import Session

from hoophigher.data import (
    QuestionRepository,
    RoundRepository,
    RunRepository,
    create_sqlite_engine,
    init_db,
)
from hoophigher.data.stats_sources import MockStatsSource
from hoophigher.domain.enums import GameMode, GuessDirection, RunEndReason
from hoophigher.domain.models import NBAGame, PlayerLine, TeamGameInfo
from hoophigher.services import GameplayService, PlayableNBAGameResolver


def _make_engine(tmp_path):
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'hoophigher.db'}")
    init_db(engine)
    return engine


def _make_service(**kwargs):
    values = {
        "historical_start_year": 2010,
        "historical_end_year": 2020,
        "historical_rounds": 5,
        "historical_max_date_probes": 10,
        "playable_game_fetch_concurrency": 8,
        "non_historical_startup_games": 5,
    }
    values.update(kwargs)
    return GameplayService(**values)


def _make_service_game(
    *,
    game_id: str,
    source_date: date,
    minutes: int = 30,
) -> NBAGame:
    home_team = TeamGameInfo(team_id=f"{game_id}-home", name="Home", abbreviation="HME", score=110)
    away_team = TeamGameInfo(team_id=f"{game_id}-away", name="Away", abbreviation="AWY", score=104)
    points = (31, 24, 19, 15, 9, 4)
    split_index = len(points) // 2
    players = tuple(
        PlayerLine(
            player_id=f"{game_id}-p{index}",
            player_name=f"Player {index}",
            team_id=away_team.team_id if index <= split_index else home_team.team_id,
            team_abbreviation=(
                away_team.abbreviation if index <= split_index else home_team.abbreviation
            ),
            points=player_points,
            minutes=minutes,
        )
        for index, player_points in enumerate(points, start=1)
    )
    return NBAGame(
        game_id=game_id,
        source_date=source_date,
        home_team=home_team,
        away_team=away_team,
        player_lines=players,
    )


def _opposite_guess(guess: GuessDirection) -> GuessDirection:
    return GuessDirection.LOWER if guess is GuessDirection.HIGHER else GuessDirection.HIGHER


class _DateStatsSource:
    def __init__(self, games_by_date: dict[date, object]) -> None:
        self._games_by_date = games_by_date

    async def get_games_by_date(self, source_date: date) -> list[NBAGame]:
        value = self._games_by_date.get(source_date, ())
        if isinstance(value, Exception):
            raise value
        return list(value)

    async def get_nba_game(
        self,
        game_id: str,
        *,
        source_date_fallback: date | None = None,
    ) -> NBAGame:
        for games in self._games_by_date.values():
            if isinstance(games, Exception):
                continue
            for game in games:
                if game.game_id == game_id:
                    return game
        raise LookupError(f"Game not found: {game_id}")


class _NoShuffleRandom(Random):
    def shuffle(self, x) -> None:
        return None

    def choice(self, seq):
        return seq[0]

    def sample(self, population, k):
        return list(population)[:k]


def test_endless_continues_after_wrong_answer_and_persists_progress(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = _make_service(engine=engine, stats_source=MockStatsSource(), rng=Random(7))

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.ENDLESS,
            source_date=date(2025, 1, 12),
            total_questions=5,
        )
    )
    question = start_snapshot.current_question
    assert question is not None

    wrong_guess = _opposite_guess(question.correct_guess)
    result = asyncio.run(service.submit_guess(wrong_guess, response_time_ms=900))
    snapshot = service.snapshot()

    assert result.is_correct is False
    assert snapshot.is_finished is False
    assert snapshot.wrong_answers == 1
    assert snapshot.score == -60

    with Session(engine) as session:
        run_record = RunRepository(session).get(start_snapshot.run_id)
        round_record = RoundRepository(session).get(start_snapshot.round_id)
        questions = QuestionRepository(session).list_by_run(start_snapshot.run_id)

    assert run_record is not None
    assert run_record.final_score == -60
    assert run_record.wrong_answers == 1
    assert run_record.end_reason is None
    assert round_record is not None
    assert round_record.wrong_answers == 1
    assert len(questions) == 1
    assert questions[0].is_correct is False


def test_service_requires_active_run_for_snapshot_submit_and_end_run(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = _make_service(engine=engine, stats_source=MockStatsSource(), rng=Random(1))

    with pytest.raises(ValueError, match="No active run"):
        service.snapshot()

    with pytest.raises(ValueError, match="No active run"):
        asyncio.run(service.submit_guess(GuessDirection.HIGHER))

    with pytest.raises(ValueError, match="No active run"):
        service.end_run()


def test_arcade_ends_on_first_error(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = _make_service(engine=engine, stats_source=MockStatsSource(), rng=Random(3))

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.ARCADE,
            source_date=date(2025, 1, 12),
            total_questions=5,
        )
    )
    question = start_snapshot.current_question
    assert question is not None

    wrong_guess = _opposite_guess(question.correct_guess)
    asyncio.run(service.submit_guess(wrong_guess))
    snapshot = service.snapshot()

    assert snapshot.is_finished is True
    assert snapshot.end_reason is RunEndReason.WRONG_GUESS
    assert snapshot.score == 0


def test_submit_answer_rejects_finished_run(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = _make_service(engine=engine, stats_source=MockStatsSource(), rng=Random(3))

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.ARCADE,
            source_date=date(2025, 1, 12),
            total_questions=5,
        )
    )
    question = start_snapshot.current_question
    assert question is not None

    asyncio.run(service.submit_guess(_opposite_guess(question.correct_guess)))

    with pytest.raises(ValueError, match="finished run"):
        asyncio.run(service.submit_guess(GuessDirection.HIGHER))


def test_start_run_delegates_source_date_and_playable_game_resolution(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    selected_date = date(2025, 1, 12)
    selected_game = _make_service_game(game_id="delegated-game", source_date=selected_date)
    resolver = PlayableNBAGameResolver(
        stats_source=_DateStatsSource({selected_date: (selected_game,)}),
        rng=Random(1),
        historical_start_year=2010,
        historical_end_year=2020,
        historical_rounds=5,
        historical_max_date_probes=10,
        playable_game_fetch_concurrency=8,
        non_historical_startup_games=5,
    )
    service = _make_service(
        engine=engine,
        stats_source=MockStatsSource(),
        rng=Random(1),
        nba_game_resolver=resolver,
    )

    snapshot = asyncio.run(
        service.start_run(
            GameMode.ENDLESS,
            source_date=selected_date,
            total_questions=5,
        )
    )

    assert snapshot.game_id == "delegated-game"


def test_endless_starts_next_round_after_perfect_round_and_persists_rounds(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = _make_service(engine=engine, stats_source=MockStatsSource(), rng=Random(1))

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.ENDLESS,
            source_date=date(2025, 1, 12),
            total_questions=5,
        )
    )

    for _ in range(start_snapshot.total_questions):
        question = service.snapshot().current_question
        assert question is not None
        asyncio.run(service.submit_guess(question.correct_guess))

    snapshot = service.snapshot()

    assert snapshot.is_finished is False
    assert snapshot.round_index == 1
    assert snapshot.current_question is not None
    assert snapshot.score == 500

    with Session(engine) as session:
        run_record = RunRepository(session).get(start_snapshot.run_id)
        rounds = RoundRepository(session).list_by_run(start_snapshot.run_id)

    assert run_record is not None
    assert run_record.final_score == 500
    assert run_record.correct_answers == 5
    assert [round_record.round_index for round_record in rounds] == [0, 1]
    assert [round_record.total_questions for round_record in rounds] == [5, 5]


def test_arcade_starts_next_round_after_perfect_round_and_persists_rounds(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = _make_service(engine=engine, stats_source=MockStatsSource(), rng=Random(1))

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.ARCADE,
            source_date=date(2025, 1, 12),
            total_questions=5,
        )
    )

    for _ in range(start_snapshot.total_questions):
        question = service.snapshot().current_question
        assert question is not None
        asyncio.run(service.submit_guess(question.correct_guess))

    snapshot = service.snapshot()

    assert snapshot.is_finished is False
    assert snapshot.round_index == 1
    assert snapshot.current_question is not None
    assert snapshot.score == 750

    with Session(engine) as session:
        run_record = RunRepository(session).get(start_snapshot.run_id)
        rounds = RoundRepository(session).list_by_run(start_snapshot.run_id)

    assert run_record is not None
    assert run_record.final_score == 750
    assert run_record.correct_answers == 5
    assert [round_record.round_index for round_record in rounds] == [0, 1]
    assert [round_record.total_questions for round_record in rounds] == [5, 5]


def test_non_historical_run_ends_after_each_fetched_game_is_played(tmp_path) -> None:
    source_date = date(2025, 2, 10)
    engine = _make_engine(tmp_path)
    service = _make_service(
        engine=engine,
        stats_source=_DateStatsSource(
            {
                source_date: (
                    _make_service_game(game_id="game-a", source_date=source_date),
                    _make_service_game(game_id="game-b", source_date=source_date),
                )
            }
        ),
        rng=_NoShuffleRandom(1),
        non_historical_startup_games=2,
    )

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.ENDLESS,
            candidate_dates=[source_date],
            total_questions=5,
        )
    )

    assert [game.game_id for game in start_snapshot.games_today] == ["game-a", "game-b"]

    for _ in range(start_snapshot.total_questions):
        question = service.snapshot().current_question
        assert question is not None
        asyncio.run(service.submit_guess(question.correct_guess))

    second_round_snapshot = service.snapshot()

    assert second_round_snapshot.is_finished is False
    assert second_round_snapshot.round_index == 1
    assert second_round_snapshot.game_id == "game-b"

    for _ in range(second_round_snapshot.total_questions):
        question = service.snapshot().current_question
        assert question is not None
        asyncio.run(service.submit_guess(question.correct_guess))

    final_snapshot = service.snapshot()

    assert final_snapshot.is_finished is True
    assert final_snapshot.end_reason is RunEndReason.NO_MORE_GAMES
    assert final_snapshot.round_index == 1
    assert final_snapshot.current_question is None

    with Session(engine) as session:
        rounds = RoundRepository(session).list_by_run(start_snapshot.run_id)

    assert [round_record.game_id for round_record in rounds] == ["game-a", "game-b"]


def test_end_run_persists_user_exit_and_is_idempotent(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = _make_service(engine=engine, stats_source=MockStatsSource(), rng=Random(1))

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.ENDLESS,
            source_date=date(2025, 1, 12),
            total_questions=5,
        )
    )

    first_snapshot = service.end_run()
    second_snapshot = service.end_run()

    assert first_snapshot.run_id == start_snapshot.run_id
    assert first_snapshot.end_reason is RunEndReason.USER_EXIT
    assert second_snapshot.end_reason is RunEndReason.USER_EXIT
    assert second_snapshot.score == first_snapshot.score

    with Session(engine) as session:
        run_record = RunRepository(session).get(start_snapshot.run_id)

    assert run_record is not None
    assert run_record.end_reason == RunEndReason.USER_EXIT.value


class _ManyGamesStatsSource:
    def __init__(self) -> None:
        source_date = date(2018, 2, 14)
        self._games = tuple(
            self._build_game(source_date=source_date, index=index) for index in range(1, 8)
        )
        self._games_by_id = {game.game_id: game for game in self._games}

    async def get_games_by_date(self, source_date: date) -> list[NBAGame]:
        if source_date == date(2018, 2, 14):
            return list(self._games)
        return []

    async def get_nba_game(
        self,
        game_id: str,
        *,
        source_date_fallback: date | None = None,
    ) -> NBAGame:
        return self._games_by_id[game_id]

    def _build_game(self, *, source_date: date, index: int) -> NBAGame:
        game_id = f"2018-02-14-game-{index:02d}"
        return NBAGame(
            game_id=game_id,
            source_date=source_date,
            home_team=TeamGameInfo(
                team_id=f"h-{index}", name="Home", abbreviation="HOM", score=110
            ),
            away_team=TeamGameInfo(
                team_id=f"a-{index}", name="Away", abbreviation="AWY", score=103
            ),
            player_lines=(
                PlayerLine(
                    player_id=f"{game_id}-p1",
                    player_name="Player A",
                    team_id=f"a-{index}",
                    team_abbreviation="AWY",
                    points=26,
                    minutes=34,
                ),
                PlayerLine(
                    player_id=f"{game_id}-p2",
                    player_name="Player B",
                    team_id=f"h-{index}",
                    team_abbreviation="HOM",
                    points=20,
                    minutes=31,
                ),
                PlayerLine(
                    player_id=f"{game_id}-p3",
                    player_name="Player C",
                    team_id=f"a-{index}",
                    team_abbreviation="AWY",
                    points=17,
                    minutes=29,
                ),
                PlayerLine(
                    player_id=f"{game_id}-p4",
                    player_name="Player D",
                    team_id=f"h-{index}",
                    team_abbreviation="HOM",
                    points=13,
                    minutes=27,
                ),
                PlayerLine(
                    player_id=f"{game_id}-p5",
                    player_name="Player E",
                    team_id=f"a-{index}",
                    team_abbreviation="AWY",
                    points=9,
                    minutes=25,
                ),
                PlayerLine(
                    player_id=f"{game_id}-p6",
                    player_name="Player F",
                    team_id=f"h-{index}",
                    team_abbreviation="HOM",
                    points=7,
                    minutes=23,
                ),
            ),
        )


class _FewGamesStatsSource:
    def __init__(self) -> None:
        self.requested_dates: list[date] = []
        source_date = date(2018, 2, 13)
        self._games = tuple(
            _make_service_game(game_id=f"few-game-{index}", source_date=source_date)
            for index in range(1, 3)
        )

    async def get_games_by_date(self, source_date: date) -> list[NBAGame]:
        self.requested_dates.append(source_date)
        if source_date == date(2018, 2, 13):
            return list(self._games)
        return [
            _make_service_game(game_id=f"fallback-game-{index}", source_date=source_date)
            for index in range(1, 6)
        ]

    async def get_nba_game(
        self,
        game_id: str,
        *,
        source_date_fallback: date | None = None,
    ) -> NBAGame:
        for game in self._games:
            if game.game_id == game_id:
                return game
        raise LookupError(f"Game not found: {game_id}")


def test_historical_uses_exactly_configured_rounds_even_when_date_has_more_games(tmp_path) -> None:
    engine = _make_engine(tmp_path)

    async def fake_eligible_dates_fetcher(_start_year: int, _end_year: int, _min_games: int):
        return (date(2018, 2, 14),)

    service = _make_service(
        engine=engine,
        stats_source=_ManyGamesStatsSource(),
        rng=Random(4),
        historical_rounds=5,
        historical_eligible_dates_fetcher=fake_eligible_dates_fetcher,
    )

    start_snapshot = asyncio.run(service.start_run(GameMode.HISTORICAL, total_questions=5))

    assert len(start_snapshot.games_today) == 5
    sampled_game_ids = {game.game_id for game in start_snapshot.games_today}
    assert len(sampled_game_ids) == 5

    for _ in range(5):
        round_snapshot = service.snapshot()
        for _ in range(round_snapshot.total_questions):
            question = service.snapshot().current_question
            assert question is not None
            asyncio.run(service.submit_guess(question.correct_guess))

    final_snapshot = service.snapshot()

    assert final_snapshot.is_finished is True
    assert final_snapshot.end_reason is RunEndReason.NO_MORE_GAMES
    assert final_snapshot.round_index == 4


def test_historical_caps_rounds_to_available_games_without_refetching_dates(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    stats_source = _FewGamesStatsSource()

    async def fake_eligible_dates_fetcher(_start_year: int, _end_year: int, _min_games: int):
        return (date(2018, 2, 13), date(2018, 2, 14))

    service = _make_service(
        engine=engine,
        stats_source=stats_source,
        rng=_NoShuffleRandom(),
        historical_rounds=5,
        historical_eligible_dates_fetcher=fake_eligible_dates_fetcher,
    )

    start_snapshot = asyncio.run(service.start_run(GameMode.HISTORICAL, total_questions=5))

    assert stats_source.requested_dates == [date(2018, 2, 13)]
    assert len(start_snapshot.games_today) == 2
    assert {game.game_id for game in start_snapshot.games_today} == {
        "few-game-1",
        "few-game-2",
    }

    for _ in range(2):
        round_snapshot = service.snapshot()
        for _ in range(round_snapshot.total_questions):
            question = service.snapshot().current_question
            assert question is not None
            asyncio.run(service.submit_guess(question.correct_guess))

    final_snapshot = service.snapshot()

    assert final_snapshot.is_finished is True
    assert final_snapshot.end_reason is RunEndReason.NO_MORE_GAMES
    assert final_snapshot.round_index == 1

    with Session(engine) as session:
        rounds = RoundRepository(session).list_by_run(start_snapshot.run_id)

    assert [round_record.game_id for round_record in rounds] == [
        "few-game-1",
        "few-game-2",
    ]


def test_historical_carries_configured_total_questions_into_next_round(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = _make_service(engine=engine, stats_source=MockStatsSource(), rng=Random(1))

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.HISTORICAL,
            source_date=date(2025, 1, 12),
            total_questions=6,
        )
    )

    for _ in range(start_snapshot.total_questions):
        question = service.snapshot().current_question
        assert question is not None
        asyncio.run(service.submit_guess(question.correct_guess))

    snapshot = service.snapshot()

    assert snapshot.round_index == 1
    assert snapshot.total_questions == 6
    assert snapshot.current_question is not None

    with Session(engine) as session:
        rounds = RoundRepository(session).list_by_run(start_snapshot.run_id)

    assert [round_record.total_questions for round_record in rounds[:2]] == [6, 6]


def test_historical_wrong_answer_keeps_run_active_and_applies_score(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = _make_service(engine=engine, stats_source=MockStatsSource(), rng=Random(5))

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.HISTORICAL,
            source_date=date(2025, 1, 12),
            total_questions=5,
        )
    )
    question = start_snapshot.current_question
    assert question is not None

    wrong_guess = _opposite_guess(question.correct_guess)
    result = asyncio.run(service.submit_guess(wrong_guess, response_time_ms=700))
    snapshot = service.snapshot()

    assert result.is_correct is False
    assert snapshot.is_finished is False
    assert snapshot.wrong_answers == 1
    assert snapshot.score == -60


def test_historical_advances_to_next_game_after_round_completion(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = _make_service(engine=engine, stats_source=MockStatsSource(), rng=Random(1))

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.HISTORICAL,
            source_date=date(2025, 1, 12),
            total_questions=5,
        )
    )
    initial_game_id = start_snapshot.game_id

    for _ in range(start_snapshot.total_questions):
        question = service.snapshot().current_question
        assert question is not None
        asyncio.run(service.submit_guess(question.correct_guess))

    snapshot = service.snapshot()

    assert snapshot.is_finished is False
    assert snapshot.round_index == 1
    assert snapshot.game_id != initial_game_id


def test_historical_ends_after_all_games_for_date_are_consumed(tmp_path) -> None:
    engine = _make_engine(tmp_path)
    service = _make_service(engine=engine, stats_source=MockStatsSource(), rng=Random(1))

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.HISTORICAL,
            source_date=date(2025, 1, 12),
            total_questions=5,
        )
    )
    total_rounds = len(start_snapshot.games_today)

    for _ in range(total_rounds):
        round_snapshot = service.snapshot()
        for _ in range(round_snapshot.total_questions):
            question = service.snapshot().current_question
            assert question is not None
            asyncio.run(service.submit_guess(question.correct_guess))

    snapshot = service.snapshot()

    assert snapshot.is_finished is True
    assert snapshot.end_reason is RunEndReason.NO_MORE_GAMES
    assert snapshot.round_index == total_rounds - 1
    assert snapshot.current_question is None

    with Session(engine) as session:
        run_record = RunRepository(session).get(start_snapshot.run_id)

    assert run_record is not None
    assert run_record.end_reason == RunEndReason.NO_MORE_GAMES.value


def _spy_on_generate_round(monkeypatch) -> list[object]:
    """Record the `rng` kwarg passed to every `generate_round` call made by the
    gameplay service module, while still delegating to the real function.
    """
    import hoophigher.services.gameplay_service as gameplay_service_module

    recorded_rngs: list[object] = []
    original_generate_round = gameplay_service_module.generate_round

    def _spy_generate_round(*args, **kwargs):
        recorded_rngs.append(kwargs.get("rng"))
        return original_generate_round(*args, **kwargs)

    monkeypatch.setattr(gameplay_service_module, "generate_round", _spy_generate_round)
    return recorded_rngs


def test_start_run_generates_round_using_service_owned_rng(tmp_path, monkeypatch) -> None:
    engine = _make_engine(tmp_path)
    service_rng = Random(11)
    service = _make_service(engine=engine, stats_source=MockStatsSource(), rng=service_rng)
    recorded_rngs = _spy_on_generate_round(monkeypatch)

    asyncio.run(
        service.start_run(
            GameMode.ENDLESS,
            source_date=date(2025, 1, 12),
            total_questions=5,
        )
    )

    # start_run should generate its Round using the service-owned rng, not the
    # deterministic default.
    assert recorded_rngs
    assert recorded_rngs[-1] is service_rng


def test_start_next_round_generates_round_using_service_owned_rng(tmp_path, monkeypatch) -> None:
    engine = _make_engine(tmp_path)
    service_rng = Random(11)
    service = _make_service(engine=engine, stats_source=MockStatsSource(), rng=service_rng)

    start_snapshot = asyncio.run(
        service.start_run(
            GameMode.HISTORICAL,
            source_date=date(2025, 1, 12),
            total_questions=5,
        )
    )
    assert len(start_snapshot.games_today) > 1

    recorded_rngs = _spy_on_generate_round(monkeypatch)

    for _ in range(start_snapshot.total_questions):
        question = service.snapshot().current_question
        assert question is not None
        asyncio.run(service.submit_guess(question.correct_guess))

    assert recorded_rngs
    assert recorded_rngs[-1] is service_rng
