"""
院校分数线定时爬虫任务 — 本地单机定时/手动触发。

优先执行项目内 crawler 脚本；若不存在则刷新 Supabase 向量同步并清除择校 Redis 缓存。
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from app.infrastructure.tasks.celery_app import celery_app
from app.infrastructure.tasks.task_store import update_task

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.score_crawler", bind=True)
def score_crawler_task(self, task_id: str | None = None, trigger: str = "manual") -> dict:
    from app.config import get_settings
    from app.infrastructure.cache import keys
    from app.infrastructure.cache.redis_client import cache_delete_pattern
    from app.infrastructure.tasks.task_store import create_task_record

    if not task_id:
        task_id = create_task_record("score_crawler", meta={"trigger": trigger})

    settings = get_settings()
    update_task(
        task_id,
        status="running",
        progress=10,
        status_label="爬取中",
        message=f"触发方式: {trigger}",
    )

    root = settings.root
    crawler_script = root / "crawler" / "sync_kaoyan_cn.py"
    output: dict = {"trigger": trigger, "crawler_ran": False, "vector_sync": None, "cache_cleared": 0}

    try:
        if crawler_script.is_file():
            update_task(task_id, progress=20, message="运行 crawler/sync_kaoyan_cn.py …")
            proc = subprocess.run(
                [sys.executable, str(crawler_script), "--import-only"],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=settings.celery_task_time_limit - 60,
            )
            output["crawler_ran"] = True
            output["crawler_exit_code"] = proc.returncode
            output["crawler_stdout"] = (proc.stdout or "")[-2000:]
            if proc.returncode != 0:
                output["crawler_stderr"] = (proc.stderr or "")[-2000:]
                logger.warning("crawler exit %s: %s", proc.returncode, proc.stderr)
        else:
            update_task(task_id, progress=30, message="未找到 crawler 脚本，执行向量同步…")

        # 无论是否爬虫，尝试增量向量同步 + 清缓存
        update_task(task_id, progress=60, message="同步院校向量库…")
        if settings.effective_supabase_url and settings.dashscope_api_key:
            from app.services.vector_sync_service import get_vector_sync_service

            sync_result = get_vector_sync_service().sync()
            output["vector_sync"] = sync_result

        update_task(task_id, progress=85, message="清除择校 Redis 缓存…")
        output["cache_cleared"] = (
            cache_delete_pattern(keys.PREFIX_SCHOOLS)
            + cache_delete_pattern(keys.PREFIX_SCORE_LINES)
        )

        update_task(
            task_id,
            status="done",
            progress=100,
            status_label="完成",
            message="分数线数据任务完成",
            result=output,
        )
        return output
    except Exception as exc:
        logger.exception("score_crawler_task failed")
        update_task(task_id, status="failed", progress=100, status_label="失败", error=str(exc))
        raise
