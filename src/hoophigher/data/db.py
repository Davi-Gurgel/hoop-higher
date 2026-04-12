from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from hoophigher.data import (  # noqa: F401 - ensure tables are registered
    schema as _schema,
)

DEFAULT_SQLITE_URL = "sqlite:///./hoophigher.db"


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

        @event.listens_for(engine, "connect")
        def _configure_sqlite(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            if sqlite_journal_mode is not None:
                cursor.execute(f"PRAGMA journal_mode={sqlite_journal_mode};")
            if sqlite_synchronous is not None:
                cursor.execute(f"PRAGMA synchronous={sqlite_synchronous};")
            if sqlite_busy_timeout_ms is not None:
                cursor.execute(f"PRAGMA busy_timeout={sqlite_busy_timeout_ms:d};")
            cursor.close()

    return engine


def _is_file_backed_sqlite_url(database_url: str) -> bool:
    if not database_url.startswith("sqlite:///"):
        return False
    return ":memory:" not in database_url


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
