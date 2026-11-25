"""DB 엔진/세션 생성."""

from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_SQLITE_URL = "sqlite:///./openbook.db"


def normalize_url(url: str) -> str:
    """Vercel·Neon이 주는 postgres://… 주소를 SQLAlchemy psycopg 3 드라이버 주소로 바꾼다."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def database_url() -> str:
    return normalize_url(os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL))


def create_db_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    target = normalize_url(url) if url else database_url()
    kwargs: dict = {"echo": echo, "future": True}
    if target.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:  # 서버리스: 쉬는 동안 끊긴 연결을 쓰기 전에 확인, 연결 수는 작게
        kwargs.update(pool_pre_ping=True, pool_size=2, max_overflow=3, pool_recycle=300)
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
