"""
试卷解析 Celery 异步任务 — 分片并行处理，进度追踪。
"""

from __future__ import annotations

import asyncio
import json
import logging

from app.infrastructure.tasks.celery_app import celery_app
from app.infrastructure.tasks.task_store import update_task

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Celery sync worker 中运行 async 函数。"""
    return asyncio.run(coro)


@celery_app.task(name="tasks.exam_process", bind=True)
def exam_process_task(
    self,
    task_id: str,
    paper_id: int,
    subject: str,
    image_path: str,
    session_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    """
    试卷解析异步任务。

    流程: 图像预处理 → OCR → 结构化解析 → 分片 → 并行 AI 处理 → 合并结果 → 入库

    :param task_id: 任务 ID（用于进度追踪）
    :param paper_id: ExamPaper 数据库 ID
    :param subject: "english" | "math"
    :param image_path: 图片路径（相对项目根）
    :param session_id: 聊天会话 ID
    :param user_id: 用户 ID
    """
    from pathlib import Path
    from app.config import get_settings
    from app.database import ExamPaper, SessionLocal
    from app.services.exam.image_preprocessor import preprocess_exam_image
    from app.services.exam.exam_parser import parse_exam_text
    from app.services.exam.sharded_processor import create_shards, process_shards_parallel, merge_shard_results
    from app.services.media_service import get_media_service
    from app.utils.image_url import validate_upload_bytes

    settings = get_settings()

    update_task(task_id, status="running", progress=5, status_label="初始化", message="开始处理试卷")

    try:
        # 1. 读取图片
        img_path = Path(image_path)
        if not img_path.is_absolute():
            img_path = settings.root / img_path

        if not img_path.is_file():
            update_task(task_id, status="failed", progress=100, error="图片文件不存在")
            return {"error": "图片文件不存在"}

        image_bytes = img_path.read_bytes()
        update_task(task_id, progress=10, status_label="预处理", message="图像预处理中")

        # 2. 图像预处理
        processed_bytes = preprocess_exam_image(image_bytes)
        resolved = validate_upload_bytes(
            processed_bytes, img_path.name, max_bytes=settings.exam_max_image_size_bytes,
        )
        update_task(task_id, progress=20, status_label="OCR", message="文字识别中")

        # 3. OCR（使用试卷专用 prompt 忽略手写内容）
        media = get_media_service()
        from app.services.media_service import EXAM_OCR_PROMPT

        async def _ocr():
            return await media.extract_image_text(
                resolved, processed_bytes, prompt=EXAM_OCR_PROMPT
            )

        ocr_text = _run_async(_ocr())
        update_task(task_id, progress=40, status_label="解析", message="结构化拆分中")

        # 4. 结构化解析
        parsed = parse_exam_text(ocr_text, subject=subject)
        parsed_dict = parsed.to_dict()
        update_task(task_id, progress=50, status_label="分片", message=f"共 {parsed.total_questions} 题，分片处理中")

        # 5. 分片
        shards = create_shards(parsed_dict)

        # 6. 并行处理
        if subject == "english":
            from app.services.exam.english_exam_service import process_english_shard
            processor = process_english_shard
        else:
            from app.services.exam.math_exam_service import process_math_shard
            processor = process_math_shard

        async def _process():
            return await process_shards_parallel(shards, processor)

        results = _run_async(_process())
        merged = merge_shard_results(results)

        update_task(task_id, progress=85, status_label="保存", message="保存结果")

        # 7. 更新数据库
        db = SessionLocal()
        try:
            paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
            if paper:
                paper.ocr_text = ocr_text
                paper.parsed_structure = json.dumps(parsed_dict, ensure_ascii=False)
                paper.analysis_result = json.dumps(merged, ensure_ascii=False)
                paper.status = "done"
                db.commit()
        finally:
            db.close()

        # 8. 向量入库
        try:
            from app.infrastructure.vector.temp_paper import get_temp_paper_store

            segments = [q.get("stem", "") for q in merged.get("questions", []) if q.get("stem")]
            temp_store = get_temp_paper_store()
            temp_store.ingest_paper_segments(
                segments,
                session_id=session_id or "",
                paper_id=paper_id,
                subject=subject,
            )
        except Exception as exc:
            logger.warning("向量入库失败（不影响主流程）: %s", exc)

        update_task(
            task_id,
            status="done",
            progress=100,
            status_label="完成",
            message=f"解析完成: {merged.get('success_shards', 0)}/{merged.get('total_shards', 0)} 分片成功",
            result={"paper_id": paper_id, "questions": len(merged.get("questions", []))},
        )

        return {
            "paper_id": paper_id,
            "questions": len(merged.get("questions", [])),
            "errors": merged.get("errors", []),
        }

    except Exception as exc:
        logger.exception("试卷处理失败")
        # 更新数据库状态
        try:
            db = SessionLocal()
            paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
            if paper:
                paper.status = "failed"
                db.commit()
            db.close()
        except Exception:
            pass

        update_task(
            task_id,
            status="failed",
            progress=100,
            status_label="失败",
            error=str(exc),
        )
        raise
