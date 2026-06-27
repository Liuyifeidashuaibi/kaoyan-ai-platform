"""
Agent 批量文档生成异步任务 — 复用 LangGraph 引擎逐项处理。

每个 item（文件 + 指令）调用 AgentModeService.run_once()（非流式），
进度写入 task_store 供前端轮询。

复刻 batch_ocr_task.py 的进度范式：
  update_task(progress=5 + int(90 * (idx+1) / total))
"""

from __future__ import annotations

import asyncio
import logging

from app.infrastructure.tasks.celery_app import celery_app
from app.infrastructure.tasks.task_store import update_task

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Celery sync worker 中运行 async AgentModeService.run_once。"""
    return asyncio.run(coro)


@celery_app.task(name="tasks.agent_batch", bind=True)
def agent_batch_task(self, task_id: str, items: list[dict]) -> dict:
    """
    Agent 批量文档生成。

    :param task_id: task_store 记录 ID
    :param items: [{"file_name": str, "instruction": str, "session_id": str}, ...]
    """
    total = len(items)
    if total == 0:
        update_task(task_id, status="failed", error="未提供批量任务项")
        return {"items": []}

    update_task(
        task_id,
        status="running",
        progress=5,
        status_label="批量处理中",
        message=f"共 {total} 项任务",
    )

    # 延迟导入避免循环依赖 + 确保 Celery worker 环境就绪
    from app.services.agent_mode_service import get_agent_mode_service

    agent = get_agent_mode_service()
    results: list[dict] = []

    try:
        for idx, item in enumerate(items):
            file_name = item.get("file_name")
            instruction = item.get("instruction", "")
            session_id = item.get("session_id") or f"batch_{task_id}_{idx}"

            update_task(
                task_id,
                progress=5 + int(90 * idx / total),
                status_label=f"处理第 {idx + 1}/{total} 项",
                message=f"正在生成: {instruction[:50]}",
            )

            try:
                result = _run_async(
                    agent.run_once(
                        user_content=instruction,
                        file_name=file_name,
                        session_id=session_id,
                    )
                )
                results.append({
                    "index": idx,
                    "instruction": instruction,
                    "file_name": file_name,
                    "ok": result.get("success", False),
                    "task_id": result.get("task_id", ""),
                    "final_output": (result.get("final_output") or "")[:500],
                    "files": result.get("files", []),
                    "error": result.get("error", ""),
                })
            except Exception as exc:
                logger.exception("batch item %d failed", idx)
                results.append({
                    "index": idx,
                    "instruction": instruction,
                    "file_name": file_name,
                    "ok": False,
                    "error": str(exc),
                })

            # 每项完成后更新进度
            pct = 5 + int(90 * (idx + 1) / total)
            ok_count = sum(1 for r in results if r.get("ok"))
            update_task(
                task_id,
                progress=pct,
                message=f"已完成 {idx + 1}/{total}（成功 {ok_count}）",
            )

        ok_count = sum(1 for r in results if r.get("ok"))
        payload = {
            "total": total,
            "success": ok_count,
            "failed": total - ok_count,
            "items": results,
        }
        update_task(
            task_id,
            status="done",
            progress=100,
            status_label="完成",
            message=f"批量完成 {ok_count}/{total}",
            result=payload,
        )
        return payload

    except Exception as exc:
        logger.exception("agent_batch_task failed")
        update_task(
            task_id,
            status="failed",
            progress=100,
            status_label="失败",
            error=str(exc),
        )
        raise
