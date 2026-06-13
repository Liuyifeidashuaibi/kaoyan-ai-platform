"""
高频相似提问结果缓存 — 相同问题跳过 RAG + LLM 全流程。
"""

from __future__ import annotations

import hashlib
import re
import time
from typing import Optional


def _normalize_query(text: str) -> str:
    s = text.strip().lower()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[，。！？、；：""''（）()【】\[\]]", "", s)
    return s


class ResponseCache:
    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 200) -> None:
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._store: dict[str, tuple[float, str]] = {}

    def _key(self, query: str) -> str:
        return hashlib.md5(_normalize_query(query).encode()).hexdigest()

    def get(self, query: str) -> Optional[str]:
        key = self._key(query)
        item = self._store.get(key)
        if not item:
            return None
        ts, answer = item
        if time.time() - ts > self.ttl:
            del self._store[key]
            return None
        return answer

    def set(self, query: str, answer: str) -> None:
        if len(self._store) >= self.max_entries:
            oldest = min(self._store, key=lambda k: self._store[k][0])
            del self._store[oldest]
        self._store[self._key(query)] = (time.time(), answer)


_cache: ResponseCache | None = None


def get_response_cache() -> ResponseCache:
    global _cache
    if _cache is None:
        from app.config import get_settings

        s = get_settings()
        _cache = ResponseCache(ttl_seconds=s.response_cache_ttl_seconds)
    return _cache
