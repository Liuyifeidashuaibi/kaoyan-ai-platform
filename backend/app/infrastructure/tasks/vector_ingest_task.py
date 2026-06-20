"""
批量文本向量化入库 RAG — 包装现有 RAGService / VectorSyncService，不修改其核心逻辑。
"""

from __future__ import annotations

import logging

from app.infrastructure.tasks.celery_app import celery_app
from app.infrastructure.tasks.task_store import update_task

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.vector_ingest", bind=True)
def vector_ingest_task(
    self,
    task_id: str,
    *,
    source: str = "public",
    force: bool = False,
) -> dict:
    """
    向量化入库。

    :param source: public | school | all
    :param force: 公共库是否 force 重建
    """
    update_task(
        task_id,
        status="running",
        progress=10,
        status_label="向量化中",
        message=f"来源: {source}",
    )

    output: dict = {}

    try:
        if source in ("public", "all"):
            update_task(task_id, progress=25, message="索引 data/public/ …")
            from app.services.rag_service import get_rag_service

            result = get_rag_service().ingest_public_knowledge(force=force)
            output["public"] = result

        if source in ("school", "all"):
            update_task(task_id, progress=60, message="同步 Supabase 院校向量…")
            from app.services.vector_sync_service import get_vector_sync_service

            sync_result = get_vector_sync_service().sync()
            output["school"] = sync_result

        update_task(
            task_id,
            status="done",
            progress=100,
            status_label="完成",
            message="RAG 向量化完成",
            result=output,
        )
        return output
    except Exception as exc:
        logger.exception("vector_ingest_task failed")
        update_task(task_id, status="failed", progress=100, status_label="失败", error=str(exc))
        raise
