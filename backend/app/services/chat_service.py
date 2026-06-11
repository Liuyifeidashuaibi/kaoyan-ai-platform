"""
聊天业务服务 — 会话管理、消息持久化、流式对话编排。
"""

import json
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import ChatMessage, ChatSession
from app.services.agent_service import run_agent_stream
from app.utils.image_url import ResolvedImage, log_image_event


class ChatService:
    """聊天相关业务逻辑。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_session(self, title: str = "新对话") -> ChatSession:
        """创建新的聊天会话。"""
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
        """列出会话，支持标题关键词搜索。"""
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
        """持久化单条消息。"""
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
                session.title = content[:50] + ("..." if len(content) > 50 else "")
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def build_history_for_llm(self, session_id: str) -> list[dict]:
        """将数据库消息转为 OpenAI 格式历史。"""
        messages = self.get_messages(session_id)
        history: list[dict] = []
        for m in messages:
            if m.role in ("user", "assistant"):
                history.append({"role": m.role, "content": m.content})
        return history

    async def stream_reply(
        self,
        session_id: str,
        user_content: str,
        image: ResolvedImage | None = None,
        *,
        skip_user_save: bool = False,
    ):
        """
        保存用户消息 → 调用 Agent 流式生成 → 保存助手回复。
        yield SSE 格式数据块。
        """
        session = self.get_session(session_id)
        if not session:
            yield 'data: {"error": "会话不存在"}\n\n'
            return

        storage_ref = image.storage_ref if image else None
        if not skip_user_save:
            self.save_message(session_id, "user", user_content, storage_ref)

        history = self.build_history_for_llm(session_id)
        if history and history[-1]["role"] == "user":
            history = history[:-1]

        request_type = "vision" if image else "text"
        log_image_event(
            request_type=request_type,
            source=image.source_type if image else "none",
            model="-",
            status="stream_start",
            detail=f"session={session_id}",
        )

        full_response: list[str] = []
        try:
            async for token in run_agent_stream(user_content, history, image):
                full_response.append(token)
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger_msg = str(exc)
            log_image_event(
                request_type=request_type,
                source=image.source_type if image else "none",
                model="-",
                status="stream_error",
                detail=logger_msg,
            )
            yield f"data: {json.dumps({'error': '对话生成失败，请稍后重试'}, ensure_ascii=False)}\n\n"
            return

        assistant_text = "".join(full_response)
        self.save_message(session_id, "assistant", assistant_text)
        log_image_event(
            request_type=request_type,
            source=image.source_type if image else "none",
            model="-",
            status="stream_done",
        )
        yield 'data: {"done": true}\n\n'
