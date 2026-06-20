"""英文纠错 + 增强翻译 Facade Schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorItem(BaseModel):
    word: str
    correction: str
    start: int
    end: int


class EnLearnTextRequest(BaseModel):
    text: str = Field(..., min_length=1)
    mode: str = Field(default="bilingual")


class SentencePairOut(BaseModel):
    source: str
    target: str


class EnLearnTranslateResult(BaseModel):
    original_text: str
    corrected_text: str
    error_list: list[ErrorItem]
    mode: str
    pairs: list[SentencePairOut] = Field(default_factory=list)
    full_text: str | None = None
    chinese_text: str | None = None
