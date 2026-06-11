"""聊天相关 Schema。"""

from datetime import datetime

from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    """创建新会话请求。"""

    title: str = Field(default="新对话", max_length=200)


class ChatSessionOut(BaseModel):
    """会话列表项。"""

    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageOut(BaseModel):
    """单条消息输出。"""

    id: int
    role: str
    content: str
    image_path: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSendRequest(BaseModel):
    """发送消息（非流式备用）。"""

    session_id: str
    content: str = Field(..., min_length=1)
    image_path: str | None = None  # 已上传图片的相对路径


class ChatSearchRequest(BaseModel):
    """搜索历史会话。"""

    keyword: str = Field(default="", max_length=100)
