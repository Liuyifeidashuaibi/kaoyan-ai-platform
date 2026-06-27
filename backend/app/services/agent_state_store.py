"""
Redis 任务状态持久化 — 商业级断点续跑。

核心能力：
  1. 状态保存：每轮 ReAct 循环结束后保存当前状态到 Redis
  2. 断点续跑：任务中断后可从上次状态恢复继续执行
  3. 临时缓存：工具执行中间结果缓存
  4. 分布式支持：多实例部署时共享任务状态

降级策略：Redis 不可用时降级为内存存储。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

# 内存存储（Redis 不可用时的降级）
_memory_store: dict[str, str] = {}


class StateStore:
    """
    任务状态持久化服务。

    优先使用 Redis，不可用时降级为内存字典。
    状态以 JSON 字符串形式存储，支持任意可序列化数据。
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._redis = None
        self._redis_url = self.settings.redis_url
        self._prefix = "agent:state:"
        self._ttl = 86400  # 24 小时 TTL

        self._init_redis()

    def _init_redis(self) -> None:
        """初始化 Redis 连接。"""
        if not self._redis_url:
            logger.info("Redis 未配置，使用内存状态存储")
            return

        try:
            import redis
            self._redis = redis.Redis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
            )
            self._redis.ping()
            logger.info("Redis 状态存储已连接: %s", self._redis_url)
        except Exception as exc:
            logger.warning("Redis 连接失败，降级为内存存储: %s", exc)
            self._redis = None

    @property
    def is_redis_available(self) -> bool:
        return self._redis is not None

    def save_state(self, task_id: str, state: dict[str, Any]) -> bool:
        """保存任务状态。"""
        key = f"{self._prefix}{task_id}"
        data = json.dumps(state, ensure_ascii=False, default=str)

        if self.is_redis_available:
            try:
                self._redis.setex(key, self._ttl, data)
                return True
            except Exception as exc:
                logger.warning("Redis 保存失败，降级到内存: %s", exc)

        _memory_store[key] = data
        return True

    def load_state(self, task_id: str) -> dict[str, Any] | None:
        """加载任务状态。"""
        key = f"{self._prefix}{task_id}"

        if self.is_redis_available:
            try:
                data = self._redis.get(key)
                if data:
                    return json.loads(data)
            except Exception as exc:
                logger.warning("Redis 加载失败，尝试内存: %s", exc)

        data = _memory_store.get(key)
        if data:
            return json.loads(data)
        return None

    def resume(self, task_id: str) -> dict[str, Any] | None:
        """
        断点续跑：加载上次中断的任务状态。

        返回可恢复的状态（含 messages, round_idx, session_id），
        或 None（无状态 / 任务已完成 / 任务不存在）。
        """
        state = self.load_state(task_id)
        if state is None:
            return None

        # 状态必须是 running 才能续跑（completed / failed 不可续）
        if state.get("status") != "running":
            logger.info("任务 %s 状态为 %s，不可续跑", task_id, state.get("status"))
            return None

        logger.info(
            "断点续跑: task_id=%s, round=%d, messages=%d条",
            task_id,
            state.get("round_idx", 0),
            len(state.get("messages", [])),
        )
        return state

    def get_resumable_tasks(self) -> list[str]:
        """列出所有可断点续跑的任务 ID（状态为 running）。"""
        all_ids = self.list_tasks()
        resumable: list[str] = []
        for tid in all_ids:
            state = self.load_state(tid)
            if state and state.get("status") == "running":
                resumable.append(tid)
        return resumable

    def delete_state(self, task_id: str) -> bool:
        """删除任务状态。"""
        key = f"{self._prefix}{task_id}"

        if self.is_redis_available:
            try:
                self._redis.delete(key)
            except Exception:
                pass

        _memory_store.pop(key, None)
        return True

    def list_tasks(self, pattern: str = "*") -> list[str]:
        """列出所有任务 ID。"""
        search = f"{self._prefix}{pattern}"

        if self.is_redis_available:
            try:
                keys = self._redis.keys(search)
                return [k.replace(self._prefix, "") for k in keys]
            except Exception:
                pass

        return [k.replace(self._prefix, "") for k in _memory_store.keys() if k.startswith(search)]

    def cache_set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """设置缓存。"""
        cache_key = f"{self._prefix}cache:{key}"
        data = json.dumps(value, ensure_ascii=False, default=str)

        if self.is_redis_available:
            try:
                self._redis.setex(cache_key, ttl, data)
                return True
            except Exception:
                pass

        _memory_store[cache_key] = data
        return True

    def cache_get(self, key: str) -> Any | None:
        """获取缓存。"""
        cache_key = f"{self._prefix}cache:{key}"

        if self.is_redis_available:
            try:
                data = self._redis.get(cache_key)
                if data:
                    return json.loads(data)
            except Exception:
                pass

        data = _memory_store.get(cache_key)
        if data:
            return json.loads(data)
        return None

    def get_stats(self) -> dict[str, Any]:
        """获取状态存储统计。"""
        return {
            "storage_type": "redis" if self.is_redis_available else "memory",
            "redis_url": self._redis_url if self._redis_url else None,
            "task_count": len(self.list_tasks()),
            "resumable_count": len(self.get_resumable_tasks()),
        }


# 全局单例
_state_store: StateStore | None = None


def get_state_store() -> StateStore:
    global _state_store
    if _state_store is None:
        _state_store = StateStore()
    return _state_store
