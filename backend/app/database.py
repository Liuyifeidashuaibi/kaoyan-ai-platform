"""
数据库连接与 ORM 模型定义（SQLite + SQLAlchemy）。
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from app.config import get_settings

settings = get_settings()

# SQLite 数据库文件放在项目根目录
_db_path = settings.root / "kaoyan.db"
engine = create_engine(
    f"sqlite:///{_db_path}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """ORM 基类。"""


class ChatSession(Base):
    """聊天会话 — 左侧历史列表中的一条记录。"""

    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True)
    title = Column(String(200), default="新对话")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """单条聊天消息（用户 / 助手）。"""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user / assistant / system
    content = Column(Text, nullable=False)
    image_path = Column(String(500), nullable=True)  # 用户上传的图片相对路径
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")


class WrongQuestionCategory(Base):
    """错题本科目分类，如「数学一」「政治」。"""

    __tablename__ = "wq_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    user_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    questions = relationship("WrongQuestion", back_populates="category")


class WrongQuestion(Base):
    """错题本 / 学习资料条目。"""

    __tablename__ = "wrong_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey("wq_categories.id"), nullable=False)
    user_id = Column(String(36), nullable=True, index=True)
    is_public = Column(Boolean, default=False, nullable=False)
    title = Column(String(200), default="未命名资料")
    image_path = Column(String(500), nullable=False)  # 兼容旧数据，新记录与 file_path 同步
    file_path = Column(String(500), nullable=True)
    file_type = Column(String(20), default="image")  # image / video / document / audio / other
    original_filename = Column(String(255), nullable=True)
    notes = Column(Text, default="")  # 用户 Markdown 笔记
    ai_analysis = Column(Text, nullable=True)  # AI 解析（可选，仅图片）
    created_at = Column(DateTime, default=datetime.utcnow)

    category = relationship("WrongQuestionCategory", back_populates="questions")


def _migrate_wrong_questions_columns() -> None:
    """为已有 SQLite 库补充多类型资料字段。"""
    with engine.connect() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(wrong_questions)").fetchall()
        columns = {row[1] for row in rows}
        if "file_path" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE wrong_questions ADD COLUMN file_path VARCHAR(500)"
            )
        if "file_type" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE wrong_questions ADD COLUMN file_type VARCHAR(20) DEFAULT 'image'"
            )
        if "original_filename" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE wrong_questions ADD COLUMN original_filename VARCHAR(255)"
            )
        conn.exec_driver_sql(
            "UPDATE wrong_questions SET file_path = image_path "
            "WHERE file_path IS NULL OR file_path = ''"
        )
        conn.exec_driver_sql(
            "UPDATE wrong_questions SET file_type = 'image' "
            "WHERE file_type IS NULL OR file_type = ''"
        )
        conn.commit()


def _migrate_wq_user_scoping() -> None:
    """补充用户归属与公开状态字段，并将分类改为按用户隔离。"""
    dev_user = "00000000-0000-0000-0000-000000000001"
    with engine.connect() as conn:
        wq_rows = conn.exec_driver_sql("PRAGMA table_info(wrong_questions)").fetchall()
        wq_cols = {row[1] for row in wq_rows}
        if "user_id" not in wq_cols:
            conn.exec_driver_sql(
                "ALTER TABLE wrong_questions ADD COLUMN user_id VARCHAR(36)"
            )
        if "is_public" not in wq_cols:
            conn.exec_driver_sql(
                "ALTER TABLE wrong_questions ADD COLUMN is_public BOOLEAN DEFAULT 0"
            )
            conn.exec_driver_sql(
                "UPDATE wrong_questions SET is_public = 0 WHERE is_public IS NULL"
            )

        cat_rows = conn.exec_driver_sql("PRAGMA table_info(wq_categories)").fetchall()
        cat_cols = {row[1] for row in cat_rows}
        if "user_id" not in cat_cols:
            conn.exec_driver_sql(
                """
                CREATE TABLE wq_categories_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100) NOT NULL,
                    user_id VARCHAR(36),
                    created_at DATETIME
                )
                """
            )
            conn.exec_driver_sql(
                """
                INSERT INTO wq_categories_new (id, name, created_at)
                SELECT id, name, created_at FROM wq_categories
                """
            )
            conn.exec_driver_sql("DROP TABLE wq_categories")
            conn.exec_driver_sql(
                "ALTER TABLE wq_categories_new RENAME TO wq_categories"
            )

        conn.exec_driver_sql(
            f"UPDATE wrong_questions SET user_id = '{dev_user}' WHERE user_id IS NULL"
        )
        conn.exec_driver_sql(
            f"UPDATE wq_categories SET user_id = '{dev_user}' WHERE user_id IS NULL"
        )
        conn.commit()


def init_db() -> None:
    """创建所有表（若不存在）并执行轻量迁移。"""
    Base.metadata.create_all(bind=engine)
    _migrate_wrong_questions_columns()
    _migrate_wq_user_scoping()


def get_db():
    """FastAPI 依赖注入：获取数据库 Session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
