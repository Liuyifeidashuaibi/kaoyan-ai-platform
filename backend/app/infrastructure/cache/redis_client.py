"""
Redis 客户端 — 本地单机部署（4090 开发机 / Docker Compose）。

- 未配置 REDIS_URL 或连接失败时自动降级，不影响原有业务
- 不使用 Redis Cluster / Sentinel，仅单实例
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any, Optional

logger = logging.getLogger(__name__)

_redis_module = None
_client: Any | None = None
_redis_available: bool | None = None


def is_redis_enabled() -> bool:
    """Redis 是否可用（配置 + 连通性）。"""
    global _redis_available
    if _redis_available is not None:
        return _redis_available
    from app.config import get_settings

    url = get_settings().redis_url.strip()
    if not url:
        _redis_available = False
        return False
    try:
        client = get_redis()
        client.ping()
        _redis_available = True
    except Exception as exc:
        logger.warning("Redis 不可用，将降级为内存/直查数据库: %s", exc)
        _redis_available = False
    return _redis_available


@lru_cache
def get_redis():
    """
    获取 Redis 连接单例。

    本地 Docker: redis://redis:6379/0
    本机直跑:   redis://127.0.0.1:6379/0
    """
    global _redis_module, _client
    from app.config import get_settings

    url = get_settings().redis_url.strip()
    if not url:
        raise RuntimeError("未配置 REDIS_URL")

    if _client is not None:
        return _client

    import redis

    _redis_module = redis
    _client = redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=5,
        health_check_interval=30,
    )
    return _client


def cache_get_json(key: str) -> Any | None:
    """读取 JSON 缓存；失败或未命中返回 None。"""
    if not is_redis_enabled():
        return None
    try:
        raw = get_redis().get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.debug("cache_get_json miss %s: %s", key, exc)
        return None


def cache_set_json(key: str, value: Any, ttl_seconds: int) -> bool:
    """写入 JSON 缓存并设置 TTL（秒）。"""
    if not is_redis_enabled():
        return False
    try:
        get_redis().setex(key, ttl_seconds, json.dumps(value, ensure_ascii=False))
        return True
    except Exception as exc:
        logger.warning("cache_set_json failed %s: %s", key, exc)
        return False


def cache_delete_pattern(prefix: str) -> int:
    """按前缀批量删除（本地单机 scan，非分布式）。"""
    if not is_redis_enabled():
        return 0
    try:
        client = get_redis()
        deleted = 0
        for key in client.scan_iter(match=f"{prefix}*"):
            client.delete(key)
            deleted += 1
        return deleted
    except Exception as exc:
        logger.warning("cache_delete_pattern failed %s: %s", prefix, exc)
        return 0


def cache_get_str(key: str) -> Optional[str]:
    if not is_redis_enabled():
        return None
    try:
        return get_redis().get(key)
    except Exception:
        return None


def cache_set_str(key: str, value: str, ttl_seconds: int) -> bool:
    if not is_redis_enabled():
        return False
    try:
        get_redis().setex(key, ttl_seconds, value)
        return True
    except Exception:
        return False
