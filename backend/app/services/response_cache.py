"""
高频相似提问结果缓存 — Redis 优先，内存降级。

与 agent_service 使用的 get/set 接口保持不变，不修改聊天核心流水线。
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)


def _normalize_query(text: str) -> str:
    s = text.strip().lower()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[，。！？、；：\"\"''（）()\[\]【】]", "", s)
    return s


class ResponseCache:
    """内存 + Redis 双层缓存。"""

    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 200) -> None:
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._store: dict[str, tuple[float, str]] = {}

    def _key(self, query: str) -> str:
        return hashlib.md5(_normalize_query(query).encode()).hexdigest()

    def _redis_key(self, query: str) -> str:
        from app.infrastructure.cache import keys

        return keys.chat_qa_key(self._key(query))

    def get(self, query: str) -> Optional[str]:
        md5_key = self._key(query)

        # 1. Redis
        try:
            from app.infrastructure.cache.redis_client import cache_get_str, is_redis_enabled

            if is_redis_enabled():
                cached = cache_get_str(self._redis_key(query))
                if cached is not None:
                    return cached
        except Exception as exc:
            logger.debug("Redis chat cache miss: %s", exc)

        # 2. 内存降级
        item = self._store.get(md5_key)
        if not item:
            return None
        ts, answer = item
        if time.time() - ts > self.ttl:
            del self._store[md5_key]
            return None
        return answer

    def set(self, query: str, answer: str) -> None:
        md5_key = self._key(query)

        # Redis
        try:
            from app.infrastructure.cache.redis_client import cache_set_str, is_redis_enabled

            if is_redis_enabled():
                cache_set_str(self._redis_key(query), answer, self.ttl)
        except Exception as exc:
            logger.debug("Redis chat cache set failed: %s", exc)

        # 内存 LRU
        if len(self._store) >= self.max_entries:
            oldest = min(self._store, key=lambda k: self._store[k][0])
            del self._store[oldest]
        self._store[md5_key] = (time.time(), answer)


_cache: ResponseCache | None = None


def get_response_cache() -> ResponseCache:
    global _cache
    if _cache is None:
        from app.config import get_settings

        s = get_settings()
        _cache = ResponseCache(ttl_seconds=s.response_cache_ttl_seconds)
    return _cache
