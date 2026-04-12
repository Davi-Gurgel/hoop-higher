from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from hoophigher.data import (  # noqa: F401 - ensure tables are registered
    schema as _schema,
)

DEFAULT_SQLITE_URL = "sqlite:///./hoophigher.db"
_ALLOWED_SQLITE_JOURNAL_MODES: Final[frozenset[str]] = frozenset(
    {"DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"}
)
_ALLOWED_SQLITE_SYNCHRONOUS: Final[frozenset[str]] = frozenset(
    {"OFF", "NORMAL", "FULL", "EXTRA"}
)


def create_sqlite_engine(
    database_url: str = DEFAULT_SQLITE_URL,
    *,
    echo: bool = False,
    sqlite_journal_mode: str | None = "WAL",
    sqlite_synchronous: str | None = "NORMAL",
    sqlite_busy_timeout_ms: int | None = 5000,
) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
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


def init_db(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
