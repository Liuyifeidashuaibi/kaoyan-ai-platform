"""
聊天业务服务 — 会话管理、消息持久化、流式对话编排。
"""

import json
import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import ChatMessage, ChatSession
from app.services.agent_service import run_agent_stream
from app.services.chat_context import build_history_for_llm, prepare_user_turn
from app.services.media_service import get_media_service
from app.utils.image_url import ResolvedImage

logger = logging.getLogger(__name__)


class ChatService:
    """聊天相关业务逻辑。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_session(self, title: str = "新对话") -> ChatSession:
        session = ChatSession(
            id=str(uuid.uuid4()),
            title=title,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def list_sessions(self, keyword: str = "") -> list[ChatSession]:
        q = self.db.query(ChatSession).order_by(ChatSession.updated_at.desc())
        if keyword.strip():
            q = q.filter(ChatSession.title.contains(keyword.strip()))
        return q.all()

    def get_session(self, session_id: str) -> ChatSession | None:
        return self.db.query(ChatSession).filter(ChatSession.id == session_id).first()

    def delete_session(self, session_id: str) -> bool:
        session = self.get_session(session_id)
        if not session:
            return False
        self.db.delete(session)
        self.db.commit()
        return True

    def get_messages(self, session_id: str) -> list[ChatMessage]:
        return (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        image_path: str | None = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            image_path=image_path,
            created_at=datetime.utcnow(),
        )
        self.db.add(msg)
        session = self.get_session(session_id)
        if session:
            session.updated_at = datetime.utcnow()
            if role == "user" and session.title == "新对话" and content:
                title_src = content.split("\n", 1)[0].strip()
                session.title = title_src[:50] + ("..." if len(title_src) > 50 else "")
        self.db.commit()
        self.db.refresh(msg)
        return msg

    async def stream_reply(
        self,
        session_id: str,
        user_content: str,
        image: ResolvedImage | None = None,
        *,
        skip_user_save: bool = False,
        audio_bytes: bytes | None = None,
        audio_filename: str = "audio.wav",
        image_bytes: bytes | None = None,
        image_disk_path: str | None = None,
        enable_tts: bool = False,
    ):
        session = self.get_session(session_id)
        if not session:
            yield 'data: {"error": "会话不存在"}\n\n'
            return

        storage_ref = image_disk_path or (image.storage_ref if image else None)
        prior_messages = self.get_messages(session_id)

        try:
            prepared = await prepare_user_turn(
                prior_messages,
                user_content,
                image,
                image_bytes,
                get_media_service(),
            )
        except Exception as exc:
            logger.error("准备对话上下文失败: %s", exc)
            yield f"data: {json.dumps({'error': '图片解析失败，请重新上传'}, ensure_ascii=False)}\n\n"
            return

        if not prepared.llm_query and not audio_bytes:
            yield f"data: {json.dumps({'error': '请输入内容或上传图片/语音'}, ensure_ascii=False)}\n\n"
            return

        if not skip_user_save:
            self.save_message(session_id, "user", prepared.db_content, storage_ref)
            prior_messages = self.get_messages(session_id)

        history = build_history_for_llm(prior_messages)
        if history and history[-1]["role"] == "user":
            history = history[:-1]

        full_response: list[str] = []
        tts_payload: str | None = None
        try:
            async for token in run_agent_stream(
                prepared.llm_query or user_content,
                history,
                image=None,
                audio_bytes=audio_bytes,
                audio_filename=audio_filename,
                image_bytes=None,
                enable_tts=enable_tts,
                use_history_cache=True,
            ):
                if "__META__" in token:
                    meta_part = token.split("__META__", 1)[-1]
                    try:
                        meta = json.loads(meta_part)
                        tts_payload = meta.get("tts_audio_base64")
                    except json.JSONDecodeError:
                        pass
                    token = token.split("__META__")[0]
                if token:
                    full_response.append(token)
                    yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.error("流式回复失败: %s", exc)
            yield f"data: {json.dumps({'error': '对话生成失败，请稍后重试'}, ensure_ascii=False)}\n\n"
            return

        assistant_text = "".join(full_response)
        self.save_message(session_id, "assistant", assistant_text)
        done_obj: dict = {"done": True}
        if tts_payload:
            done_obj["tts_audio_base64"] = tts_payload
        yield f"data: {json.dumps(done_obj, ensure_ascii=False)}\n\n"
