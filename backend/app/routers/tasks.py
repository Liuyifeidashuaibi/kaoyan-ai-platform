"""
异步任务 HTTP 路由 — 提交后台任务 + 查询进度。

不替代 chat / translator / schools 等原有同步接口；
大文件/长文档场景走此路由立即返回 task_id，前端轮询状态。
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.config import get_settings
from app.infrastructure.cache.membership_quota import get_membership_quota_cache
from app.infrastructure.tasks.batch_ocr_task import batch_ocr_task
from app.infrastructure.tasks.pdf_parse_task import pdf_parse_task
from app.infrastructure.tasks.score_crawler_task import score_crawler_task
from app.infrastructure.tasks.task_store import (
    bind_celery_id,
    create_task_record,
    get_task,
    list_user_tasks,
)
from app.infrastructure.tasks.vector_ingest_task import vector_ingest_task
from app.utils.auth import require_user_id
from app.utils.file_utils import ensure_dir
from app.utils.response import error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["异步任务"])


def _enqueue(celery_task_fn, task_id: str, *args, **kwargs):
    """提交 Celery 任务并绑定 celery_id。"""
    async_result = celery_task_fn.delay(task_id, *args, **kwargs)
    bind_celery_id(task_id, async_result.id)
    return async_result.id


@router.get("/health")
async def tasks_health():
    """Redis / Celery 基础设施状态（本地诊断）。"""
    from app.infrastructure.cache.redis_client import is_redis_enabled

    settings = get_settings()
    return success_response(
        {
            "redis_enabled": is_redis_enabled(),
            "redis_url_configured": bool(settings.redis_url.strip()),
            "celery_broker": settings.celery_broker_url or settings.redis_url or "",
            "celery_beat_enabled": settings.celery_beat_enabled,
        }
    )


@router.get("/quota")
async def get_my_quota(user_id: str = Depends(require_user_id)):
    """查询当前用户会员额度缓存。"""
    quota = get_membership_quota_cache().get_quota(user_id)
    return success_response(quota)


@router.get("")
async def list_my_tasks(
    user_id: str = Depends(require_user_id),
    limit: int = 20,
):
    """列出当前用户最近异步任务。"""
    items = list_user_tasks(user_id, limit=min(limit, 50))
    return success_response(items)


@router.get("/{task_id}")
async def get_task_status(task_id: str, user_id: str = Depends(require_user_id)):
    """查询单个任务进度与结果。"""
    record = get_task(task_id)
    if not record:
        return error_response("任务不存在或已过期", data={"id": task_id})
    owner = record.get("user_id")
    if owner and owner != user_id:
        return error_response("无权查看该任务")
    return success_response(record)


@router.post("/pdf/parse")
async def submit_pdf_parse(
    file: UploadFile = File(...),
    user_id: str = Depends(require_user_id),
):
    """
    上传 PDF 后立即返回 task_id，后台 Celery 解析文本。
    适合大 PDF，不阻塞页面。
    """
    settings = get_settings()
    content = await file.read()
    if not content:
        return error_response("文件为空")

    staging = settings.root / "uploads" / "tasks" / "pdf"
    ensure_dir(staging)
    safe_name = f"{uuid.uuid4().hex}_{file.filename or 'document.pdf'}"
    dest = staging / safe_name
    dest.write_bytes(content)

    task_id = create_task_record("pdf_parse", user_id=user_id, meta={"filename": file.filename})
    _enqueue(pdf_parse_task, task_id, dest.relative_to(settings.root).as_posix())
    return success_response(
        {"task_id": task_id, "status": "pending"},
        message="PDF 已接收，后台解析中",
    )


@router.post("/ocr/batch")
async def submit_batch_ocr(
    files: list[UploadFile] = File(...),
    user_id: str = Depends(require_user_id),
):
    """批量上传试卷图片，后台 OCR。"""
    if not files:
        return error_response("请至少上传一张图片")
    if len(files) > 20:
        return error_response("单次最多 20 张图片")

    settings = get_settings()
    staging = settings.root / "uploads" / "tasks" / "ocr"
    ensure_dir(staging)
    rel_paths: list[str] = []

    for upload in files:
        content = await upload.read()
        if not content:
            continue
        safe_name = f"{uuid.uuid4().hex}_{upload.filename or 'image.png'}"
        dest = staging / safe_name
        dest.write_bytes(content)
        rel_paths.append(dest.relative_to(settings.root).as_posix())

    if not rel_paths:
        return error_response("没有有效图片")

    task_id = create_task_record(
        "batch_ocr",
        user_id=user_id,
        meta={"count": len(rel_paths)},
    )
    _enqueue(batch_ocr_task, task_id, rel_paths)
    return success_response(
        {"task_id": task_id, "status": "pending", "image_count": len(rel_paths)},
        message="图片已接收，后台 OCR 中",
    )


@router.post("/rag/ingest")
async def submit_vector_ingest(
    source: str = Form(default="public"),
    force: bool = Form(default=False),
    user_id: str = Depends(require_user_id),
):
    """提交 RAG 向量化入库任务（public / school / all）。"""
    if source not in ("public", "school", "all"):
        return error_response("source 必须是 public | school | all")

    task_id = create_task_record("vector_ingest", user_id=user_id, meta={"source": source})
    _enqueue(vector_ingest_task, task_id, source=source, force=force)
    return success_response(
        {"task_id": task_id, "status": "pending"},
        message="向量化任务已提交",
    )


@router.post("/crawler/scores")
async def submit_score_crawler(user_id: str = Depends(require_user_id)):
    """手动触发院校分数线爬虫 + 缓存刷新。"""
    task_id = create_task_record("score_crawler", user_id=user_id)
    _enqueue(score_crawler_task, task_id, trigger="manual")
    return success_response(
        {"task_id": task_id, "status": "pending"},
        message="分数线爬虫任务已提交",
    )
