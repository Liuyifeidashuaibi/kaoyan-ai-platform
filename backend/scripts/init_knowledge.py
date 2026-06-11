#!/usr/bin/env python3
"""
知识库初始化脚本 — 加载 data/public/ 下所有资料到 Chroma 向量库。

用法（在项目根目录执行）：
  python backend/scripts/init_knowledge.py
  python backend/scripts/init_knowledge.py --force   # 强制重建索引

支持的文件格式：PDF、TXT、Markdown
"""

import argparse
import logging
import sys
from pathlib import Path

# 将 backend 目录加入 Python 路径
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv

from app.config import get_settings
from app.services.rag_service import get_rag_service
from app.utils.file_utils import ensure_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="初始化公共考研知识库")
    parser.add_argument(
        "--force",
        action="store_true",
        help="清空现有公共知识库后重新索引",
    )
    args = parser.parse_args()

    settings = get_settings()
    load_dotenv(settings.root / ".env")

    # 确保目录存在
    ensure_dir(settings.public_data_path)
    ensure_dir(settings.chroma_path)

    if not settings.dashscope_api_key or settings.dashscope_api_key == "your_dashscope_api_key_here":
        logger.error("请先在 .env 中配置有效的 DASHSCOPE_API_KEY")
        sys.exit(1)

    # 扫描资料文件
    extensions = {".pdf", ".txt", ".md", ".markdown"}
    files = [
        f
        for f in settings.public_data_path.rglob("*")
        if f.is_file() and f.suffix.lower() in extensions
    ]

    if not files:
        logger.warning(
            "未在 %s 找到 PDF/TXT/Markdown 文件，请将考研资料放入该目录后重试。",
            settings.public_data_path,
        )
        logger.info("目录已创建，可稍后添加资料再运行本脚本。")
        return

    logger.info("发现 %d 个资料文件，开始向量化索引...", len(files))
    for f in files:
        logger.info("  - %s", f.relative_to(settings.root))

    rag = get_rag_service()
    result = rag.ingest_public_knowledge(force=args.force)

    logger.info("索引完成: %s", result)
    print(f"\n✅ 公共知识库初始化完成")
    print(f"   索引节点数: {result.get('ingested', 0)}")
    print(f"   文件数: {result.get('files', 0)}")
    print(f"   向量库路径: {settings.chroma_path}")


if __name__ == "__main__":
    main()
