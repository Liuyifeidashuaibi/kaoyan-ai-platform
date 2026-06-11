"""
数据库连接与 ORM 模型定义（SQLite + SQLAlchemy）。
"""

from datetime import datetime

from sqlalchemy import (
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
    name = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    questions = relationship("WrongQuestion", back_populates="category")


class WrongQuestion(Base):
    """错题本条目。"""

    __tablename__ = "wrong_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey("wq_categories.id"), nullable=False)
    title = Column(String(200), default="未命名错题")
    image_path = Column(String(500), nullable=False)
    notes = Column(Text, default="")  # 用户 Markdown 笔记
    ai_analysis = Column(Text, nullable=True)  # AI 解析（可选）
    created_at = Column(DateTime, default=datetime.utcnow)

    category = relationship("WrongQuestionCategory", back_populates="questions")


def init_db() -> None:
    """创建所有表（若不存在）。"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI 依赖注入：获取数据库 Session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
