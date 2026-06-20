"""单词查询 API Schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class WordQueryRequest(BaseModel):
    word: str = Field(..., min_length=1, max_length=64)
    mode: str = Field(default="hover", description="hover | detail")


class WordBrief(BaseModel):
    word: str
    phonetic: str | None = None
    pos: str | None = None
    gloss: str
    source: str = Field(description="local | ai_cache | ai")


class WordDetail(BaseModel):
    word: str
    phonetic: str | None = None
    pos: str | None = None
    translation: str | None = None
    definition: str | None = None
    tag: str | None = None
    collins: int | None = None
    oxford: int | None = None
    exchange: str | None = None
    detail: str | None = None
    kaoyan_gloss: str | None = None
    kaoyan_phrases: list[str] = Field(default_factory=list)
    source: str
