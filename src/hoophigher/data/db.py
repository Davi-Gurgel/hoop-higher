from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

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
) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, echo=echo, connect_args=connect_args)


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
