"""
Celery 应用配置 — 本地单机 4090 测试环境。

启动 Worker（项目根目录）:
  celery -A app.infrastructure.tasks.celery_app worker --loglevel=info -Q default,heavy

启动 Beat（定时分数线爬虫）:
  celery -A app.infrastructure.tasks.celery_app beat --loglevel=info
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from celery import Celery
from celery.schedules import crontab

# 确保 backend 在 PYTHONPATH（Docker / 本地均可用）
_backend = Path(__file__).resolve().parents[3]
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from dotenv import load_dotenv

_root = _backend.parent
for name in (".env", ".env.local", "crawler/.env"):
    p = _root / name
    if p.exists():
        load_dotenv(p)

from app.config import get_settings

settings = get_settings()

broker_url = settings.celery_broker_url or settings.redis_url or "redis://127.0.0.1:6379/0"
result_backend = settings.celery_result_backend or broker_url

celery_app = Celery(
    "kaoyan_platform",
    broker=broker_url,
    backend=result_backend,
    include=[
        "app.infrastructure.tasks.pdf_parse_task",
        "app.infrastructure.tasks.batch_ocr_task",
        "app.infrastructure.tasks.score_crawler_task",
        "app.infrastructure.tasks.vector_ingest_task",
        "app.infrastructure.tasks.exam_process_task",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    worker_prefetch_multiplier=1,  # 单机 GPU 任务避免堆积
    worker_max_tasks_per_child=20,
    result_expires=settings.celery_result_expires,
    task_default_queue="default",
    task_routes={
        "app.infrastructure.tasks.pdf_parse_task.*": {"queue": "heavy"},
        "app.infrastructure.tasks.batch_ocr_task.*": {"queue": "heavy"},
        "app.infrastructure.tasks.vector_ingest_task.*": {"queue": "heavy"},
        "app.infrastructure.tasks.exam_process_task.*": {"queue": "heavy"},
        "app.infrastructure.tasks.score_crawler_task.*": {"queue": "default"},
    },
)

# 定时任务：每日 03:00 触发院校分数线爬虫（本地单机 cron）
if settings.celery_beat_enabled:
    celery_app.conf.beat_schedule = {
        "score-lines-crawler-daily": {
            "task": "tasks.score_crawler",
            "schedule": crontab(
                hour=settings.celery_beat_crawler_hour,
                minute=settings.celery_beat_crawler_minute,
            ),
            "kwargs": {"trigger": "beat"},
        },
    }
