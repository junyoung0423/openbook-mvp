"""DB 엔진/세션 생성."""

from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_SQLITE_URL = "sqlite:///./openbook.db"


def database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL)


def create_db_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    target = url or database_url()
    kwargs: dict = {"echo": echo, "future": True}
    if target.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(target, **kwargs)
    if target.startswith("sqlite"):
        _enable_sqlite_foreign_keys(engine)
    return engine


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def session_scope(engine: Engine) -> Iterator[Session]:
    factory = make_session_factory(engine)
    with factory.begin() as session:
        yield session
