"""
错题本路由 — 独立并列功能模块。

功能：科目分类管理、错题图片上传、笔记编辑、AI 解析、按分类筛选、一键发起新聊天。
"""

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.schemas.wrong_questions import (
    CategoryCreate,
    WrongQuestionAnalyzeRequest,
    WrongQuestionUpdate,
)
from app.services.chat_service import ChatService
from app.services.wrong_question_service import WrongQuestionService
from app.utils.file_utils import is_allowed_image
from app.utils.response import error_response, success_response

router = APIRouter(prefix="/api/wrong-questions", tags=["错题本"])
settings = get_settings()


def _get_wq_service(db: Session = Depends(get_db)) -> WrongQuestionService:
    return WrongQuestionService(db)


# ==================== 分类管理 ====================


@router.post("/categories")
async def create_category(
    body: CategoryCreate,
    service: WrongQuestionService = Depends(_get_wq_service),
):
    """手动创建科目分类，如「数学一」「政治」「英语」。"""
    cat = service.create_category(body.name)
    return success_response(
        {
            "id": cat.id,
            "name": cat.name,
            "created_at": cat.created_at.isoformat(),
            "question_count": 0,
        },
        message="分类创建成功",
    )


@router.get("/categories")
async def list_categories(service: WrongQuestionService = Depends(_get_wq_service)):
    """获取所有科目分类及错题数量。"""
    data = service.list_categories()
    for item in data:
        item["created_at"] = item["created_at"].isoformat()
    return success_response(data)


# ==================== 错题 CRUD ====================


@router.post("/upload")
async def upload_wrong_question(
    file: UploadFile = File(..., description="错题图片"),
    category_id: int | None = Form(default=None, description="已有分类 ID"),
    category_name: str | None = Form(default=None, description="新建分类名称"),
    title: str = Form(default="未命名错题"),
    notes: str = Form(default="", description="用户 Markdown 笔记"),
    service: WrongQuestionService = Depends(_get_wq_service),
):
    """
    上传错题图片并创建记录。

    需指定 category_id（已有分类）或 category_name（自动创建分类）。
    """
    if not file.filename or not is_allowed_image(file.filename):
        return error_response("仅支持 jpg/png/gif/webp/bmp 格式图片")

    if category_id is None and not category_name:
        return error_response("请提供 category_id 或 category_name")

    # 确定分类
    if category_id is not None:
        from app.database import WrongQuestionCategory

        db = service.db
        cat = db.query(WrongQuestionCategory).filter_by(id=category_id).first()
        if not cat:
            return error_response("分类不存在")
    else:
        cat = service.get_or_create_category(category_name)  # type: ignore[arg-type]
        category_id = cat.id

    content = await file.read()
    image_path = service.save_image(content, file.filename, settings.upload_path)

    question = service.create_question(
        category_id=category_id,
        image_path=image_path,
        title=title,
        notes=notes,
    )

    return success_response(
        service._to_dict(question),
        message="错题上传成功",
    )


@router.get("")
async def list_wrong_questions(
    category_id: int | None = Query(default=None, description="按分类筛选"),
    service: WrongQuestionService = Depends(_get_wq_service),
):
    """
    错题列表 — 支持按分类筛选。

    返回缩略图路径 + 标题，移动端友好。
    """
    data = service.list_questions(category_id)
    for item in data:
        item["created_at"] = item["created_at"].isoformat()
    return success_response(data)


@router.get("/{question_id}")
async def get_wrong_question(
    question_id: int,
    service: WrongQuestionService = Depends(_get_wq_service),
):
    """查看单条错题详情：大图、笔记、AI 解析。"""
    q = service.get_question(question_id)
    if not q:
        return error_response("错题不存在")
    data = service._to_dict(q)
    data["created_at"] = data["created_at"].isoformat()
    return success_response(data)


@router.put("/{question_id}")
async def update_wrong_question(
    question_id: int,
    body: WrongQuestionUpdate,
    service: WrongQuestionService = Depends(_get_wq_service),
):
    """更新错题标题、笔记或分类。"""
    q = service.update_question(
        question_id,
        title=body.title,
        notes=body.notes,
        category_id=body.category_id,
    )
    if not q:
        return error_response("错题不存在")
    data = service._to_dict(q)
    data["created_at"] = data["created_at"].isoformat()
    return success_response(data, message="更新成功")


@router.delete("/{question_id}")
async def delete_wrong_question(
    question_id: int,
    service: WrongQuestionService = Depends(_get_wq_service),
):
    """删除错题记录。"""
    ok = service.delete_question(question_id)
    if not ok:
        return error_response("错题不存在")
    return success_response(message="错题已删除")


@router.post("/analyze")
async def analyze_wrong_question(
    body: WrongQuestionAnalyzeRequest,
    service: WrongQuestionService = Depends(_get_wq_service),
):
    """
    对错题图片进行 AI 解析（qwen-vl-max）。

    解析结果写入 ai_analysis 字段并同步到私有知识库。
    """
    analysis = await service.analyze_question(body.question_id)
    if analysis is None:
        return error_response("错题不存在")
    return success_response({"ai_analysis": analysis}, message="AI 解析完成")


@router.post("/{question_id}/start-chat")
async def start_chat_from_question(
    question_id: int,
    db: Session = Depends(get_db),
    wq_service: WrongQuestionService = Depends(_get_wq_service),
):
    """
    一键发起新聊天 — 基于错题内容创建会话并预填上下文。

    前端拿到 session_id 后跳转到聊天页继续追问。
    """
    q = wq_service.get_question(question_id)
    if not q:
        return error_response("错题不存在")

    chat_service = ChatService(db)
    session = chat_service.create_session(title=f"追问：{q.title}")

    # 预填一条系统上下文消息，帮助 AI 理解错题背景
    context_parts = [
        f"我正在复习【{q.category.name}】科目的错题：{q.title}",
    ]
    if q.notes:
        context_parts.append(f"我的笔记：{q.notes}")
    if q.ai_analysis:
        context_parts.append(f"已有 AI 解析：{q.ai_analysis}")
    context_parts.append("请基于以上错题背景，帮我继续解答和追问。")

    initial_msg = "\n".join(context_parts)
    chat_service.save_message(session.id, "user", initial_msg, q.image_path)

    return success_response(
        {
            "session_id": session.id,
            "title": session.title,
            "image_path": q.image_path,
            "initial_message": initial_msg,
        },
        message="已创建追问会话",
    )
