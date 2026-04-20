# Hoop Higher

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/release/python-3130/)
[![Textual](https://img.shields.io/badge/GUI-Textual-green.svg)](https://github.com/Textualize/textual)

A modern terminal-based game inspired by "Higher or Lower", utilizing real NBA player point totals. Built natively with Python and Textual to provide a sleek, fast, and responsive TUI experience.

## Features

* **Multiple Game Modes:**
  * **Endless:** Keep playing and building your score multiplier. Wrong answers deduct points, but don't end the game!
  * **Arcade:** Strive for perfection. One wrong answer and your run is over.
  * **Historical:** Journey back in time! Play rounds using real NBA game data sampled from random historical dates across defined eras.
* **Live & Cached NBA Data:** Seamlessly interfaces with the real NBA stats API, falling back on an intelligent SQLite-backed caching layer for speed and resilience.
* **Fast & Tactile UI:** A beautiful TUI architecture built with `Textual`, featuring keyboard shortcuts, fluid layouts, and immediate visual feedback.
* **Local Leaderboards:** Track your high scores, best streaks, and overall stats locally via SQLModel and SQLite.

## Tech Stack

* **Language:** Python 3.13+
* **TUI Framework:** [Textual](https://textual.textualize.io/)
* **Database:** SQLite
* **ORM:** [SQLModel](https://sqlmodel.tiangolo.com/)
* **HTTP Client:** `httpx` and `nba_api`
* **Configuration:** `pydantic-settings`
* **Package Manager:** `uv`
* **Testing:** `pytest`

## Installation and Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Davi-Gurgel/hoop-higher.git
   cd hoop-higher
   ```

2. **Set up the virtual environment using `uv`:**
   ```bash
   uv venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   uv sync --all-groups
   ```

4. **Run the game:**
   ```bash
   uv run hoophigher
   ```

## Install from PyPI 📦

Once published, you can run Hoop Higher without cloning the repo.

* **Run with `uvx` (ephemeral):**
  ```bash
  uvx hoop-higher
  ```
* **Install with `pipx` (persistent):**
  ```bash
  pipx install hoop-higher
  hoop-higher
  ```

## Configuration ⚙️

Customize the app's behavior by overriding these environment variables (all prefixed with `HOOPHIGHER_`):

* **`HOOPHIGHER_STATS_PROVIDER`**
  * `nba_api` (default): Uses real NBA data with a SQLite caching layer.
  * `mock`: Uses pre-populated mock data for incredibly fast local development and testing.
* **`HOOPHIGHER_HISTORICAL_START_YEAR`** (default: `2010`)
* **`HOOPHIGHER_HISTORICAL_END_YEAR`** (default: `2020`)
* **`HOOPHIGHER_HISTORICAL_ROUNDS`** (default: `5`)
* **`HOOPHIGHER_NBA_API_TIMEOUT_SECONDS`** (default: `20`)

*Note: Historical mode intelligently probes and samples available games on the fly, avoiding massive initial database syncs and ensuring a fast start.*

## Local Development & Testing

Code quality, formatting, and tests are heavily utilized in this repository.

* **Run all tests:**
  ```bash
  uv run pytest
  ```
* **Linting & Formatting:** (via ruff)
  ```bash
  uv run ruff check src tests
  ```

## Publishing to PyPI 🛰️

This repository includes automated publishing via GitHub Actions in `.github/workflows/publish.yml`.

1. Create your package on PyPI (first time only) and configure a **Trusted Publisher** pointing to this repository and workflow.
2. Bump `version` in `pyproject.toml`.
3. Create and push a version tag (must match `v*`):
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

After the workflow succeeds, users can run `uvx hoop-higher` or `pipx install hoop-higher`.

---
*For more architectural guidelines and decisions, view [ARCHITECTURE.md](ARCHITECTURE.md) and [AGENTS.md](AGENTS.md).*
