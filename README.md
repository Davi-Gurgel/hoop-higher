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
uv run python main.py
```

Run tests:

```bash
uv run pytest
```
