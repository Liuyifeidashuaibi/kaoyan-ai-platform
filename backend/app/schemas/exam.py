"""
试卷解析相关请求/响应模型。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExamUploadResponse(BaseModel):
    """试卷上传响应。"""
    paper_id: int
    task_id: str | None = None
    status: str = "pending"
    message: str = "试卷已提交，正在解析"


class ExamPaperResponse(BaseModel):
    """试卷详情响应。"""
    id: int
    session_id: str | None = None
    subject: str
    title: str
    status: str
    ocr_text: str | None = None
    parsed_structure: dict | None = None
    analysis_result: dict | None = None
    created_at: str
    expires_at: str | None = None


class ExamQuestionResponse(BaseModel):
    """试卷题目列表响应。"""
    paper_id: int
    subject: str
    total_questions: int
    sections: list[dict] = Field(default_factory=list)


class ExamQuestionAskRequest(BaseModel):
    """单题追问请求。"""
    question: str = Field(..., description="追问内容")
    session_id: str | None = Field(default=None, description="聊天会话 ID")


class ExamFavoriteRequest(BaseModel):
    """收藏题目请求。"""
    question_ids: list[str] = Field(..., description="要收藏的题目 ID 列表")
    subject: str = Field(default="", description="科目")


class ExamVocabularyExport(BaseModel):
    """英语生词导出响应。"""
    paper_id: int
    vocabulary: list[dict] = Field(default_factory=list)
    total_words: int = 0


class ExamSessionCleanupResponse(BaseModel):
    """会话清理响应。"""
    session_id: str
    deleted_papers: int = 0
    deleted_vectors: int = 0
    message: str = "清理完成"
