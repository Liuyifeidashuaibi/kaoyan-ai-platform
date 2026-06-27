#!/usr/bin/env python3
"""
SQLite → PostgreSQL 数据迁移脚本（商用正式环境部署用）。

把本地 kaoyan.db（SQLite）里的业务数据迁移到目标数据库（通常由 DATABASE_URL 指向的 Postgres）。
全程走 SQLAlchemy ORM，自动处理方言差异，不写裸 SQL。

用法（项目根目录，先确保目标库可达）：
  DATABASE_URL="postgresql+psycopg://kaoyan:kaoyan_dev@localhost:5432/kaoyan" \
      python backend/scripts/migrate_sqlite_to_pg.py

幂等：以主键存在为判定，已迁移的行会跳过，可安全重复执行。
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 迁移的表与对应 ORM 模型（保持外键依赖顺序：父表在前）
# Agent 商用层表为空时自动跳过，无需手动维护。
from app.database import (  # noqa: E402
    Base,
    ChatSession,
    ChatMessage,
    ExamPaper,
    WrongQuestion,
    WrongQuestionCategory,
)


def _build_sqlite_engine(root: Path):
    """连接源 SQLite（项目根 kaoyan.db）。"""
    src = root / "kaoyan.db"
    if not src.is_file():
        logger.error("源 SQLite 不存在: %s", src)
        sys.exit(1)
    url = f"sqlite:///{src.as_posix()}"
    logger.info("源数据库 (SQLite): %s", url)
    return create_engine(url)


def _build_dst_engine():
    """连接目标数据库（DATABASE_URL，默认仍是同一 SQLite —— 此时迁移无意义但允许跑）。"""
    from app.config import get_settings

    settings = get_settings()
    url = settings.effective_database_url
    if url.startswith("sqlite"):
        logger.warning("DATABASE_URL 未配置或仍为 SQLite，目标与源可能相同，迁移无意义。")
    logger.info("目标数据库: %s", url)
    return create_engine(url, pool_pre_ping=True)


def _existing_pks(dst_session: Session, model, pk_values: list) -> set:
    """查询目标库已存在的主键集合，用于幂等跳过。"""
    if not pk_values:
        return set()
    pk_col = inspect(model).primary_key[0].name
    rows = dst_session.query(getattr(model, pk_col)).filter(
        getattr(model, pk_col).in_(pk_values)
    ).all()
    return {r[0] for r in rows}


def _migrate_model(src_session: Session, dst_session: Session, model, label: str) -> int:
    """按主键幂等迁移单个模型。返回新写入行数。"""
    rows = src_session.query(model).all()
    if not rows:
        logger.info("[%s] 源无数据，跳过", label)
        return 0

    pk_col = inspect(model).primary_key[0].name
    pk_values = [getattr(r, pk_col) for r in rows]
    existing = _existing_pks(dst_session, model, pk_values)

    inserted = 0
    for row in rows:
        pk = getattr(row, pk_col)
        if pk in existing:
            continue
        # 脱离源 session，挂到目标 session
        src_session.expunge(row)
        # 重新构造一个干净对象，避免 instance state 跨 session 污染
        data = {c.name: getattr(row, c.name) for c in row.__table__.columns}
        dst_session.add(model(**data))
        inserted += 1

    dst_session.commit()
    logger.info("[%s] 迁移完成: 新增 %d / 共 %d", label, inserted, len(rows))
    return inserted


def main() -> None:
    start = datetime.now()
    from app.config import get_settings

    settings = get_settings()
    src_engine = _build_sqlite_engine(settings.root)
    dst_engine = _build_dst_engine()

    # 目标库先建表（幂等）
    Base.metadata.create_all(bind=dst_engine)
    logger.info("目标库表结构已确保存在")

    SrcSession = sessionmaker(bind=src_engine)
    DstSession = sessionmaker(bind=dst_engine)

    total = 0
    src_session = SrcSession()
    dst_session = DstSession()
    try:
        # 顺序遵循外键依赖：父表（session/category）→ 子表（message/question/paper）
        plan = [
            (ChatSession, "chat_sessions"),
            (ChatMessage, "chat_messages"),
            (WrongQuestionCategory, "wq_categories"),
            (WrongQuestion, "wrong_questions"),
            (ExamPaper, "exam_papers"),
        ]
        for model, label in plan:
            total += _migrate_model(src_session, dst_session, model, label)
    finally:
        src_session.close()
        dst_session.close()

    elapsed = (datetime.now() - start).total_seconds()
    logger.info("✅ 迁移完成: 共新增 %d 行，耗时 %.1fs", total, elapsed)


if __name__ == "__main__":
    main()
