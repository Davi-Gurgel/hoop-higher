# ARCHITECTURE.md

## 1. Purpose

This document describes the technical architecture of **Hoop Higher**.

The priorities are:
- decoupling between UI, domain, persistence, and external integrations
- easy iteration by code agents
- support for mocked data and a real provider without rewriting the application
- a solid base for evolving the game without taking on unnecessary early technical debt

---

## 2. Architectural Principles

1. **UI does not contain business rules.**
2. **Domain does not know Textual, SQLite, or external APIs.**
3. **External integrations enter through clear interfaces.**
4. **Persistence should be simple, explicit, and local.**
5. **Each layer should be testable in isolation.**

---

## 3. Layered View

```text
TUI (Textual screens/widgets)
        ↓
Services (use cases/orchestration)
        ↓
Domain (game rules)
        ↓
Data (repositories, providers, cache)
```

### Allowed dependencies
- `tui -> services`
- `services -> domain`
- `services -> data`
- `data -> domain` only for mapping payloads into internal models

### Forbidden dependencies
- `domain -> tui`
- `domain -> data`
- `tui -> direct sqlite`
- `tui -> direct api provider`

---

## 4. Proposed Directory Structure

```text
src/
└── hoophigher/
    ├── main.py
    ├── app.py
    ├── config.py
    ├── tui/
    │   ├── screens/
    │   ├── widgets/
    │   └── styles.tcss
    ├── domain/
    │   ├── enums.py
    │   ├── models.py
    │   ├── scoring.py
    │   ├── difficulty.py
    │   ├── round_generator.py
    │   └── game_session.py
    ├── services/
    │   ├── play_endless.py
    │   ├── play_arcade.py
    │   ├── play_historical.py
    │   └── stats_service.py
    ├── data/
    │   ├── db.py
    │   ├── schema.py
    │   ├── repositories/
    │   ├── cache_repository.py
    │   └── api/
    │       ├── base.py
    │       ├── mock_provider.py
    │       └── balldontlie_provider.py
    └── utils/
```

---

## 5. Domain Layer

## Responsibilities
- represent the game concepts
- contain the core rules
- encapsulate scoring, difficulty, and question generation

## Expected components

### `enums.py`
- `GameMode`
- `Difficulty`
- `GuessDirection`
- `RunEndReason`

### `models.py`
Pure domain models, for example:
- `PlayerLine`
- `GameBoxScore`
- `Question`
- `RoundDefinition`
- `RunState`

### `scoring.py`
Functions such as:
- `calculate_endless_score_delta(...)`
- `calculate_arcade_score_delta(...)`

### `difficulty.py`
Functions such as:
- `classify_question_difficulty(points_a, points_b)`
- `pick_target_difficulty(question_index, total_questions)`

### `round_generator.py`
Responsible for:
- filtering eligible players
- generating 5 to 10 questions
- applying difficulty fallback rules
- avoiding invalid pairs or excessive repetition

## Restrictions
The domain must not:
- open database connections
- make HTTP requests
- render widgets
- read environment variables

---

## 6. Services Layer

## Responsibilities
- orchestrate use cases
- coordinate providers, repositories, and domain rules
- prepare data for UI consumption

## Suggested services

### `play_endless.py`
- start an endless run
- load the next round
- apply an answer
- persist progress

### `play_arcade.py`
- start an arcade run
- end on the first mistake

### `play_historical.py`
- select an eligible date
- load games from that date
- choose a game for the round

### `stats_service.py`
- calculate aggregated stats
- provide leaderboard data

## Rule
The service layer may depend on:
- domain
- repositories
- providers

But it must not know widget or Textual layout details.

---

## 7. Data Layer

## Responsibilities
- SQLite access
- local cache
- external API integration
- mapping between raw payloads and internal models

## Subdivision

### `db.py`
- SQLite engine
- session handling
- database bootstrap

### `schema.py`
SQLModel models:
- `RunRecord`
- `RoundRecord`
- `QuestionRecord`
- `CachedGameRecord`
- `CachedGameStatsRecord`

### `repositories/`
Repositories for reads and writes:
- `RunRepository`
- `StatsRepository`
- `CacheRepository`

### `api/base.py`
Provider interface, for example:

```python
class StatsProvider(Protocol):
    async def get_games_by_date(self, date: str) -> list[GameBoxScore]:
        ...

    async def get_game_boxscore(self, game_id: str) -> GameBoxScore:
        ...
```

### `api/mock_provider.py`
- returns fixed or mocked data
- should be the project's initial data source

### `api/nba_api_provider.py`
- real provider using `nba_api`
- uses cache-first reads for games by date and boxscores by game id
- applies explicit timeout and bounded retry policy for transient upstream failures
- converts external payloads into internal models

---

## 8. TUI Layer

## Responsibilities
- render screens and widgets
- capture user input
- dispatch actions to services
- show loading, error, and success states

## Suggested structure

### `screens/`
- `home.py`
- `game.py`
- `leaderboard.py`
- `stats.py`
- `results.py`
- `settings.py`

### `widgets/`
- `score_panel.py`
- `matchup_card.py`
- `history_panel.py`
- `key_hints.py`
- `animated_reveal.py`

### `styles.tcss`
- visual theme
- borders, layout, spacing, visual states

## Important rule
The screen does not calculate score or generate questions by itself. It only consumes state produced by services and domain logic.

---

## 9. Game Data Flow

### Startup flow
1. app starts
2. database is bootstrapped
3. configuration is loaded
4. the TUI opens the Home Screen

### Run flow
1. user chooses a mode
2. screen triggers the run-start service
3. service gets an eligible game through provider or repository
4. round generator builds the questions
5. state is returned to the UI
6. user answers
7. UI calls the service to apply the answer
8. service uses scoring plus persistence
9. UI updates score, streak, and history
10. when the round ends, the next round is loaded

---

## 10. Cache Data Flow

### Games by date
1. service asks the provider for games on a date
2. provider queries `CacheRepository`
3. if valid cache exists, return cached data
4. otherwise, call the API
5. save the result in cache
6. return domain models

### Historical eligible date index
1. historical service queries `HistoricalIndexRepository` for eligible dates in the configured window
2. if index exists, reuse it immediately
3. otherwise, fetch season-level data, compute dates with enough games, and persist the index
4. gameplay service selects one random indexed date and samples up to the configured round count from the playable games returned for that date

### Box score by game
1. service asks for box score by `game_id`
2. provider checks local cache
3. on cache miss, call the API
4. persist the payload
5. return `GameBoxScore`

---

## 11. Persistence Model

## Main tables

### `runs`
Stores the run as the aggregate unit:
- mode
- source date
- final score
- correct answers
- wrong answers
- best streak
- end reason

### `rounds`
Stores each game used inside the run:
- `run_id`
- `game_id`
- teams
- total questions
- correct and wrong answers in the round
- round score

### `questions`
Stores each individual comparison:
- player A
- player B
- both point totals
- guess
- correctness
- difficulty
- response time

### `cache_games`
Stores games by date or other relevant metadata.

### `cache_game_stats`
Stores detailed box score data per game.

---

## 12. Testability

## What should be tested in domain
- scoring
- difficulty classification
- question generation
- fallback rules
- arcade run termination

## What should be tested in data
- repositories
- database bootstrap
- external payload mapping
- cache hit and miss behavior

## What should be tested in UI
- smoke tests for main screens
- basic navigation
- rendering of critical states

---

## 13. Evolution Strategy

### Phase 1
- `MockProvider`
- functional UI
- functional SQLite
- playable loop

### Phase 2
- real provider
- real cache
- real historical mode
- real yesterday mode

### Phase 3
- UX calibration
- visual improvements
- daily challenge
- reproducible seeds

---

## 14. Intentional Technical Decisions

### Why Python + Textual
- high iteration speed
- good experience for code agents
- sophisticated TUI without excessive infrastructure cost

### Why SQLite
- excellent for single-user local usage
- simple to inspect and maintain
- enough for leaderboard and cache in the MVP

### Why an isolated provider
- mock and real API can coexist
- reduces rework
- simplifies testing

---

## 15. Forbidden Anti-Patterns

- scoring logic inside TUI event handlers
- inline SQL inside screens or widgets
- HTTP calls inside widgets
- circular dependencies between layers
- game rules spread across multiple files without centralization
- repeated magic values in code

---

## 16. Healthy Architecture Criteria

The architecture is healthy when:
- swapping the mock for a real provider does not require rewriting the UI
- score adjustments do not require changing widgets
- leaderboard and stats can be recalculated from the database
- domain tests run without starting the TUI
- the project grows through layers, not lateral coupling
