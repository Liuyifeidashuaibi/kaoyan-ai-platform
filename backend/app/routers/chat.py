"""
AI 聊天路由 — 会话管理、消息历史、流式对话、图片处理。

图片策略：
  - 本地上传：落盘到 uploads/chat/，同时转 Base64 发给 VL 模型，刷新后仍可显示
  - 公网链接：仅 https://，拦截内网/本机
  - 错题本追问：沿用 uploads/ 磁盘路径（转 Base64）
"""

import json
import logging
import pathlib
from dataclasses import replace as dc_replace

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.schemas.chat import ChatSearchRequest, ChatSendRequest, ChatSessionCreate
from app.services.agent_mode_service import get_agent_mode_service
from app.services.chat_context import build_history_for_llm, strip_ocr_for_display
from app.services.chat_service import ChatService
from app.services.media_service import get_media_service
from app.utils.file_utils import ensure_dir, save_upload_image
from app.utils.image_url import ImageProcessingError, ResolvedImage, resolve_chat_image
from app.utils.response import error_response, success_response

router = APIRouter(prefix="/api/chat", tags=["AI聊天"])
settings = get_settings()
logger = logging.getLogger(__name__)


def _get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    return ChatService(db)


async def _read_audio_file(
    audio_file: UploadFile | None,
) -> tuple[bytes | None, str | None]:
    if not audio_file:
        return None, None
    filename = audio_file.filename or "recording.wav"
    try:
        content = await audio_file.read()
    except Exception as exc:
        raise ImageProcessingError("读取语音失败，请重试。", log_detail=str(exc)) from exc
    if not content:
        return None, None
    logger.info(
        "[Router] 收到语音: filename=%s bytes=%d head=%s",
        filename,
        len(content),
        content[:4].hex(),
    )
    if len(content) > settings.max_audio_upload_bytes:
        raise ImageProcessingError(
            f"语音文件过大（上限 {settings.max_audio_upload_bytes // 1024 // 1024}MB）"
        )
    return content, filename


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
            "display_content": (
                strip_ocr_for_display(m.content or "")
                if m.role == "user"
                else (m.content or "")
            ),
            "image_path": m.image_path,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]
    return success_response(data)


@router.post("/transcribe")
async def transcribe_audio_only(
    audio_file: UploadFile = File(...),
):
    """
    仅语音识别：将录音转为文字，供前端展示在输入框供用户校对、编辑。
    不创建会话、不调用大模型。
    """
    try:
        audio_bytes, filename = await _read_audio_file(audio_file)
        if not audio_bytes:
            return error_response("语音文件为空")
        text = await get_media_service().transcribe_audio(
            audio_bytes,
            filename or "recording.wav",
        )
        return success_response({"text": text})
    except ImageProcessingError as exc:
        logger.warning("[Router] transcribe 失败: %s", exc.user_message)
        return error_response(exc.user_message)


@router.post("/send/stream")
async def send_message_stream(
    session_id: str = Form(...),
    content: str = Form(default=""),
    image_file: UploadFile | None = File(default=None),
    audio_file: UploadFile | None = File(default=None),
    image_url: str | None = Form(default=None),
    image_path: str | None = Form(default=None),
    enable_tts: bool = Form(default=False),
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
        return JSONResponse(
            status_code=404,
            content=error_response("会话不存在，请新建对话后重试"),
        )

    audio_bytes: bytes | None = None
    audio_filename: str | None = None
    image_bytes: bytes | None = None
    image_filename: str | None = None
    resolved: ResolvedImage | None = None

    try:
        audio_bytes, audio_filename = await _read_audio_file(audio_file)
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

        resolved = await resolve_chat_image(
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

    if not content.strip() and not resolved and not audio_bytes:
        return error_response("请输入文字、上传图片或语音")

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
            audio_bytes=audio_bytes,
            audio_filename=audio_filename or "audio.wav",
            image_bytes=image_bytes,
            image_disk_path=saved_image_path,
            enable_tts=enable_tts or settings.enable_tts_default,
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


# ── Agent 模式 ────────────────────────────────────────────

AGENT_FILES_MARKER = "__AGENT_FILES__"


@router.post("/agent/stream")
async def agent_stream(
    session_id: str = Form(...),
    content: str = Form(default=""),
    file: UploadFile | None = File(default=None),
    resume_task_id: str = Form(default=""),
    service: ChatService = Depends(_get_chat_service),
):
    """
    Agent 模式流式回复 — 任务执行型 AI，可调用工具（导出文件、知识检索）。

    支持文件上传：用户可上传 docx/pdf/txt 等文档，Agent 会先读取文件内容再生成。
    支持断点续跑：传入 resume_task_id 从上次中断处恢复。

    SSE 事件格式：
      data: {"type":"thinking","round":1}
      data: {"type":"step","tool":"...","args":{},"status":"running"|"done"}
      data: {"type":"token","token":"..."}
      data: {"type":"file","file":{"filename":"...","file_url":"..."}}
      data: {"type":"done"}
      data: {"type":"resumed","task_id":"..."}  (断点续跑成功)
    """
    session = service.get_session(session_id)
    if not session:
        return JSONResponse(
            status_code=404,
            content=error_response("会话不存在，请新建对话后重试"),
        )

    if not content.strip() and not file:
        return error_response("请输入任务描述或上传文件")

    # 保存上传文件到 uploads/chat/
    saved_file_name: str | None = None
    if file:
        try:
            file_bytes = await file.read()
        except Exception as exc:
            return error_response(f"读取文件失败: {exc}")
        if file_bytes:
            chat_upload_dir = settings.upload_path.parent / "chat"
            ensure_dir(chat_upload_dir)
            import uuid as _uuid
            safe_name = pathlib.Path(file.filename or "upload.docx").name
            stem = pathlib.Path(safe_name).stem
            ext = pathlib.Path(safe_name).suffix
            file_id = _uuid.uuid4().hex[:8]
            saved_file_name = f"{stem}_{file_id}{ext}"
            saved_path = chat_upload_dir / saved_file_name
            saved_path.write_bytes(file_bytes)
            logger.info("[Agent] 文件已保存: %s", saved_file_name)

    # 保存用户消息
    service.save_message(session_id, "user", content)

    # 构建多轮历史
    prior_messages = service.get_messages(session_id)
    history = build_history_for_llm(prior_messages)
    # 移除最后一条（刚保存的用户消息），因为 stream_agent_reply 会自己加
    if history and history[-1]["role"] == "user":
        history = history[:-1]

    # 更新会话标题（首次）
    if session.title == "新对话" and content:
        title_src = content.split("\n", 1)[0].strip()
        session.title = title_src[:50] + ("..." if len(title_src) > 50 else "")
        service.db.commit()

    agent_service = get_agent_mode_service()

    async def event_generator():
        full_response: list[str] = []
        files_info: list[dict] = []
        try:
            async for chunk in agent_service.stream_agent_reply(
                content, history, file_name=saved_file_name, session_id=session_id,
                resume_task_id=resume_task_id,
            ):
                if not chunk.startswith("data: "):
                    continue
                payload = chunk[6:].strip()
                if not payload:
                    continue
                try:
                    evt = json.loads(payload)
                except json.JSONDecodeError:
                    continue

                # 转发给前端
                yield chunk

                # 收集结果（error 事件不重复 yield）
                if evt.get("type") == "token":
                    full_response.append(evt.get("token", ""))
                elif evt.get("type") == "file":
                    file_data = evt.get("file", {})
                    files_info.append(file_data)
                elif evt.get("type") == "error":
                    return
        except Exception as exc:
            logger.error("Agent stream 失败: %s", exc)
            yield f'data: {json.dumps({"error": str(exc)}, ensure_ascii=False)}\n\n'
            return

        # 保存助手消息（文件信息编码在内容末尾）
        assistant_text = "".join(full_response)
        if files_info:
            assistant_text += f"\n\n{AGENT_FILES_MARKER}{json.dumps(files_info, ensure_ascii=False)}"
        service.save_message(session_id, "assistant", assistant_text)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/files/{filename}")
async def download_chat_file(filename: str):
    """下载 Agent 生成的文件（uploads/chat/ 目录）。"""
    # 安全检查：禁止路径穿越
    safe_name = pathlib.Path(filename).name
    if safe_name != filename:
        return error_response("非法文件名")

    file_path = settings.upload_path.parent / "chat" / safe_name
    if not file_path.is_file():
        return error_response("文件不存在")

    return FileResponse(
        path=str(file_path),
        filename=safe_name,
        media_type="application/octet-stream",
    )


# ── Agent 任务日志 ─────────────────────────────────────────

@router.get("/agent/tasks")
async def list_agent_tasks(
    limit: int = Query(default=20, description="返回任务数量"),
):
    """获取最近的 Agent 任务列表（全链路审计）。"""
    from app.services.agent_task_logger import get_task_logger
    logger = get_task_logger()
    tasks = logger.get_recent_tasks(limit=limit)
    return success_response(tasks)


@router.get("/agent/tasks/{task_id}")
async def get_agent_task_detail(task_id: str):
    """获取 Agent 任务执行详情（含每步工具调用记录）。"""
    from app.services.agent_task_logger import get_task_logger
    logger = get_task_logger()
    detail = logger.get_task_detail(task_id)
    if detail is None:
        return error_response("任务不存在")
    return success_response(detail)


@router.get("/agent/stats")
async def agent_stats():
    """获取 Agent 系统统计（商业级监控面板）。"""
    from app.services.agent_mode_service import get_agent_mode_service
    service = get_agent_mode_service()
    stats = service.get_system_stats()
    return success_response(stats)
