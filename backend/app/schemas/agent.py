"""Agent 模板管理 Schema。"""

from pydantic import BaseModel, Field


class TemplateCreate(BaseModel):
    """创建模板请求。"""

    name: str = Field(..., min_length=1, max_length=200, description="模板名称")
    category: str = Field(default="general", max_length=100, description="分类（论文/报告/标书/报表…）")
    doc_type: str = Field(default="pdf", max_length=50, description="文档类型 pdf/docx/xlsx/pptx")
    description: str = Field(default="", description="模板描述")
    style_rules: dict = Field(default_factory=dict, description="样式规则（字体/字号/行距/标题层级）")
    cover_format: dict = Field(default_factory=dict, description="封面格式（字段与排版）")
    validation_rules: dict = Field(default_factory=dict, description="校验规则（必含章节/字数/结构）")
    source_text: str = Field(default="", description="模板原文（向量化用纯文本）")


class TemplateUpdate(BaseModel):
    """更新模板请求。"""

    name: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    doc_type: str | None = Field(default=None, max_length=50)
    description: str | None = None
    style_rules: dict | None = None
    cover_format: dict | None = None
    validation_rules: dict | None = None
    source_text: str | None = None
    is_active: bool | None = None


class TemplateMatchRequest(BaseModel):
    """模板语义匹配请求。"""

    doc_type: str = Field(..., description="文档类型 pdf/docx/xlsx/pptx")
    query: str = Field(..., min_length=1, description="检索关键词")


class TemplateValidateRequest(BaseModel):
    """格式校验请求。"""

    content: str = Field(..., min_length=1, description="待校验的文档内容")
    template_id: int = Field(..., description="模板ID")
