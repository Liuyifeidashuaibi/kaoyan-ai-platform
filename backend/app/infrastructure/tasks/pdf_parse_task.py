"""
PDF 文档解析异步任务 — pypdf 提取文本，适合大 PDF 后台处理。
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.infrastructure.tasks.celery_app import celery_app
from app.infrastructure.tasks.task_store import update_task

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.pdf_parse", bind=True)
def pdf_parse_task(self, task_id: str, file_path: str) -> dict:
    """
    解析 PDF 为纯文本。

    :param task_id: task_store 中的业务 task_id
    :param file_path: 相对于项目根或绝对路径
    """
    from app.config import get_settings

    update_task(task_id, status="running", progress=10, status_label="读取 PDF", message="正在打开文件…")

    settings = get_settings()
    path = Path(file_path)
    if not path.is_absolute():
        path = settings.root / path
    if not path.is_file():
        update_task(task_id, status="failed", progress=100, status_label="失败", error="文件不存在")
        raise FileNotFoundError(str(path))

    try:
        from pypdf import PdfReader

        update_task(task_id, progress=30, status_label="解析中", message=f"共 {path.name}")
        reader = PdfReader(str(path))
        total = len(reader.pages)
        chunks: list[str] = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            chunks.append(text)
            pct = 30 + int(60 * (i + 1) / max(total, 1))
            update_task(
                task_id,
                progress=pct,
                message=f"已解析 {i + 1}/{total} 页",
            )

        full_text = "\n".join(chunks)
        result = {
            "filename": path.name,
            "pages": total,
            "char_count": len(full_text),
            "text_preview": full_text[:2000],
            "text_path": str(path),
        }
        update_task(
            task_id,
            status="done",
            progress=100,
            status_label="完成",
            message=f"解析完成，共 {total} 页",
            result=result,
        )
        return result
    except Exception as exc:
        logger.exception("pdf_parse_task failed")
        update_task(task_id, status="failed", progress=100, status_label="失败", error=str(exc))
        raise
