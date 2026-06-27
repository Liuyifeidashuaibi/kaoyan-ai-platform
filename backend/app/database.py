"""
数据库连接与 ORM 模型定义。

支持两种后端：
  - PostgreSQL（商用正式环境）：设置 DATABASE_URL=postgresql://...
  - SQLite（本地开发默认）：kaoyan.db 单文件

新增 Agent 商用层表：AgentTask / AgentTaskStep / AgentTemplate / AgentGeneratedFile，
支撑任务审计、模板管理、文件资产清单等商用能力。
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from app.config import get_settings

settings = get_settings()

# 方言自适应引擎：PostgreSQL（生产）或 SQLite（本地）透明切换
engine = create_engine(
    settings.effective_database_url,
    # SQLite 单连接并发限制；其它后端不传该参数
    connect_args={"check_same_thread": False} if settings.effective_database_url.startswith("sqlite") else {},
    pool_pre_ping=True,
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
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False, index=True)
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


class ExamPaper(Base):
    """试卷解析记录 — 英语/数学试卷 OCR + 结构化 + 分析结果。"""

    __tablename__ = "exam_papers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=True, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    subject = Column(String(20), nullable=False)          # "english" | "math"
    title = Column(String(200), default="未命名试卷")
    original_image_path = Column(String(500), nullable=True)
    ocr_text = Column(Text, nullable=True)
    parsed_structure = Column(Text, nullable=True)        # JSON string
    analysis_result = Column(Text, nullable=True)         # JSON string
    status = Column(String(20), default="pending")        # pending/processing/done/failed
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)          # 7天TTL

    session = relationship("ChatSession", backref="exam_papers")


# ── Agent 商用层 ORM 表 ────────────────────────────────────
# 持久化任务审计、模板配置、文件资产清单，满足企业商用交付要求。


class AgentTask(Base):
    """Agent 任务记录 — 全链路审计主表。

    每次 Agent 任务（用户一次提问触发的完整工作流）对应一条记录，
    持久化到数据库（替代旧的内存字典），重启不丢失。
    """

    __tablename__ = "agent_tasks"

    task_id = Column(String(64), primary_key=True)
    session_id = Column(String(36), nullable=True, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    user_input = Column(Text, default="")
    status = Column(String(20), default="running", index=True)  # running/completed/failed
    final_output = Column(Text, default="")
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    total_duration_ms = Column(Float, default=0.0)
    success = Column(Boolean, default=False)
    error = Column(Text, default="")

    steps = relationship(
        "AgentTaskStep",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="AgentTaskStep.step_id",
    )
    files = relationship(
        "AgentGeneratedFile",
        back_populates="task",
        cascade="all, delete-orphan",
    )


class AgentTaskStep(Base):
    """Agent 任务单步执行记录 — 工具调用审计明细。"""

    __tablename__ = "agent_task_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), ForeignKey("agent_tasks.task_id"), nullable=False, index=True)
    step_id = Column(Integer, nullable=False)             # 轮内步骤序号
    round_idx = Column(Integer, nullable=False, default=0)
    tool_name = Column(String(100), default="")
    args = Column(Text, default="{}")                     # JSON 字符串
    result = Column(Text, default="{}")                   # JSON 字符串
    status = Column(String(20), default="pending")        # pending/running/done/error
    error = Column(Text, default="")
    duration_ms = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=datetime.utcnow)

    task = relationship("AgentTask", back_populates="steps")


class AgentTemplate(Base):
    """文档/行业模板 — 强制格式约束的规则来源。

    Agent 导出前检索匹配模板，按 style_rules / validation_rules 约束生成内容，
    实现"输出版式高度统一"的商用核心能力。
    """

    __tablename__ = "agent_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    category = Column(String(100), default="general", index=True)  # 论文/报告/标书/报表…
    doc_type = Column(String(50), default="pdf")                   # pdf/docx/xlsx/pptx
    description = Column(Text, default="")
    style_rules = Column(Text, default="{}")        # JSON: 字体/字号/行距/标题层级
    cover_format = Column(Text, default="{}")       # JSON: 封面字段与排版
    validation_rules = Column(Text, default="{}")   # JSON: 校验规则(必含章节/字数/结构)
    source_text = Column(Text, default="")          # 向量化用的纯文本(供 RAG 检索)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentGeneratedFile(Base):
    """Agent 生成的文件资产清单 — 可审计/可批量管理。"""

    __tablename__ = "agent_generated_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), ForeignKey("agent_tasks.task_id"), nullable=True, index=True)
    object_name = Column(String(500), default="")
    filename = Column(String(255), default="")
    format = Column(String(20), default="pdf")  # pdf/docx/xlsx/pptx/txt
    title = Column(String(255), default="")
    size = Column(Integer, default=0)
    storage = Column(String(20), default="local")  # local / minio
    file_url = Column(String(1000), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("AgentTask", back_populates="files")


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


def _migrate_chat_message_indexes() -> None:
    """为已有 SQLite 库补充 chat_messages.session_id 索引。"""
    with engine.connect() as conn:
        rows = conn.exec_driver_sql("PRAGMA index_list(chat_messages)").fetchall()
        names = {row[1] for row in rows}
        if "ix_chat_messages_session_id" not in names:
            conn.exec_driver_sql(
                "CREATE INDEX ix_chat_messages_session_id ON chat_messages(session_id)"
            )
        conn.commit()


_db_initialized = False


def init_db() -> None:
    """创建所有表（若不存在）并执行轻量迁移（仅首次调用时执行）。

    SQLite 专属迁移逻辑（PRAGMA 补列）仅在 SQLite 后端执行；
    PostgreSQL 等其它后端跳过（新库由 create_all 直接建全字段）。
    """
    global _db_initialized
    if _db_initialized:
        return
    Base.metadata.create_all(bind=engine)
    if settings.is_postgres:
        _db_initialized = True
        return
    _migrate_wrong_questions_columns()
    _migrate_wq_user_scoping()
    _migrate_chat_message_indexes()
    _db_initialized = True


def get_db():
    """FastAPI 依赖注入：获取数据库 Session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
