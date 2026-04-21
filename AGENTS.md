# OpenCode & AI Agent Instructions

This file contains high-signal context and conventions for autonomous coding agents working on the `hoop-higher` repository.

## Commands & Workflows

- **Dependency Management:** Use `uv` exclusively. Do not use `pip`, `pipenv`, or `poetry`.
  - Sync dependencies: `uv sync --all-groups`
  - Add packages: `uv add <pkg>`
  - Run app: `uv run hoop-higher`
- **Fast Local Dev:** Prepend `HOOPHIGHER_STATS_PROVIDER=mock` when running the app locally to bypass external API calls and use immediate mock data (`HOOPHIGHER_STATS_PROVIDER=mock uv run hoop-higher`).
- **Testing:** `uv run pytest`.
- **TUI Snapshots:** Textual UI snapshot tests live in `tests/test_tui_snapshots.py`. When you make visual layout changes, regenerate snapshots using: `uv run pytest --snapshot-update`.
- **Linting & Formatting:** `uv run ruff check src tests` and `uv run ruff format src tests`.

## Architecture & Boundaries

- **Domain Layer (`src/hoophigher/domain/`):** Pure business logic (models, scoring rules). Must remain independent of Textual or external APIs like `nba_api`.
- **Data Layer (`src/hoophigher/data/`):** External API providers (`mock` vs `nba_api`) and SQLite/SQLModel persistence logic.
- **Service Layer (`src/hoophigher/services/`):** Application services that coordinate domain and data layers. Consumed by the UI.
- **TUI Layer (`src/hoophigher/tui/`):** Textual screens, widgets, and `.tcss` styles. Should primarily read state/actions from `services/`.
- **Config (`src/hoophigher/config.py`):** Relies on `pydantic-settings`. All environment variables must be prefixed with `HOOPHIGHER_`.

## TUI Quirks (Textual)

- **Debugging:** Avoid `print()` for debugging as it breaks the Textual terminal render. Instead, write to a log file or use Textual's logging mechanisms.
- **Styling:** CSS-like styling is stored in `src/hoophigher/tui/styles.tcss`. 

## Publishing

- The package automatically publishes to PyPI on GitHub tag pushes (via `.github/workflows/publish.yml`).
- When asked to cut a release: update the `version` field in `pyproject.toml`, then push a semantic version tag (e.g., `git tag v0.1.1` and `git push origin v0.1.1`).
