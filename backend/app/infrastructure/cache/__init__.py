"""Redis 热点数据缓存模块。"""

from app.infrastructure.cache.redis_client import get_redis, is_redis_enabled

__all__ = ["get_redis", "is_redis_enabled"]
