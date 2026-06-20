"""
异步任务状态存储 — Redis JSON，供前端轮询 /api/tasks/{id}。

Celery AsyncResult 与自定义 meta 合并，统一进度展示。
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.infrastructure.cache import keys
from app.infrastructure.cache.redis_client import cache_get_json, cache_set_json, is_redis_enabled

logger = logging.getLogger(__name__)

# Redis 不可用时的进程内降级（仅本地开发）
_fallback_tasks: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_task_record(task_type: str, *, user_id: str | None = None, meta: dict | None = None) -> str:
    """创建任务记录并返回 task_id（与 Celery task id 可相同）。"""
    task_id = str(uuid.uuid4())
    record = {
        "id": task_id,
        "type": task_type,
        "status": "pending",
        "progress": 0,
        "status_label": "排队中",
        "message": "",
        "user_id": user_id,
        "meta": meta or {},
        "result": None,
        "error": None,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    _save(task_id, record)
    return task_id


def bind_celery_id(task_id: str, celery_id: str) -> None:
    record = get_task(task_id)
    if record:
        record["celery_id"] = celery_id
        record["status"] = "running"
        record["status_label"] = "处理中"
        record["progress"] = 5
        record["updated_at"] = _now_iso()
        _save(task_id, record)


def update_task(
    task_id: str,
    *,
    status: str | None = None,
    progress: int | None = None,
    status_label: str | None = None,
    message: str | None = None,
    result: Any = None,
    error: str | None = None,
) -> None:
    record = get_task(task_id)
    if not record:
        return
    if status is not None:
        record["status"] = status
    if progress is not None:
        record["progress"] = max(0, min(100, progress))
    if status_label is not None:
        record["status_label"] = status_label
    if message is not None:
        record["message"] = message
    if result is not None:
        record["result"] = result
    if error is not None:
        record["error"] = error
    record["updated_at"] = _now_iso()
    _save(task_id, record)


def get_task(task_id: str) -> dict[str, Any] | None:
    if is_redis_enabled():
        return cache_get_json(keys.task_key(task_id))
    return _fallback_tasks.get(task_id)


def list_user_tasks(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """列出用户最近任务（Redis scan，本地单机）。"""
    if not is_redis_enabled():
        items = [t for t in _fallback_tasks.values() if t.get("user_id") == user_id]
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return items[:limit]

    try:
        from app.infrastructure.cache.redis_client import get_redis

        client = get_redis()
        out: list[dict[str, Any]] = []
        for key in client.scan_iter(match=f"{keys.PREFIX_TASK}*"):
            raw = client.get(key)
            if not raw:
                continue
            item = json.loads(raw)
            if item.get("user_id") == user_id:
                out.append(item)
        out.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return out[:limit]
    except Exception as exc:
        logger.warning("list_user_tasks failed: %s", exc)
        return []


def _save(task_id: str, record: dict[str, Any]) -> None:
    ttl = get_settings().celery_result_expires
    if is_redis_enabled():
        cache_set_json(keys.task_key(task_id), record, ttl)
    else:
        _fallback_tasks[task_id] = record
