from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Final

from sqlalchemy import event
from sqlalchemy.engine import Connection, Engine, make_url
from sqlmodel import Session, SQLModel, create_engine

from hoophigher.data import (  # noqa: F401 - ensure tables are registered
    schema as _schema,
)
from hoophigher.paths import (  # noqa: F401 - preserve public data-layer helpers
    APP_NAME,
    DATABASE_FILENAME,
    default_sqlite_url,
)

_ALLOWED_SQLITE_JOURNAL_MODES: Final[frozenset[str]] = frozenset(
    {"DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"}
)
_ALLOWED_SQLITE_SYNCHRONOUS: Final[frozenset[str]] = frozenset({"OFF", "NORMAL", "FULL", "EXTRA"})


def create_sqlite_engine(
    database_url: str,
    *,
    echo: bool = False,
    sqlite_journal_mode: str | None = "WAL",
    sqlite_synchronous: str | None = "NORMAL",
    sqlite_busy_timeout_ms: int | None = 5000,
) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    _ensure_sqlite_parent_directory(database_url)
    engine = create_engine(database_url, echo=echo, connect_args=connect_args)

    if _is_file_backed_sqlite_url(database_url):
        validated_journal_mode = _normalize_sqlite_pragma_value(
            sqlite_journal_mode,
            setting_name="sqlite_journal_mode",
            allowed_values=_ALLOWED_SQLITE_JOURNAL_MODES,
        )
        validated_synchronous = _normalize_sqlite_pragma_value(
            sqlite_synchronous,
            setting_name="sqlite_synchronous",
            allowed_values=_ALLOWED_SQLITE_SYNCHRONOUS,
        )
        validated_busy_timeout_ms = _validate_busy_timeout_ms(sqlite_busy_timeout_ms)

        @event.listens_for(engine, "connect")
        def _configure_sqlite(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            if validated_journal_mode is not None:
                cursor.execute(f"PRAGMA journal_mode={validated_journal_mode};")
            if validated_synchronous is not None:
                cursor.execute(f"PRAGMA synchronous={validated_synchronous};")
            if validated_busy_timeout_ms is not None:
                cursor.execute(f"PRAGMA busy_timeout={validated_busy_timeout_ms:d};")
            cursor.close()

    return engine


def _ensure_sqlite_parent_directory(database_url: str) -> None:
    if not _is_file_backed_sqlite_url(database_url):
        return
    sqlite_path = make_url(database_url).database
    if sqlite_path is None:
        return
    Path(sqlite_path).expanduser().parent.mkdir(parents=True, exist_ok=True)


def _is_file_backed_sqlite_url(database_url: str) -> bool:
    if not database_url.startswith("sqlite:///"):
        return False
    return ":memory:" not in database_url


def _normalize_sqlite_pragma_value(
    value: str | None,
    *,
    setting_name: str,
    allowed_values: frozenset[str],
) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    if normalized not in allowed_values:
        allowed = ", ".join(sorted(allowed_values))
        raise ValueError(f"{setting_name} must be one of: {allowed}")
    return normalized


def _validate_busy_timeout_ms(value: int | None) -> int | None:
    if value is None:
        return None
    if value < 0:
        raise ValueError("sqlite_busy_timeout_ms must be >= 0")
    return value


# Columns removed from the schema but present in databases created by older
# versions. create_all never drops columns, and the NOT NULL ones would reject
# inserts once the model stops providing values, so they are dropped on startup.
_STALE_COLUMNS: Final[tuple[tuple[str, str], ...]] = (
    ("rounds", "total_questions"),
    ("questions", "player_a_id"),
    ("questions", "player_a_team_id"),
    ("questions", "player_a_minutes"),
    ("questions", "player_b_id"),
    ("questions", "player_b_team_id"),
    ("questions", "player_b_minutes"),
    ("questions", "revealed_points"),
    ("questions", "response_time_ms"),
)


def init_db(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
    _drop_stale_columns(engine)


def _existing_columns(connection: Connection, table: str) -> set[str]:
    rows = connection.exec_driver_sql(f'PRAGMA table_info("{table}")')
    return {row[1] for row in rows}


def _droppable_index_names(connection: Connection, table: str) -> list[str]:
    rows = connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = ?",
        (table,),
    )
    return [name for (name,) in rows if not name.startswith("sqlite_autoindex_")]


def _index_columns(connection: Connection, index_name: str) -> set[str]:
    rows = connection.exec_driver_sql(f'PRAGMA index_info("{index_name}")')
    return {row[2] for row in rows}


def _drop_stale_columns(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    stale_columns_by_table: dict[str, list[str]] = {}
    for table, column in _STALE_COLUMNS:
        stale_columns_by_table.setdefault(table, []).append(column)

    with engine.begin() as connection:
        for table, candidate_columns in stale_columns_by_table.items():
            existing_columns = _existing_columns(connection, table)
            stale_columns = [column for column in candidate_columns if column in existing_columns]
            if not stale_columns:
                continue

            stale_columns_set = set(stale_columns)
            stale_index_names = [
                index_name
                for index_name in _droppable_index_names(connection, table)
                if _index_columns(connection, index_name) & stale_columns_set
            ]

            # The helpers above return fully materialized containers; issuing
            # DDL while a schema-reading cursor is still open locks the
            # connection ("database table is locked").
            for index_name in stale_index_names:
                connection.exec_driver_sql(f'DROP INDEX IF EXISTS "{index_name}"')
            for column in stale_columns:
                connection.exec_driver_sql(f'ALTER TABLE "{table}" DROP COLUMN "{column}"')


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
