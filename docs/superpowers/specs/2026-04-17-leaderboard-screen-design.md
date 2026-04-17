# Local Leaderboard Screen Design

## Goal

Implement issue `#21` with a small, reviewable PR that adds a local leaderboard screen backed by persisted run data, limited to the top 10 runs.

## Scope

Included:
- a dedicated leaderboard use case in the service layer
- a leaderboard screen in the Textual UI
- home-screen navigation to open the leaderboard and return back
- rendering of the top 10 persisted runs in explicit, predictable order
- tests for service behavior, navigation, and screen rendering

Excluded:
- online leaderboard
- multiple users
- pagination or scrolling beyond top 10
- merging leaderboard and stats into one screen
- provider or gameplay changes

## Existing Context

The repository already contains the core persistence needed for this feature:
- `RunRecord` stores final score, best streak, mode, and creation time
- `StatsRepository.leaderboard(limit=10)` already returns runs ordered by score descending, best streak descending, correct answers descending, created_at ascending, and id ascending
- the app currently exposes gameplay-only navigation from the home screen to mode select and game screens

This means issue `#21` does not require schema work or changes to gameplay persistence. The missing pieces are service orchestration, a leaderboard screen, and TUI coverage.

## Architecture

### Service layer

Add a dedicated `LeaderboardService` in `src/hoophigher/services/`.

Responsibilities:
- open a database session using the app engine
- call `StatsRepository.leaderboard(limit=10)`
- map `RunRecord` values into a simple presentation-friendly row model
- keep formatting and ordering rules outside the TUI

Planned row shape:
- `rank`
- `mode`
- `score`
- `best_streak`
- `correct_answers`
- `source_date`
- `created_at`

The service will return a small immutable result object containing the leaderboard rows and whether the list is empty. The TUI should not import repositories directly.

### TUI layer

Add `LeaderboardScreen` in `src/hoophigher/tui/screens/`.

Responsibilities:
- request the current leaderboard from `app.leaderboard_service`
- render a top-level title and a concise subtitle explaining this is the local top 10
- render either:
  - the top 10 rows, or
  - an empty state when no runs exist yet
- expose clear navigation back to the home screen

The screen should follow existing non-game screen patterns:
- centered dialog-style layout
- keyboard-first navigation
- reuse existing Textual primitives already used by home and mode-select screens
- no direct database access

### App wiring

Update `HoopHigherApp` to:
- construct `LeaderboardService` during mount using the existing engine
- install the new screen by name
- keep current gameplay wiring unchanged

### Home navigation

Update `HomeScreen` to add a `Leaderboard` button and keybinding path.

The home screen becomes the entry point for:
- play
- leaderboard
- quit

## Data and Ordering Rules

The leaderboard must use persisted local runs only.

Ordering remains explicit and unchanged from the repository implementation:
1. higher `final_score`
2. higher `best_streak`
3. higher `correct_answers`
4. earlier `created_at`
5. lower `id`

The first 10 rows from that ordered result are shown.

The screen should display enough columns to explain ranking without visual overload:
- rank
- mode
- score
- streak
- correct
- date

`source_date` should be shown when present; otherwise the UI may fall back to a placeholder such as `--`.

## Error Handling

This PR should keep failure handling simple and explicit:
- if the leaderboard query returns no runs, show an empty state instead of a blank table
- no special recovery flow is required for database errors in this increment; existing app-level behavior is sufficient

## Testing Strategy

### Service tests

Add tests proving:
- leaderboard results are limited to 10 rows
- ranking order is stable and matches the documented ordering
- empty databases return an empty leaderboard result

These tests should use persisted `RunRecord` data through the existing SQLite test setup.

### TUI tests

Add navigation coverage for:
- home screen can focus and open leaderboard
- leaderboard screen can return to home

Add snapshot coverage for:
- leaderboard with rows
- optionally empty leaderboard state if that can be covered cheaply without overcomplicating fixtures

The goal is to verify the main user flow without adding brittle layout assertions beyond the existing snapshot pattern.

## File Plan

Expected new files:
- `src/hoophigher/services/leaderboard_service.py`
- `src/hoophigher/tui/screens/leaderboard.py`
- `tests/test_services_leaderboard.py`

Expected modified files:
- `src/hoophigher/services/__init__.py`
- `src/hoophigher/tui/screens/__init__.py`
- `src/hoophigher/app.py`
- `src/hoophigher/tui/screens/home.py`
- `tests/test_tui_navigation.py`
- `tests/test_tui_snapshots.py`

## Commit Shape

Keep commits organized into small logical units:
1. `spec:` add leaderboard design doc
2. `feat:` add leaderboard service and tests
3. `feat:` add leaderboard screen and navigation
4. `test:` add snapshot/navigation coverage refinements if they do not fit cleanly in the prior commit

If the implementation lands cleanly in fewer commits, that is acceptable as long as each commit remains coherent and reviewable.

## Risks and Trade-offs

- Reusing `StatsRepository.leaderboard()` keeps the PR small, but it means presentation-oriented aggregation stays split between repository and service. That is acceptable here because the repository already owns the ordering query and the service only shapes output.
- A richer table widget could be added later, but plain Textual layout is preferred for this increment to match the current UI style and avoid unnecessary complexity.
- This PR intentionally does not combine stats and leaderboard work, even though both depend on `StatsRepository`, because issue-driven scope discipline is more important than premature consolidation.
