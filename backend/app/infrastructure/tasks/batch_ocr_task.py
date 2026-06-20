"""
试卷图片批量 OCR 异步任务 — 调用现有 MediaService，不修改 OCR 核心逻辑。
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.infrastructure.tasks.celery_app import celery_app
from app.infrastructure.tasks.task_store import update_task

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Celery sync worker 中运行 async MediaService。"""
    return asyncio.run(coro)


@celery_app.task(name="tasks.batch_ocr", bind=True)
def batch_ocr_task(self, task_id: str, image_paths: list[str]) -> dict:
    """
    批量 OCR 试卷图片。

    :param image_paths: 相对项目根或绝对路径列表
    """
    from app.config import get_settings
    from app.services.media_service import get_media_service
    from app.utils.image_url import validate_upload_bytes

    settings = get_settings()
    media = get_media_service()
    total = len(image_paths)
    if total == 0:
        update_task(task_id, status="failed", error="未提供图片路径")
        return {"items": []}

    update_task(
        task_id,
        status="running",
        progress=5,
        status_label="OCR 处理中",
        message=f"共 {total} 张图片",
    )

    results: list[dict] = []
    try:
        for idx, rel in enumerate(image_paths):
            path = Path(rel)
            if not path.is_absolute():
                path = settings.root / path
            if not path.is_file():
                results.append({"path": str(rel), "ok": False, "error": "文件不存在"})
                continue

            image_bytes = path.read_bytes()
            resolved = validate_upload_bytes(
                image_bytes,
                path.name,
                max_bytes=settings.max_image_upload_bytes,
            )

            async def _ocr():
                return await media.extract_image_text(resolved, image_bytes)

            try:
                text = _run_async(_ocr())
                results.append({"path": str(rel), "ok": True, "text": text, "chars": len(text or "")})
            except Exception as exc:
                results.append({"path": str(rel), "ok": False, "error": str(exc)})

            pct = 10 + int(85 * (idx + 1) / total)
            update_task(task_id, progress=pct, message=f"已完成 {idx + 1}/{total}")

        ok_count = sum(1 for r in results if r.get("ok"))
        payload = {"total": total, "success": ok_count, "items": results}
        update_task(
            task_id,
            status="done",
            progress=100,
            status_label="完成",
            message=f"OCR 完成 {ok_count}/{total}",
            result=payload,
        )
        return payload
    except Exception as exc:
        logger.exception("batch_ocr_task failed")
        update_task(task_id, status="failed", progress=100, status_label="失败", error=str(exc))
        raise
