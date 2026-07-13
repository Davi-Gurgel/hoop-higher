from __future__ import annotations

from pathlib import Path

from platformdirs import user_data_path

APP_NAME = "hoop-higher"
DATABASE_FILENAME = "hoophigher.db"


def default_sqlite_url() -> str:
    """Return the default per-user SQLite URL, preserving legacy local data."""
    legacy_database_path = Path.cwd() / "var" / DATABASE_FILENAME
    if legacy_database_path.is_file():
        database_path = legacy_database_path
    else:
        database_path = user_data_path(APP_NAME, appauthor=False) / DATABASE_FILENAME
    return f"sqlite:///{database_path.resolve()}"
