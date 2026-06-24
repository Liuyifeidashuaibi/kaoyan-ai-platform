"""
试卷解析 API 路由 — 上传、查询、追问、收藏、生词导出、会话清理。

端点:
  POST /api/exam/upload              — 上传试卷图片，启动解析
  GET  /api/exam/{paper_id}          — 获取解析结果
  GET  /api/exam/{paper_id}/questions — 获取结构化题目列表
  POST /api/exam/{paper_id}/questions/{qid}/ask — 单题追问（流式）
  POST /api/exam/{paper_id}/favorite — 收藏题目到 kaoyan_bank
  POST /api/exam/{paper_id}/vocabulary/export — 导出英语生词
  DELETE /api/exam/session/{session_id} — 清理会话关联的临时试卷数据
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import ExamPaper, get_db
from app.schemas.exam import (
    ExamFavoriteRequest,
    ExamQuestionAskRequest,
    ExamQuestionResponse,
    ExamVocabularyExport,
)
from app.utils.file_utils import ensure_dir, save_upload_image
from app.utils.response import error_response, success_response

router = APIRouter(prefix="/api/exam", tags=["试卷解析"])
settings = get_settings()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _paper_to_dict(paper: ExamPaper) -> dict:
    """将 ORM 对象转为响应字典。"""
    parsed = None
    if paper.parsed_structure:
        try:
            parsed = json.loads(paper.parsed_structure)
        except (json.JSONDecodeError, TypeError):
            parsed = None

    analysis = None
    if paper.analysis_result:
        try:
            analysis = json.loads(paper.analysis_result)
        except (json.JSONDecodeError, TypeError):
            analysis = None

    return {
        "id": paper.id,
        "session_id": paper.session_id,
        "subject": paper.subject,
        "title": paper.title,
        "status": paper.status,
        "ocr_text": paper.ocr_text,
        "parsed_structure": parsed,
        "analysis_result": analysis,
        "created_at": paper.created_at.isoformat() if paper.created_at else "",
        "expires_at": paper.expires_at.isoformat() if paper.expires_at else None,
    }


# ---------------------------------------------------------------------------
# POST /api/exam/upload — 上传试卷图片，启动解析
# ---------------------------------------------------------------------------

@router.post("/upload")
async def upload_exam(
    subject: str = Form(..., description="科目: english | math"),
    session_id: str = Form(default="", description="关联聊天会话 ID"),
    title: str = Form(default="未命名试卷"),
    image_file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """上传试卷图片并启动异步解析流程。"""
    from app.infrastructure.tasks.task_store import create_task_record, bind_celery_id
    from app.infrastructure.tasks.exam_process_task import exam_process_task

    # 校验科目
    if subject not in ("english", "math"):
        return error_response("科目必须为 english 或 math")

    # 读取图片
    try:
        content = await image_file.read()
    except Exception as exc:
        logger.warning("读取试卷图片失败: %s", exc)
        return error_response("读取图片失败，请重试")

    if not content:
        return error_response("图片文件为空")

    if len(content) > settings.exam_max_image_size_bytes:
        max_mb = settings.exam_max_image_size_bytes // (1024 * 1024)
        return error_response(f"图片过大，上限 {max_mb}MB")

    # 图片落盘
    exam_upload_dir = settings.upload_path.parent / "exam"
    ensure_dir(exam_upload_dir)
    filename = image_file.filename or "exam.jpg"
    saved_path = save_upload_image(
        content,
        exam_upload_dir,
        filename,
        project_root=settings.root,
    )
    logger.info("[Exam] 图片已保存: %s (%d bytes)", saved_path, len(content))

    # 创建数据库记录
    expires_at = datetime.utcnow() + timedelta(days=settings.exam_temp_ttl_days)
    paper = ExamPaper(
        session_id=session_id or None,
        subject=subject,
        title=title,
        original_image_path=saved_path,
        status="pending",
        expires_at=expires_at,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)

    # 创建异步任务
    task_id = create_task_record(
        "exam_process",
        meta={"paper_id": paper.id, "subject": subject},
    )

    # 提交 Celery
    celery_result = exam_process_task.apply_async(
        args=[task_id, paper.id, subject, saved_path, session_id or None, None],
        task_id=task_id,
        queue="heavy",
    )
    bind_celery_id(task_id, celery_result.id)

    # 更新 DB 状态为 processing
    paper.status = "processing"
    db.commit()

    logger.info(
        "[Exam] 试卷已提交: paper_id=%d task_id=%s subject=%s",
        paper.id, task_id, subject,
    )

    return success_response(
        {
            "paper_id": paper.id,
            "task_id": task_id,
            "status": "pending",
            "message": "试卷已提交，正在解析",
        },
        message="试卷已提交",
    )


# ---------------------------------------------------------------------------
# GET /api/exam/{paper_id} — 获取解析结果
# ---------------------------------------------------------------------------

@router.get("/{paper_id}")
async def get_exam_paper(
    paper_id: int,
    db: Session = Depends(get_db),
):
    """获取试卷详情（含解析结果）。"""
    paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
    if not paper:
        return error_response("试卷不存在")

    return success_response(_paper_to_dict(paper))


# ---------------------------------------------------------------------------
# GET /api/exam/{paper_id}/questions — 获取结构化题目列表
# ---------------------------------------------------------------------------

@router.get("/{paper_id}/questions")
async def get_exam_questions(
    paper_id: int,
    db: Session = Depends(get_db),
):
    """获取试卷的结构化题目列表。"""
    paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
    if not paper:
        return error_response("试卷不存在")

    parsed = None
    if paper.parsed_structure:
        try:
            parsed = json.loads(paper.parsed_structure)
        except (json.JSONDecodeError, TypeError):
            pass

    sections = parsed.get("sections", []) if parsed else []
    total = sum(len(s.get("questions", [])) for s in sections)

    return success_response({
        "paper_id": paper.id,
        "subject": paper.subject,
        "total_questions": total,
        "sections": sections,
    })


# ---------------------------------------------------------------------------
# POST /api/exam/{paper_id}/questions/{qid}/ask — 单题追问（流式）
# ---------------------------------------------------------------------------

@router.post("/{paper_id}/questions/{qid}/ask")
async def ask_question(
    paper_id: int,
    qid: str,
    body: ExamQuestionAskRequest,
    db: Session = Depends(get_db),
):
    """针对单题发起追问，复用聊天流式接口。"""
    from app.services.ai_service import get_ai_service
    from app.services.chat_service import ChatService

    paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
    if not paper:
        return error_response("试卷不存在")

    # 从 parsed_structure 中找到对应题目
    parsed = None
    if paper.parsed_structure:
        try:
            parsed = json.loads(paper.parsed_structure)
        except (json.JSONDecodeError, TypeError):
            pass

    question_stem = ""
    if parsed:
        for section in parsed.get("sections", []):
            for q in section.get("questions", []):
                if str(q.get("id", "")) == str(qid):
                    question_stem = q.get("stem", "")
                    break
            if question_stem:
                break

    # 如果有分析结果，也带上
    analysis_context = ""
    if paper.analysis_result:
        try:
            analysis = json.loads(paper.analysis_result)
            for q in analysis.get("questions", []):
                if str(q.get("id", "")) == str(qid):
                    answer = q.get("answer", "") or q.get("stem_translated", "")
                    analysis_text = q.get("analysis", "")
                    if answer or analysis_text:
                        analysis_context = f"\n\n已有解析:\n答案: {answer}\n{analysis_text}"
                    break
        except (json.JSONDecodeError, TypeError):
            pass

    # 构建 prompt
    system_prompt = (
        "你是考研辅导专家。请针对用户提出的具体题目进行详细解答。"
        "使用 LaTeX 格式书写数学公式（行内 $...$，独立 $$...$$）。"
        "语言简洁，重点突出。"
    )

    # RAG 上下文：从 kaoyan_bank 检索同科目相关题目
    rag_context = ""
    try:
        from app.infrastructure.vector.kaoyan_bank import get_kaoyan_bank_store
        bank = get_kaoyan_bank_store()
        # 用题目题干 + 用户追问 作为查询，按科目过滤
        rag_query = f"{question_stem}\n{body.question}" if body.question else question_stem
        rag_context = bank.search_context(
            rag_query,
            subject=paper.subject,
            top_k=3,
        )
    except Exception as exc:
        logger.warning("RAG 检索失败（不影响主流程）: %s", exc)

    if rag_context:
        system_prompt += f"\n\n以下是知识库中的相关题目，可作参考:\n{rag_context}"

    user_content = (
        f"题目: {question_stem}\n\n"
        f"{analysis_context}\n\n"
        f"我的问题: {body.question}"
    )

    ai = get_ai_service()

    async def event_generator():
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        async for token in ai.chat_stream(messages):
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# POST /api/exam/{paper_id}/favorite — 收藏题目到 kaoyan_bank
# ---------------------------------------------------------------------------

@router.post("/{paper_id}/favorite")
async def favorite_questions(
    paper_id: int,
    body: ExamFavoriteRequest,
    db: Session = Depends(get_db),
):
    """收藏指定题目到永久知识库 kaoyan_bank。"""
    from app.infrastructure.vector.kaoyan_bank import get_kaoyan_bank_store

    paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
    if not paper:
        return error_response("试卷不存在")

    # 从分析结果中提取题目数据
    analysis = None
    if paper.analysis_result:
        try:
            analysis = json.loads(paper.analysis_result)
        except (json.JSONDecodeError, TypeError):
            pass

    if not analysis:
        return error_response("试卷尚未完成解析")

    # 按 ID 索引分析结果
    analysis_map = {}
    for q in analysis.get("questions", []):
        analysis_map[str(q.get("id", ""))] = q

    bank = get_kaoyan_bank_store()
    count = 0

    for qid in body.question_ids:
        q_data = analysis_map.get(str(qid))
        if not q_data:
            continue

        stem = q_data.get("stem", "")
        if not stem.strip():
            continue

        added = bank.add_question(
            stem=stem,
            answer=q_data.get("answer", "") or q_data.get("stem_translated", ""),
            analysis=q_data.get("analysis", ""),
            key_points=q_data.get("key_points", ""),
            subject=body.subject or paper.subject,
            source="user_favorite",
        )
        count += added

    return success_response(
        {"favorited": count},
        message=f"已收藏 {count} 道题目",
    )


# ---------------------------------------------------------------------------
# POST /api/exam/{paper_id}/vocabulary/export — 导出英语生词
# ---------------------------------------------------------------------------

@router.post("/{paper_id}/vocabulary/export")
async def export_vocabulary(
    paper_id: int,
    db: Session = Depends(get_db),
):
    """从英语试卷中导出核心生词列表。"""
    paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
    if not paper:
        return error_response("试卷不存在")

    if paper.subject != "english":
        return error_response("仅英语试卷支持生词导出")

    analysis = None
    if paper.analysis_result:
        try:
            analysis = json.loads(paper.analysis_result)
        except (json.JSONDecodeError, TypeError):
            pass

    vocabulary = analysis.get("vocabulary", []) if analysis else []

    # 尝试从 ECDICT 补充释义
    enriched = []
    try:
        from app.modules.word_dict.service import WordDictService
        wds = WordDictService()
        for item in vocabulary:
            word = item.get("word", "")
            entry = None
            if word:
                try:
                    entry = await wds.query(db, word, mode="hover")
                except Exception:
                    entry = None
            enriched.append({
                "word": word,
                "phonetic": "",
                "definition": str(entry) if entry else "",
                "context": item.get("context", ""),
            })
    except Exception as exc:
        logger.warning("ECDICT 查询失败，使用原始词汇: %s", exc)
        enriched = [
            {
                "word": item.get("word", ""),
                "phonetic": "",
                "definition": "",
                "context": item.get("context", ""),
            }
            for item in vocabulary
        ]

    return success_response({
        "paper_id": paper.id,
        "vocabulary": enriched,
        "total_words": len(enriched),
    })


# ---------------------------------------------------------------------------
# DELETE /api/exam/session/{session_id} — 清理会话关联的临时试卷数据
# ---------------------------------------------------------------------------

@router.delete("/session/{session_id}")
async def cleanup_session(
    session_id: str,
    db: Session = Depends(get_db),
):
    """清理指定聊天会话关联的所有临时试卷数据（含向量）。"""
    from app.infrastructure.vector.temp_paper import get_temp_paper_store

    # 查找关联试卷
    papers = db.query(ExamPaper).filter(ExamPaper.session_id == session_id).all()
    deleted_papers = len(papers)

    # 删除向量
    deleted_vectors = 0
    try:
        temp_store = get_temp_paper_store()
        deleted_vectors = temp_store.delete_by_session(session_id)
    except Exception as exc:
        logger.warning("清理临时向量失败: %s", exc)

    # 删除图片文件
    for paper in papers:
        if paper.original_image_path:
            try:
                img_path = Path(paper.original_image_path)
                if not img_path.is_absolute():
                    img_path = settings.root / img_path
                img_path.unlink(missing_ok=True)
            except Exception as exc:
                logger.warning("删除图片失败: %s", exc)

    # 删除数据库记录
    db.query(ExamPaper).filter(ExamPaper.session_id == session_id).delete()
    db.commit()

    logger.info(
        "[Exam] 会话清理完成: session=%s, papers=%d, vectors=%d",
        session_id, deleted_papers, deleted_vectors,
    )

    return success_response({
        "session_id": session_id,
        "deleted_papers": deleted_papers,
        "deleted_vectors": deleted_vectors,
        "message": "清理完成",
    })


# ---------------------------------------------------------------------------
# POST /api/exam/rag/search — RAG 科目隔离检索
# ---------------------------------------------------------------------------

@router.post("/rag/search")
async def rag_search(
    query: str = Form(..., description="查询文本"),
    subject: str = Form(default="", description="科目过滤: english/math/空=全部"),
    top_k: int = Form(default=5, description="返回结果数"),
):
    """
    RAG 科目隔离检索：从 kaoyan_bank 知识库中检索相关题目。

    通过 subject 参数实现按科目逻辑隔离，避免跨科目干扰。
    """
    from app.infrastructure.vector.kaoyan_bank import get_kaoyan_bank_store

    if not query.strip():
        return error_response("查询文本不能为空")

    bank = get_kaoyan_bank_store()
    subject_filter = subject if subject else None

    try:
        results = bank.query(query, top_k=top_k, subject=subject_filter)
        items = [
            {
                "text": r.text,
                "score": r.score,
                "subject": r.metadata.get("subject", ""),
                "year": r.metadata.get("year", ""),
                "source": r.metadata.get("source", ""),
            }
            for r in results
        ]
        return success_response({
            "query": query,
            "subject_filter": subject_filter,
            "results": items,
            "total": len(items),
        })
    except Exception as exc:
        logger.error("RAG 检索失败: %s", exc)
        return error_response(f"检索失败: {exc}")
