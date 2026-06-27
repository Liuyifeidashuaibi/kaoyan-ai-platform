"""
Agent 批量任务路由 — 多文件 + 多指令提交 + 进度轮询。

端点：
  POST /api/agent/batch           提交批量任务（多文件+多指令 → Celery → 返回 task_id）
  GET  /api/agent/batch/{task_id} 轮询批量任务进度（复用 task_store）
"""

from __future__ import annotations

import json
import logging
import uuid
import pathlib

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.config import get_settings
from app.infrastructure.tasks.agent_batch_task import agent_batch_task
from app.infrastructure.tasks.task_store import (
    bind_celery_id,
    create_task_record,
    get_task,
)
from app.utils.auth import require_user_id
from app.utils.file_utils import ensure_dir
from app.utils.response import error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent/batch", tags=["Agent批量任务"])
settings = get_settings()


@router.post("")
async def submit_batch(
    files: list[UploadFile] = File(default=[]),
    instructions: str = Form(..., description="JSON 数组，每项含 instruction(必填) 和 file_index(可选)"),
    user_id: str = Depends(require_user_id),
):
    """
    提交 Agent 批量文档生成任务。

    前端传入：
      - files: 多个文件上传（可选，有些项可能无文件）
      - instructions: JSON 字符串数组，每项格式：
          {"instruction": "生成论文", "file_index": 0}
          file_index 对应 files 列表索引（可选，无则该项无文件）

    返回 task_id，前端轮询 GET /api/agent/batch/{task_id} 获取进度。
    """
    # 解析 instructions JSON
    try:
        items_spec = json.loads(instructions) if isinstance(instructions, str) else instructions
    except json.JSONDecodeError as exc:
        return error_response(f"instructions JSON 格式错误: {exc}")

    if not isinstance(items_spec, list) or not items_spec:
        return error_response("instructions 必须是非空 JSON 数组")

    if len(items_spec) > 50:
        return error_response("单次最多 50 项任务")

    # 保存上传文件到 uploads/chat/
    chat_dir = settings.upload_path.parent / "chat"
    ensure_dir(chat_dir)

    saved_names: list[str | None] = [None] * len(files)
    for i, upload in enumerate(files):
        content = await upload.read()
        if not content:
            continue
        safe_name = pathlib.Path(upload.filename or f"batch_{i}.bin").name
        stem = pathlib.Path(safe_name).stem
        ext = pathlib.Path(safe_name).suffix
        file_id = uuid.uuid4().hex[:8]
        saved_name = f"{stem}_{file_id}{ext}"
        (chat_dir / saved_name).write_bytes(content)
        saved_names[i] = saved_name
        logger.info("[AgentBatch] 文件已保存: %s", saved_name)

    # 构建 items（每项含 file_name + instruction + session_id）
    items: list[dict] = []
    for spec in items_spec:
        instruction = spec.get("instruction", "").strip()
        if not instruction:
            continue
        file_index = spec.get("file_index")
        file_name = None
        if file_index is not None and 0 <= file_index < len(saved_names):
            file_name = saved_names[file_index]
        items.append({
            "instruction": instruction,
            "file_name": file_name,
            "session_id": f"batch_{uuid.uuid4().hex[:8]}",
        })

    if not items:
        return error_response("无有效任务项（instruction 不能为空）")

    # 创建 task_store 记录 + 提交 Celery
    task_id = create_task_record(
        "agent_batch",
        user_id=user_id,
        meta={"count": len(items), "has_files": any(it["file_name"] for it in items)},
    )
    async_result = agent_batch_task.delay(task_id, items)
    bind_celery_id(task_id, async_result.id)

    return success_response(
        {"task_id": task_id, "status": "pending", "item_count": len(items)},
        message=f"批量任务已提交（{len(items)} 项），后台处理中",
    )


@router.get("/{task_id}")
async def get_batch_status(
    task_id: str,
    user_id: str = Depends(require_user_id),
):
    """轮询批量任务进度与结果（复用 task_store）。"""
    record = get_task(task_id)
    if not record:
        return error_response("任务不存在或已过期", data={"id": task_id})
    owner = record.get("user_id")
    if owner and owner != user_id:
        return error_response("无权查看该任务")
    return success_response(record)
