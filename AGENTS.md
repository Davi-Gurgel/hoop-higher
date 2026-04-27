# Repository Guidelines

## Project Structure & Module Organization

`hoop-higher` is a Python 3.13 Textual TUI app with package code in `src/hoophigher/`.

- `src/hoophigher/domain/`: pure game models, scoring, difficulty, and round generation. Keep it independent of Textual, persistence, and external APIs.
- `src/hoophigher/data/`: API providers, SQLModel schema, database, cache, and repositories.
- `src/hoophigher/services/`: orchestration layer consumed by the UI.
- `src/hoophigher/tui/`: Textual app screens, widgets, and `styles.tcss`.
- `tests/`: pytest tests, including Textual snapshots in `tests/__snapshots__/`.
- `docs/assets/`: documentation images and static assets.

## Build, Test, and Development Commands

Use `uv` exclusively. Do not install dependencies with `pip`, Poetry, or Pipenv.

- `uv sync --all-groups`: install runtime and dev dependencies.
- `HOOPHIGHER_STATS_PROVIDER=mock uv run hoop-higher`: run the TUI with mock stats for fast local startup.
- `uv run pytest`: run the full test suite.
- `uv run pytest --snapshot-update`: regenerate snapshots after intentional layout changes.
- `uv run ruff check src tests`: lint source and tests.
- `uv run ruff format src tests`: format source and tests.

If `.venv/` exists, use it. If missing, create it with `uv venv` before running Python commands.

## Coding Style & Naming Conventions

Follow standard Python style with 4-space indentation and clear module boundaries. Use `snake_case` for functions, modules, and variables; `PascalCase` for classes; and `UPPER_SNAKE_CASE` for constants.

Keep domain logic deterministic and framework-free. UI code belongs under `tui/` and should read state/actions from services. Avoid `print()` in Textual code because it disrupts terminal rendering; use logging or a file.

## Testing Guidelines

Tests use `pytest`. Name files `test_*.py` and functions `test_*`. Place focused tests near the relevant layer: domain behavior in domain tests, repositories in data tests, service flows in service tests, and Textual behavior in TUI tests.

When changing layouts, screens, widgets, or `styles.tcss`, update snapshots only for intentional visual changes.

## Commit & Pull Request Guidelines

Recent history uses concise imperative subjects and prefixes such as `fix:`, `chore:`, `docs:`, and `refactor:`. Prefer examples like `fix: stabilize tui snapshots` or `docs: refresh readme commands`.

Pull requests must always follow `.github/pull_request_template.md` and keep its section pattern: Summary, Changes, Validation, Screenshots / Snapshots, Risk & Rollback, and Checklist. Fill each section explicitly; use `Not applicable` only when it truly applies.

## Security & Configuration Tips

Configuration is handled through `src/hoophigher/config.py` with `pydantic-settings`. Environment variables must use the `HOOPHIGHER_` prefix. Keep secrets out of version control; use `.env.example` as the public reference for expected settings.
