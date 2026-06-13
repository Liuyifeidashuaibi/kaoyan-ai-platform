#!/usr/bin/env python3
"""
Supabase 招生数据增量向量化 — 建议每日定时执行一次。

用法（项目根目录）：
  python backend/scripts/sync_supabase_vectors.py
"""

import logging
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv

from app.config import get_settings
from app.services.vector_sync_service import get_vector_sync_service
from app.utils.file_utils import ensure_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    load_dotenv(settings.root / ".env")

    if not settings.dashscope_api_key:
        logger.error("请配置 DASHSCOPE_API_KEY")
        sys.exit(1)
    if not settings.supabase_url or not settings.supabase_service_key:
        logger.error("请配置 SUPABASE_URL 与 SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

    ensure_dir(settings.chroma_path)
    result = get_vector_sync_service().sync()
    print(f"\n✅ 向量同步完成: {result}")


if __name__ == "__main__":
    main()
