"""
聊天业务服务 — 会话管理、消息持久化、流式对话编排。
"""

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import ChatMessage, ChatSession
from app.services.agent_service import run_agent_stream
from app.config import get_settings
from app.utils.file_utils import ensure_dir, save_upload_image


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
        # 更新会话时间；首条用户消息可自动更新标题
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
        image_path: str | None = None,
        *,
        skip_user_save: bool = False,
    ):
        """
        保存用户消息 → 调用 Agent 流式生成 → 保存助手回复。

        这是一个 async generator，yield SSE 格式数据块。
        """
        session = self.get_session(session_id)
        if not session:
            yield 'data: {"error": "会话不存在"}\n\n'
            return

        if not skip_user_save:
            self.save_message(session_id, "user", user_content, image_path)

        history = self.build_history_for_llm(session_id)
        # 当前轮 user 已在历史中（含 skip_user_save 场景），Agent 会自行 append
        if history and history[-1]["role"] == "user":
            history = history[:-1]

        full_response: list[str] = []
        async for token in run_agent_stream(user_content, history, image_path):
            full_response.append(token)
            # SSE 格式：data: <json>\n\n
            import json

            yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

        assistant_text = "".join(full_response)
        self.save_message(session_id, "assistant", assistant_text)
        yield 'data: {"done": true}\n\n'

    def save_chat_image(self, content: bytes, filename: str, upload_dir) -> str:
        """保存聊天中上传的图片，返回相对路径。"""
        ensure_dir(upload_dir)
        return save_upload_image(
            content, upload_dir, filename, project_root=get_settings().root
        )
