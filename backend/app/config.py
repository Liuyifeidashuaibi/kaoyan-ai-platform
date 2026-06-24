"""
全局配置模块 — 从项目根目录 .env 加载环境变量。
"""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _detect_project_root() -> Path:
    """向上查找包含 data/public 的目录作为项目根。"""
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        if (parent / "data" / "public").exists():
            return parent
    # 默认：backend/app/config.py -> 上两级为 backend，再上一级为根
    return Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """应用配置，所有路径均相对于项目根目录解析。"""

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # 百炼 / DashScope
    dashscope_api_key: str = ""
    llm_model: str = "qwen3.5-plus"
    llm_fallback_models: str = "qwen-turbo"
    vl_model: str = "qwen-vl-ocr-latest"
    asr_model: str = "paraformer-realtime-v2"
    tts_model: str = "sambert-zhida-v1"
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.1
    # qwen3.5/qwen3.6 默认开启思考模式，首字延迟 20s+；考研答疑建议关闭
    llm_enable_thinking: bool = False
    # 聊天图片上传大小上限（字节）
    max_image_upload_bytes: int = 5 * 1024 * 1024
    max_audio_upload_bytes: int = 5 * 1024 * 1024
    max_audio_seconds: int = 30
    vision_max_width: int = 1920
    max_query_chars: int = 2000
    tts_max_chars: int = 500
    enable_tts_default: bool = False
    # 模型 API 调用超时（秒）
    model_timeout_seconds: int = 120
    # Supabase（向量同步）
    supabase_url: str = ""
    supabase_service_key: str = Field(
        default="",
        validation_alias="SUPABASE_SERVICE_ROLE_KEY",
    )

    # 服务
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    admin_emails: str = Field(default="", validation_alias="ADMIN_EMAILS")
    supabase_jwt_secret: str = Field(
        default="",
        validation_alias="SUPABASE_JWT_SECRET",
    )

    # 路径
    project_root: str = ""
    public_data_dir: str = "data/public"
    upload_dir: str = "uploads/wrong_questions"
    chroma_persist_dir: str = "chroma_db"
    database_url: str = "sqlite:///./kaoyan.db"

    # RAG
    rag_top_k: int = 4
    rag_snippet_max_chars: int = 280
    embedding_model: str = "text-embedding-v3"
    embedding_dim: int = 1024
    vector_chunk_size: int = 900
    vector_chunk_overlap: int = 80
    response_cache_ttl_seconds: int = 3600
    # 多轮对话记忆
    chat_history_max_turns: int = 12
    chat_history_max_chars: int = 18000
    chat_assistant_msg_max_chars: int = 4000
    chat_image_context_turns: int = 8
    chat_image_ocr_max_chars: int = 6000

    # Redis 缓存（本地单机，Docker Compose 中 redis://redis:6379/0）
    redis_url: str = Field(default="", validation_alias="REDIS_URL")
    cache_ttl_schools_list: int = Field(
        default=1800, validation_alias="CACHE_TTL_SCHOOLS_LIST"
    )
    cache_ttl_schools_detail: int = Field(
        default=3600, validation_alias="CACHE_TTL_SCHOOLS_DETAIL"
    )
    cache_ttl_score_lines: int = Field(
        default=1800, validation_alias="CACHE_TTL_SCORE_LINES"
    )
    cache_ttl_translator: int = Field(
        default=86400, validation_alias="CACHE_TTL_TRANSLATOR"
    )
    cache_ttl_membership_quota: int = Field(
        default=86400, validation_alias="CACHE_TTL_MEMBERSHIP"
    )

    # 用户会员额度（本地测试默认值，Redis 缓存当日用量）
    membership_daily_translate_limit: int = Field(
        default=50, validation_alias="MEMBERSHIP_DAILY_TRANSLATE_LIMIT"
    )
    membership_daily_chat_limit: int = Field(
        default=200, validation_alias="MEMBERSHIP_DAILY_CHAT_LIMIT"
    )

    # Celery 异步任务（Broker/Backend 默认复用 REDIS_URL）
    celery_broker_url: str = Field(default="", validation_alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(
        default="", validation_alias="CELERY_RESULT_BACKEND"
    )
    celery_task_time_limit: int = Field(
        default=3600, validation_alias="CELERY_TASK_TIME_LIMIT"
    )
    celery_task_soft_time_limit: int = Field(
        default=3300, validation_alias="CELERY_TASK_SOFT_TIME_LIMIT"
    )
    celery_result_expires: int = Field(
        default=86400, validation_alias="CELERY_RESULT_EXPIRES"
    )
    celery_beat_enabled: bool = Field(
        default=True, validation_alias="CELERY_BEAT_ENABLED"
    )
    celery_beat_crawler_hour: int = Field(
        default=3, validation_alias="CELERY_BEAT_CRAWLER_HOUR"
    )
    celery_beat_crawler_minute: int = Field(
        default=0, validation_alias="CELERY_BEAT_CRAWLER_MINUTE"
    )

    # 本地 Ollama（英文纠错 / 生词 AI 补全，不上传外网）
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434",
        validation_alias="OLLAMA_BASE_URL",
    )
    ollama_text_model: str = Field(
        default="qwen2.5-vl:7b-q4_K_M",
        validation_alias="OLLAMA_TEXT_MODEL",
    )

    # ECDICT 离线词库（独立 SQLite）
    word_lib_db: str = Field(
        default="data/word_lib.db", validation_alias="WORD_LIB_DB_PATH"
    )

    # 本地 Qwen3-TTS + Piper 兜底
    qwen3_tts_enabled: bool = Field(default=False, validation_alias="QWEN3_TTS_ENABLED")
    qwen3_tts_script: str = Field(default="", validation_alias="QWEN3_TTS_SCRIPT")
    qwen3_tts_model: str = Field(
        default="data/tts/qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
        validation_alias="QWEN3_TTS_MODEL",
    )
    qwen3_tts_host_url: str = Field(
        default="http://host.docker.internal:8200",
        validation_alias="QWEN3_TTS_HOST_URL",
    )
    tts_prefer_piper: bool = Field(default=True, validation_alias="TTS_PREFER_PIPER")
    piper_model_us_female: str = Field(
        default="data/tts/piper/en_US-lessac-medium.onnx",
        validation_alias="PIPER_MODEL_US_FEMALE",
    )
    piper_model_us_male: str = Field(
        default="data/tts/piper/en_US-ryan-medium.onnx",
        validation_alias="PIPER_MODEL_US_MALE",
    )
    piper_model_uk_female: str = Field(
        default="data/tts/piper/en_GB-alba-medium.onnx",
        validation_alias="PIPER_MODEL_UK_FEMALE",
    )
    piper_model_uk_male: str = Field(
        default="data/tts/piper/en_GB-northern_english_male-medium.onnx",
        validation_alias="PIPER_MODEL_UK_MALE",
    )

    # 试卷解析
    exam_shard_threshold_tokens: int = 12000
    exam_shard_questions_per_chunk: int = 10
    exam_temp_ttl_days: int = 7
    exam_max_image_size_bytes: int = 10 * 1024 * 1024

    # Translator export email (SMTP)
    smtp_host: str = Field(default="", validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT")
    smtp_user: str = Field(default="", validation_alias="SMTP_USER")
    smtp_password: str = Field(default="", validation_alias="SMTP_PASSWORD")
    smtp_from: str = Field(default="", validation_alias="SMTP_FROM")
    smtp_use_tls: bool = Field(default=True, validation_alias="SMTP_USE_TLS")
    pdf_font_path: str = Field(default="", validation_alias="PDF_FONT_PATH")

    @property
    def root(self) -> Path:
        """项目根目录绝对路径。"""
        if self.project_root:
            return Path(self.project_root).resolve()
        return _detect_project_root()

    @property
    def word_lib_db_path(self) -> Path:
        p = Path(self.word_lib_db)
        if not p.is_absolute():
            return self.root / p
        return p

    @property
    def public_data_path(self) -> Path:
        return self.root / self.public_data_dir

    @property
    def upload_path(self) -> Path:
        return self.root / self.upload_dir

    @property
    def chroma_path(self) -> Path:
        return self.root / self.chroma_persist_dir

    @property
    def effective_supabase_url(self) -> str:
        return (
            self.supabase_url or os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "").strip()
        )

    @property
    def effective_supabase_service_key(self) -> str:
        return self.supabase_service_key.strip()

    @property
    def effective_supabase_jwt_secret(self) -> str:
        return (
            self.supabase_jwt_secret.strip()
            or os.environ.get("SUPABASE_JWT_SECRET", "").strip()
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """单例配置，避免重复解析 .env。"""
    root = _detect_project_root()
    env_files: list[Path] = []
    for name in (".env", ".env.local", "crawler/.env"):
        p = root / name
        if p.exists():
            env_files.append(p)
    if env_files:
        return Settings(_env_file=tuple(str(f) for f in env_files))
    return Settings()
