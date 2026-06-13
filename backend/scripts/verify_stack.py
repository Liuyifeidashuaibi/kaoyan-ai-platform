#!/usr/bin/env python3
"""
本地验证三大改造模块（无需调用付费 API）。

用法：python backend/scripts/verify_stack.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
CRAWLER = ROOT / "crawler"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(CRAWLER))

from app.config import get_settings
from app.services.response_cache import ResponseCache
from app.utils.text_utils import compress_rag_snippet, trim_user_query
from llm_parser import ParseCache, clean_page_content, truncate_for_llm


def section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def demo_crawler_llm() -> None:
    section("1. 爬虫 LLM 输入精简")
    raw = """
    <nav>首页 | 招生 | 就业</nav>
    <script>track()</script>
    <footer>版权所有</footer>
    北京大学2025年硕士研究生复试分数线公布
    计算机科学与技术 总分385 政治55 英语55
    这是一段很长的无关院校宣传文字。""" + "宣传" * 500

    cleaned = clean_page_content(raw)
    truncated = truncate_for_llm(cleaned, 200)
    print(f"原始长度: {len(raw)} → 清洗后: {len(cleaned)} → 截断后: {len(truncated)}")
    print("截断预览:", truncated[:180].replace("\n", " "))

    cache = ParseCache(path=CRAWLER / ".verify_parse_cache.json")
    sample = [{"type": "复试分数线", "school": "北京大学", "score": 385}]
    cache.set("demo_hash", sample)
    assert cache.get("demo_hash") == sample
    (CRAWLER / ".verify_parse_cache.json").unlink(missing_ok=True)
    print("[OK] content_hash parse cache read/write")


def demo_rag_utils() -> None:
    section("2. RAG 检索节流 / 提问缓存")
    long_ctx = "北京大学\n北京大学\n复试分数线385分\n" + "无关内容 " * 40
    compressed = compress_rag_snippet(long_ctx, 80)
    print("压缩后:", compressed)

    query = "  北大  计算机  分数线？  "
    print("提问截断:", trim_user_query(query * 200, 50))

    cache = ResponseCache(ttl_seconds=60)
    cache.set("北大计算机分数线", "2025年复试线约385分。")
    hit = cache.get("北大计算机分数线")
    assert hit is not None
    print("[OK] response cache hit:", hit)


def demo_config() -> None:
    section("3. 模型与额度配置")
    s = get_settings()
    cfg = {
        "llm_model": s.llm_model,
        "vl_model": s.vl_model,
        "asr_model": s.asr_model,
        "tts_model": s.tts_model,
        "embedding_model": s.embedding_model,
        "rag_top_k": s.rag_top_k,
        "llm_temperature": s.llm_temperature,
        "llm_max_tokens": s.llm_max_tokens,
        "max_query_chars": s.max_query_chars,
        "max_audio_seconds": s.max_audio_seconds,
        "vector_chunk_size": s.vector_chunk_size,
        "supabase_configured": bool(s.supabase_url and s.supabase_service_key),
        "dashscope_configured": bool(s.dashscope_api_key),
    }
    print(json.dumps(cfg, ensure_ascii=False, indent=2))


def main() -> None:
    demo_crawler_llm()
    demo_rag_utils()
    demo_config()
    section("验证完成")
    print("Local checks passed. With API keys configured, run:")
    print("  python crawler/crawl_updates_smart.py --concurrency 2")
    print("  python backend/scripts/sync_supabase_vectors.py")


if __name__ == "__main__":
    main()
