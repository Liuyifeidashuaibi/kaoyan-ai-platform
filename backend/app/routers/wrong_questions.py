"""
错题本路由 — 独立并列功能模块。

功能：科目分类管理、多类型学习资料上传、笔记编辑、AI 解析、按分类/类型筛选、一键发起新聊天。
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
from app.utils.auth import optional_user_id, require_user_id
from app.utils.file_utils import is_allowed_learning_material, normalize_upload_filename
from app.utils.response import error_response, success_response

router = APIRouter(prefix="/api/wrong-questions", tags=["错题本"])
settings = get_settings()


def _get_wq_service(db: Session = Depends(get_db)) -> WrongQuestionService:
    return WrongQuestionService(db)


def _serialize_question(service: WrongQuestionService, question) -> dict:
    data = service._to_dict(question)
    data["created_at"] = data["created_at"].isoformat()
    return data


# ==================== 分类管理 ====================


@router.post("/categories")
async def create_category(
    body: CategoryCreate,
    user_id: str = Depends(require_user_id),
    service: WrongQuestionService = Depends(_get_wq_service),
):
    """手动创建科目分类，如「数学一」「政治」「英语」。"""
    cat = service.create_category(body.name, user_id)
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
async def list_categories(
    user_id: str = Depends(require_user_id),
    service: WrongQuestionService = Depends(_get_wq_service),
):
    """获取当前用户的科目分类及资料数量。"""
    data = service.list_categories(user_id)
    for item in data:
        item["created_at"] = item["created_at"].isoformat()
    return success_response(data)


# ==================== 公开资料（个人主页） ====================


@router.get("/public")
async def list_public_materials(
    user_id: str = Query(..., description="用户 UUID"),
    service: WrongQuestionService = Depends(_get_wq_service),
):
    """列出某用户公开的学习资料，供个人主页展示。"""
    data = service.list_public_questions(user_id)
    for item in data:
        item["created_at"] = item["created_at"].isoformat()
    return success_response(data)


# ==================== 错题 CRUD ====================


@router.post("/upload")
async def upload_wrong_question(
    file: UploadFile = File(..., description="学习资料文件"),
    category_id: int | None = Form(default=None, description="已有分类 ID"),
    category_name: str | None = Form(default=None, description="新建分类名称"),
    title: str = Form(default="未命名资料"),
    notes: str = Form(default="", description="用户 Markdown 笔记"),
    is_public: bool = Form(default=False, description="是否公开到个人主页"),
    user_id: str = Depends(require_user_id),
    service: WrongQuestionService = Depends(_get_wq_service),
):
    """
    上传学习资料并创建记录（支持图片、视频、文档、音频等）。

    需指定 category_id（已有分类）或 category_name（自动创建分类）。
    """
    resolved_filename = normalize_upload_filename(file.filename, file.content_type)
    if not resolved_filename or not is_allowed_learning_material(
        resolved_filename, file.content_type
    ):
        return error_response(
            "不支持的文件格式。支持：图片(jpg/png/gif/webp)、"
            "视频(mp4/webm/mov/avi/mkv)、文档(pdf/doc/docx/txt/md/ppt/xls)、音频(mp3/wav/m4a)"
        )

    if category_id is None and not category_name:
        return error_response("请提供 category_id 或 category_name")

    if category_id is not None:
        cat = service._get_user_category(category_id, user_id)
        if not cat:
            return error_response("分类不存在")
    else:
        cat = service.get_or_create_category(category_name, user_id)  # type: ignore[arg-type]
        category_id = cat.id

    content = await file.read()
    file_path, file_type = service.save_file(
        content, resolved_filename, settings.upload_path
    )

    question = service.create_question(
        category_id=category_id,
        file_path=file_path,
        file_type=file_type,
        user_id=user_id,
        title=title,
        notes=notes,
        original_filename=resolved_filename,
        is_public=is_public,
    )

    return success_response(
        _serialize_question(service, question),
        message="资料上传成功",
    )


@router.get("")
async def list_wrong_questions(
    category_id: int | None = Query(default=None, description="按分类筛选"),
    file_type: str | None = Query(
        default=None,
        description="按资料类型筛选：image / video / document / audio / other",
    ),
    user_id: str = Depends(require_user_id),
    service: WrongQuestionService = Depends(_get_wq_service),
):
    """当前用户的学习资料列表。"""
    data = service.list_questions(user_id, category_id, file_type=file_type)
    for item in data:
        item["created_at"] = item["created_at"].isoformat()
    return success_response(data)


@router.get("/{question_id}")
async def get_wrong_question(
    question_id: int,
    viewer_id: str | None = Depends(optional_user_id),
    service: WrongQuestionService = Depends(_get_wq_service),
):
    """查看资料详情；本人可看全部，他人仅可看公开资料。"""
    q = service.get_question(
        question_id,
        user_id=viewer_id,
        allow_public=True,
    )
    if not q:
        return error_response("资料不存在或无权查看")
    return success_response(_serialize_question(service, q))


@router.put("/{question_id}")
async def update_wrong_question(
    question_id: int,
    body: WrongQuestionUpdate,
    user_id: str = Depends(require_user_id),
    service: WrongQuestionService = Depends(_get_wq_service),
):
    """更新资料标题、笔记、分类或公开状态。"""
    q = service.update_question(
        question_id,
        user_id,
        title=body.title,
        notes=body.notes,
        category_id=body.category_id,
        is_public=body.is_public,
    )
    if not q:
        return error_response("资料不存在")
    return success_response(_serialize_question(service, q), message="更新成功")


@router.delete("/{question_id}")
async def delete_wrong_question(
    question_id: int,
    user_id: str = Depends(require_user_id),
    service: WrongQuestionService = Depends(_get_wq_service),
):
    """删除资料记录。"""
    ok = service.delete_question(question_id, user_id)
    if not ok:
        return error_response("资料不存在")
    return success_response(message="资料已删除")


@router.post("/analyze")
async def analyze_wrong_question(
    body: WrongQuestionAnalyzeRequest,
    user_id: str = Depends(require_user_id),
    service: WrongQuestionService = Depends(_get_wq_service),
):
    """
    对图片资料进行 AI 解析（qwen-vl-max）。

    解析结果写入 ai_analysis 字段并同步到私有知识库。
    """
    q = service.get_question(body.question_id, user_id=user_id)
    if not q:
        return error_response("资料不存在")
    file_type = q.file_type or "image"
    if file_type != "image":
        return error_response("AI 解析仅支持图片类型资料")

    analysis = await service.analyze_question(body.question_id, user_id)
    if analysis is None:
        return error_response("资料不存在")
    return success_response({"ai_analysis": analysis}, message="AI 解析完成")


@router.post("/{question_id}/start-chat")
async def start_chat_from_question(
    question_id: int,
    user_id: str = Depends(require_user_id),
    db: Session = Depends(get_db),
    wq_service: WrongQuestionService = Depends(_get_wq_service),
):
    """
    一键发起新聊天 — 基于错题内容创建会话并预填上下文。

    前端拿到 session_id 后跳转到聊天页继续追问。
    """
    q = wq_service.get_question(question_id, user_id=user_id)
    if not q:
        return error_response("资料不存在")

    chat_service = ChatService(db)
    session = chat_service.create_session(title=f"追问：{q.title}")

    context_parts = [
        f"我正在复习【{q.category.name}】科目的错题：{q.title}",
    ]
    if q.notes:
        context_parts.append(f"我的笔记：{q.notes}")
    if q.ai_analysis:
        context_parts.append(f"已有 AI 解析：{q.ai_analysis}")
    context_parts.append("请基于以上错题背景，帮我继续解答和追问。")

    initial_msg = "\n".join(context_parts)
    chat_service.save_message(
        session.id,
        "user",
        initial_msg,
        q.file_path or q.image_path,
    )

    return success_response(
        {
            "session_id": session.id,
            "title": session.title,
            "image_path": q.file_path or q.image_path,
            "initial_message": initial_msg,
        },
        message="已创建追问会话",
    )
