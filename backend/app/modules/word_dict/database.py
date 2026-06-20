"""
word_lib 独立 SQLite 连接 — 与 kaoyan.db 分离，便于 76 万词条高性能查询。
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class WordLibBase(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def _sql_path() -> Path:
    return get_settings().root / "scripts" / "sql" / "word_lib.sql"


def get_word_lib_engine():
    global _engine, _SessionLocal
    if _engine is not None:
        return _engine

    settings = get_settings()
    db_path = settings.word_lib_db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    _engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.close()

    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_word_lib_session_factory():
    get_word_lib_engine()
    return _SessionLocal


def init_word_lib_db() -> None:
    """建表（若不存在）。"""
    engine = get_word_lib_engine()
    sql_file = _sql_path()
    if sql_file.is_file():
        ddl = sql_file.read_text(encoding="utf-8")
        with engine.connect() as conn:
            for stmt in ddl.split(";"):
                s = stmt.strip()
                if s:
                    conn.exec_driver_sql(s)
            conn.commit()
    else:
        WordLibBase.metadata.create_all(bind=engine)


def get_word_lib_db():
    """FastAPI 依赖：word_lib Session。"""
    factory = get_word_lib_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()
