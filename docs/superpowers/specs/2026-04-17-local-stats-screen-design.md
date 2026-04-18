# Local Stats Screen Design

## Goal

Implement issue `#24` with a small, reviewable PR that adds a local stats screen backed by persisted run data and a dedicated service for MVP aggregate metrics.

## Scope

Included:
- a dedicated stats use case in the service layer
- a stats screen in the Textual UI
- home-screen navigation to open stats and return back
- rendering of the MVP local metrics defined in `SPEC.md`
- tests for aggregate calculations, navigation, and screen rendering

Excluded:
- persisted stats snapshots
- analytics remotos
- metrics beyond the MVP set in `SPEC.md`
- stats entry points from non-home screens
- gameplay, provider, or schema changes

## Existing Context

The repository already contains the persistence needed for this feature:
- `RunRecord` stores mode, final score, correct answers, wrong answers, best streak, and creation time
- `StatsRepository` already exposes count and aggregate helpers for runs, questions, best score, best streak, and mode distribution
- the app already follows a clear pattern for read-only screens through `LeaderboardService`, `LeaderboardScreen`, and home-screen navigation

This means issue `#24` does not require schema work or gameplay persistence changes. The missing pieces are service orchestration, a stats screen, and TUI coverage.

## Architecture

### Service layer

Add a dedicated `StatsService` in `src/hoophigher/services/`.

Responsibilities:
- open a database session using the app engine
- read persisted aggregate inputs through `StatsRepository`
- shape those values into a presentation-friendly result object
- keep all metric calculations and defaults outside the TUI

Planned result shape:
- `total_runs`
- `total_answered_questions`
- `total_correct_answers`
- `accuracy_rate`
- `best_score`
- `best_streak`
- `mode_distribution`

The service should return a small immutable result object with safe defaults for the empty-database case. The TUI should not import repositories directly.

### Aggregation rules

The screen must expose the MVP metrics from `SPEC.md`:
- total runs
- total perguntas respondidas
- total de acertos
- percentual de acerto
- melhor score
- melhor streak
- distribuição por modo

Implementation rules:
- `total_answered_questions` is derived from persisted answered-question data, not from UI state
- `accuracy_rate` is `0.0` when no answered questions exist
- `best_score` and `best_streak` fall back to `0` when the database has no runs
- `mode_distribution` includes only persisted modes with data; the screen decides whether to render missing modes as zero rows or omit them

This keeps the service responsible for business-facing numbers while leaving display formatting to the UI layer.

### TUI layer

Add `StatsScreen` in `src/hoophigher/tui/screens/stats.py`.

Responsibilities:
- request current stats from `app.stats_service`
- render a title and concise subtitle explaining these are local machine stats
- render the aggregate metrics in a compact read-only layout
- expose a clear path back to the home screen

The screen should follow existing non-game screen patterns:
- centered dialog-style layout
- keyboard-first navigation
- reuse existing Textual primitives already used by home and leaderboard screens
- no direct database access

### App wiring

Update `HoopHigherApp` to:
- construct `StatsService` during mount using the existing engine
- install the new screen by name
- keep current gameplay and leaderboard wiring unchanged

### Home navigation

Update `HomeScreen` to add a `Stats` button and keybinding path.

The home screen becomes the entry point for:
- play
- leaderboard
- stats
- quit

This PR explicitly limits stats navigation to `Home -> Stats`.

## Error Handling

This PR should keep failure handling simple and explicit:
- if no runs exist, the screen still renders with zero/default values
- no special recovery flow is required for database errors in this increment; existing app-level behavior is sufficient

## Testing Strategy

### Service tests

Add tests proving:
- stats aggregate correctly across multiple runs and modes
- accuracy rate handles both populated and empty datasets correctly
- best score and best streak fall back to zero when no runs exist
- mode distribution reflects persisted run counts

These tests should use persisted `RunRecord` and question data through the existing SQLite test setup.

### TUI tests

Add navigation coverage for:
- home screen can focus and open stats
- stats screen can return to home

Add snapshot coverage for:
- stats screen with populated values
- empty stats state if that can be added cleanly without overcomplicating fixtures

The goal is to verify the main user flow without adding brittle layout assertions beyond the existing snapshot pattern.

## File Plan

Expected new files:
- `src/hoophigher/services/stats_service.py`
- `src/hoophigher/tui/screens/stats.py`
- `tests/test_services_stats.py`

Expected modified files:
- `src/hoophigher/services/__init__.py`
- `src/hoophigher/tui/screens/__init__.py`
- `src/hoophigher/app.py`
- `src/hoophigher/tui/screens/home.py`
- `tests/test_tui_navigation.py`
- `tests/test_tui_snapshots.py`

Potentially modified files:
- `src/hoophigher/data/repositories/stats_repository.py`

That repository file should only change if the existing helpers are insufficient for a clean service implementation. Prefer reusing the current API to keep the PR small.

## Commit Shape

Keep commits organized into small logical units:
1. `spec:` add local stats screen design doc
2. `feat:` add stats service and tests
3. `feat:` add stats screen and home navigation
4. `test:` add snapshot and navigation coverage refinements if they do not fit cleanly in the prior commit

If the implementation lands cleanly in fewer commits, that is acceptable as long as each commit remains coherent and reviewable.

## Risks and Trade-offs

- Computing aggregates on read is slightly less optimized than a persisted projection, but it keeps the PR aligned with issue `#24`, avoids schema churn, and is sufficient for the expected local SQLite data volume.
- Reusing `StatsRepository` keeps the change small, but some display-oriented shaping still happens in the service. That is acceptable because the service owns the feature-facing result contract.
- The screen intentionally stays read-only and home-accessible only. Broader stats navigation can be added later if it becomes a real UX need.
