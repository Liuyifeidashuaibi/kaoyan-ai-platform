"""错题本相关 Schema。"""

from datetime import datetime

from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    """创建科目分类。"""

    name: str = Field(..., min_length=1, max_length=100)


class CategoryOut(BaseModel):
    """分类输出。"""

    id: int
    name: str
    created_at: datetime
    question_count: int = 0

    model_config = {"from_attributes": True}


class WrongQuestionOut(BaseModel):
    """错题条目输出。"""

    id: int
    category_id: int
    category_name: str
    title: str
    image_path: str
    notes: str
    ai_analysis: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WrongQuestionUpdate(BaseModel):
    """更新错题笔记 / 标题。"""

    title: str | None = None
    notes: str | None = None
    category_id: int | None = None


class WrongQuestionAnalyzeRequest(BaseModel):
    """请求 AI 解析错题。"""

    question_id: int
