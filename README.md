# Hoop Higher

Terminal game inspired by Higher or Lower using NBA player point totals.

## Stack

- Python 3.13+
- Textual
- SQLite
- SQLModel
- httpx
- pydantic-settings
- pytest
- uv

## Development

Create or reuse the virtual environment:

```bash
uv venv
source .venv/bin/activate
```

Install dependencies:

```bash
uv sync --all-groups
```

Run the app:

```bash
uv run hoophigher
```

Run tests:

```bash
uv run pytest
```

## Configuration

The app reads environment variables with the `HOOPHIGHER_` prefix.

### Provider selection

- `HOOPHIGHER_STATS_PROVIDER`
  - `nba_api` (default): real NBA data with SQLite-backed cache.
  - `mock`: local mock data for fast development.

### Historical mode controls

- `HOOPHIGHER_HISTORICAL_START_YEAR` (default: `2010`)
- `HOOPHIGHER_HISTORICAL_END_YEAR` (default: `2020`)
- `HOOPHIGHER_HISTORICAL_ROUNDS` (default: `5`)

Historical mode selects one random eligible date inside the configured year window, then samples exactly `HOOPHIGHER_HISTORICAL_ROUNDS` games from that date.

### nba_api timeout

- `HOOPHIGHER_NBA_API_TIMEOUT_SECONDS` (default: `20`)

Used for scoreboard and boxscore requests when `HOOPHIGHER_STATS_PROVIDER=nba_api`.

## Real data behavior

By default, or when `HOOPHIGHER_STATS_PROVIDER=nba_api`:

- The app uses cache-first reads for games-by-date and game boxscores.
- Historical mode builds and persists an eligible-date index in SQLite for the configured window.
- First historical run can take longer while the date index is built.
- Later historical runs reuse the persisted index and local cache to reduce requests.
- Upstream failures are surfaced as explicit errors instead of silent fallbacks.
