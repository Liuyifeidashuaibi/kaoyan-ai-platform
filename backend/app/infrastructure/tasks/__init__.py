"""
Celery 异步任务模块 — 本地单机 Worker，Redis 作 Broker + Result Backend。
"""

from app.infrastructure.tasks.celery_app import celery_app

__all__ = ["celery_app"]
