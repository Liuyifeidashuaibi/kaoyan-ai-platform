#!/usr/bin/env python3
"""
Celery 异步任务本地测试 — 在项目根目录执行:
  python examples/test_celery_tasks.py

需 Redis + Celery Worker 运行中。
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app.infrastructure.cache.redis_client import is_redis_enabled
from app.infrastructure.tasks.task_store import create_task_record, get_task, update_task
from app.infrastructure.tasks.vector_ingest_task import vector_ingest_task


def main() -> None:
    print("=== Celery 任务测试 ===\n")

    if not is_redis_enabled():
        print("❌ Redis 不可用")
        sys.exit(1)

    task_id = create_task_record("vector_ingest", user_id="test-user", meta={"source": "public"})
    print(f"创建任务: {task_id}")

    # 提交 Celery（public 库向量化，需 DASHSCOPE_API_KEY）
    async_result = vector_ingest_task.delay(task_id, source="public", force=False)
    print(f"Celery ID: {async_result.id}")

    for i in range(60):
        record = get_task(task_id)
        if not record:
            print("任务记录丢失")
            break
        status = record.get("status")
        progress = record.get("progress", 0)
        label = record.get("status_label", "")
        print(f"  [{i}s] status={status} progress={progress}% {label}")
        if status in ("done", "failed"):
            if record.get("error"):
                print("错误:", record["error"])
            else:
                print("结果:", record.get("result"))
            break
        time.sleep(2)
    else:
        print("超时，请检查 Worker 日志")

    print("\n测试结束。")


if __name__ == "__main__":
    main()
