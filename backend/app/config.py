"""
全局配置模块 — 从项目根目录 .env 加载环境变量。
"""

from functools import lru_cache
from pathlib import Path

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
    )

    # 百炼 / DashScope
    dashscope_api_key: str = ""
    llm_model: str = "qwen-max-latest"
    vl_model: str = "qwen2.5-vl-72b-instruct"
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    # 聊天图片上传大小上限（字节）
    max_image_upload_bytes: int = 10 * 1024 * 1024
    # 模型 API 调用超时（秒）
    model_timeout_seconds: int = 120

    # 服务
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    # 路径
    project_root: str = ""
    public_data_dir: str = "data/public"
    upload_dir: str = "uploads/wrong_questions"
    chroma_persist_dir: str = "chroma_db"
    database_url: str = "sqlite:///./kaoyan.db"

    # RAG
    rag_top_k: int = 5
    embedding_model: str = "text-embedding-v3"
    embedding_dim: int = 1024

    @property
    def root(self) -> Path:
        """项目根目录绝对路径。"""
        if self.project_root:
            return Path(self.project_root).resolve()
        return _detect_project_root()

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
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """单例配置，避免重复解析 .env。"""
    root = _detect_project_root()
    env_file = root / ".env"
    return Settings(_env_file=env_file if env_file.exists() else None)
