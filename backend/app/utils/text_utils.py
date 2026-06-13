"""文本精简与 RAG 上下文压缩。"""

from __future__ import annotations

import re


def trim_user_query(text: str, max_chars: int) -> str:
    """超长提问截断，保留开头核心内容。"""
    s = text.strip()
    if len(s) <= max_chars:
        return s
    return s[:max_chars].rstrip() + "…"


def compress_rag_snippet(text: str, max_chars: int = 280) -> str:
    """检索结果短句压缩：去重复空行、截断。"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    seen: set[str] = set()
    unique: list[str] = []
    for ln in lines:
        key = re.sub(r"\s+", "", ln)[:80]
        if key in seen:
            continue
        seen.add(key)
        unique.append(ln)
    merged = " ".join(unique)
    if len(merged) <= max_chars:
        return merged
    return merged[:max_chars].rstrip() + "…"
