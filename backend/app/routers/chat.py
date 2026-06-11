"""
AI 聊天路由 — 会话管理、消息历史、流式对话、图片处理。

图片策略：
  - 本地上传：落盘到 uploads/chat/，同时转 Base64 发给 VL 模型，刷新后仍可显示
  - 公网链接：仅 https://，拦截内网/本机
  - 错题本追问：沿用 uploads/ 磁盘路径（转 Base64）
"""

import json
import logging
from dataclasses import replace as dc_replace

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.schemas.chat import ChatSearchRequest, ChatSendRequest, ChatSessionCreate
from app.services.chat_service import ChatService
from app.utils.file_utils import ensure_dir, save_upload_image
from app.utils.image_url import ImageProcessingError, ResolvedImage, resolve_chat_image
from app.utils.response import error_response, success_response

router = APIRouter(prefix="/api/chat", tags=["AI聊天"])
settings = get_settings()
logger = logging.getLogger(__name__)


def _get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    return ChatService(db)


async def _read_image_file(
    image_file: UploadFile | None,
) -> tuple[bytes | None, str | None]:
    """读取上传文件的字节内容，空文件返回 (None, None)。"""
    if not image_file:
        return None, None

    filename = image_file.filename or "upload.jpg"
    try:
        content = await image_file.read()
    except Exception as exc:
        raise ImageProcessingError(
            "读取上传图片失败，请重试。",
            log_detail=str(exc),
        ) from exc

    if not content:
        logger.warning("[Router] 收到空图片文件: filename=%s", filename)
        return None, None

    logger.info("[Router] 收到图片上传: filename=%s, bytes=%d", filename, len(content))
    return content, filename


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


@router.post("/send/stream")
async def send_message_stream(
    session_id: str = Form(...),
    content: str = Form(...),
    image_file: UploadFile | None = File(default=None),
    image_url: str | None = Form(default=None),
    image_path: str | None = Form(default=None),
    skip_user_save: bool = Form(default=False),
    service: ChatService = Depends(_get_chat_service),
):
    """
    发送消息并以 SSE 流式返回 AI 回复。

    图片输入（三选一，优先级从高到低）：
      - image_file：本地上传，落盘 uploads/chat/ + 转 Base64 给 VL 模型
      - image_url：公网 https 图片链接
      - image_path：错题本追问等已落盘相对路径

    也可在 content 中直接粘贴 https 图片链接。
    """
    session = service.get_session(session_id)
    if not session:
        return error_response("会话不存在")

    try:
        image_bytes, image_filename = await _read_image_file(image_file)

        # ── 聊天图片落盘（uploads/chat/），确保刷新后仍可显示 ──
        saved_image_path: str | None = None
        if image_bytes:
            chat_upload_dir = settings.upload_path.parent / "chat"
            ensure_dir(chat_upload_dir)
            saved_image_path = save_upload_image(
                image_bytes,
                chat_upload_dir,
                image_filename or "image.jpg",
                project_root=settings.root,
            )
            logger.info("[Router] 图片已落盘: %s", saved_image_path)

        resolved: ResolvedImage | None = await resolve_chat_image(
            content=content,
            image_bytes=image_bytes,
            image_filename=image_filename,
            image_url_field=image_url,
            image_path_legacy=image_path,
            settings=settings,
        )

        # 把磁盘路径写入 storage_ref，chat_service 会用它存入 DB image_path 字段
        if resolved is not None and saved_image_path is not None:
            resolved = dc_replace(resolved, storage_ref=saved_image_path)

    except ImageProcessingError as exc:
        logger.warning("[Router] 图片处理失败: %s | %s", exc.user_message, exc.log_detail)
        return error_response(exc.user_message)

    logger.info(
        "[Router] send/stream | session=%s | has_image=%s | source=%s | storage_ref=%s | content=%r",
        session_id,
        resolved is not None,
        resolved.source_type if resolved else "none",
        resolved.storage_ref if resolved else "none",
        content[:80],
    )

    async def event_generator():
        async for chunk in service.stream_reply(
            session_id,
            content,
            resolved,
            skip_user_save=skip_user_save,
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
    """非流式发送消息（备用接口，收集完整回复后返回）。"""
    session = service.get_session(body.session_id)
    if not session:
        return error_response("会话不存在")

    try:
        resolved = await resolve_chat_image(
            content=body.content,
            image_bytes=None,
            image_filename=None,
            image_url_field=body.image_url,
            image_path_legacy=body.image_path,
            settings=settings,
        )
    except ImageProcessingError as exc:
        return error_response(exc.user_message)

    full: list[str] = []
    async for chunk in service.stream_reply(body.session_id, body.content, resolved):
        if chunk.startswith("data: "):
            payload = chunk[6:].strip()
            try:
                obj = json.loads(payload)
                if "token" in obj:
                    full.append(obj["token"])
                if "error" in obj:
                    return error_response(obj["error"])
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
