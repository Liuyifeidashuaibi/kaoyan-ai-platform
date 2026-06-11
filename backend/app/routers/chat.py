"""
AI 聊天路由 — 会话管理、消息历史、流式对话、图片上传。

对应前端左侧侧边栏：新建聊天、搜索历史、错题本入口（错题本见 wrong_questions 路由）。
"""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.schemas.chat import ChatSearchRequest, ChatSendRequest, ChatSessionCreate
from app.services.chat_service import ChatService
from app.utils.file_utils import is_allowed_image
from app.utils.image_url import resolve_public_image_url
from app.utils.response import error_response, success_response

router = APIRouter(prefix="/api/chat", tags=["AI聊天"])
settings = get_settings()


def _get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    return ChatService(db)


@router.post("/sessions")
async def create_session(
    body: ChatSessionCreate,
    service: ChatService = Depends(_get_chat_service),
):
    """新建聊天会话。"""
    session = service.create_session(body.title)
    return success_response(
        {
            "id": session.id,
            "title": session.title,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
        },
        message="会话创建成功",
    )


@router.get("/sessions")
async def list_sessions(
    keyword: str = Query(default="", description="搜索会话标题"),
    service: ChatService = Depends(_get_chat_service),
):
    """获取聊天历史列表，支持关键词搜索。"""
    sessions = service.list_sessions(keyword)
    data = [
        {
            "id": s.id,
            "title": s.title,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        }
        for s in sessions
    ]
    return success_response(data)


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    service: ChatService = Depends(_get_chat_service),
):
    """删除指定会话及其所有消息。"""
    ok = service.delete_session(session_id)
    if not ok:
        return error_response("会话不存在")
    return success_response(message="会话已删除")


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str,
    service: ChatService = Depends(_get_chat_service),
):
    """获取某会话的全部消息记录。"""
    session = service.get_session(session_id)
    if not session:
        return error_response("会话不存在")
    messages = service.get_messages(session_id)
    data = [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "image_path": m.image_path,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]
    return success_response(data)


@router.post("/upload-image")
async def upload_chat_image(
    file: UploadFile = File(...),
    service: ChatService = Depends(_get_chat_service),
):
    """
    上传聊天图片（数学题、截图等）。

    返回图片相对路径，发送消息时携带 image_path 字段。
    """
    if not file.filename or not is_allowed_image(file.filename):
        return error_response("仅支持 jpg/png/gif/webp/bmp 格式图片")

    content = await file.read()
    # 聊天图片也存到 uploads 目录下的 chat 子目录
    chat_upload_dir = settings.upload_path.parent / "chat"
    rel_path = service.save_chat_image(content, file.filename, chat_upload_dir)
    payload: dict = {"image_path": rel_path}
    try:
        payload["image_url"] = resolve_public_image_url(rel_path, settings)
    except Exception:
        payload["image_url"] = None
    return success_response(payload, message="图片上传成功")


@router.post("/send/stream")
async def send_message_stream(
    session_id: str = Form(...),
    content: str = Form(...),
    image_path: str | None = Form(default=None),
    skip_user_save: bool = Form(default=False),
    service: ChatService = Depends(_get_chat_service),
):
    """
    发送消息并以 SSE 流式返回 AI 回复。

    支持多轮对话；若携带 image_path 则启用多模态图片题识别。
    Content-Type: multipart/form-data
    """
    session = service.get_session(session_id)
    if not session:
        return error_response("会话不存在")

    async def event_generator():
        async for chunk in service.stream_reply(
            session_id, content, image_path, skip_user_save=skip_user_save
        ):
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/send")
async def send_message(
    body: ChatSendRequest,
    service: ChatService = Depends(_get_chat_service),
):
    """
    非流式发送消息（备用接口，收集完整回复后返回）。
    """
    session = service.get_session(body.session_id)
    if not session:
        return error_response("会话不存在")

    full: list[str] = []
    async for chunk in service.stream_reply(body.session_id, body.content, body.image_path):
        if chunk.startswith("data: "):
            payload = chunk[6:].strip()
            try:
                obj = json.loads(payload)
                if "token" in obj:
                    full.append(obj["token"])
            except json.JSONDecodeError:
                pass

    return success_response({"content": "".join(full)}, message="回复完成")


@router.post("/search")
async def search_sessions(
    body: ChatSearchRequest,
    service: ChatService = Depends(_get_chat_service),
):
    """搜索历史会话（与 GET /sessions?keyword= 等效）。"""
    sessions = service.list_sessions(body.keyword)
    data = [
        {
            "id": s.id,
            "title": s.title,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        }
        for s in sessions
    ]
    return success_response(data)
