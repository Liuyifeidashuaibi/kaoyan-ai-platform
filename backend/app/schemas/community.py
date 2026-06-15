"""社区模块 Pydantic 模型。"""

from typing import Literal

from pydantic import BaseModel, Field

PostType = Literal["experience", "material"]

SUBJECT_CATEGORIES = [
    "哲学", "经济学", "法学", "教育学", "文学",
    "历史学", "理学", "工学", "农学", "医学",
    "军事学", "管理学", "艺术学",
]

COHORT_GRADES = ["23级", "24级", "25级", "26级"]

POST_TYPE_LABELS = {
    "experience": "经验帖",
    "material": "资料帖",
}


class AttachmentItem(BaseModel):
    url: str
    name: str = ""
    mime_type: str = ""


class PostCreate(BaseModel):
    post_type: PostType
    subject_category: str
    grade: str = Field(min_length=2, max_length=10)
    university_id: str | None = None
    university_name: str | None = Field(default=None, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=50000)
    attachments: list[AttachmentItem] = Field(default_factory=list)


class PostUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, max_length=50000)
    is_hidden: bool | None = None


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    parent_id: str | None = None


class UserProfileUpdate(BaseModel):
    subject_category: str | None = None
    avatar_url: str | None = None


class SearchResult(BaseModel):
    kind: Literal["user", "subject", "posts"]
    user_id: str | None = None
    display_id: str | None = None
    subject_category: str | None = None
    posts: list | None = None
