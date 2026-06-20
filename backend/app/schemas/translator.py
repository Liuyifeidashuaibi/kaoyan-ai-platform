"""Pydantic schemas for the translator business module."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TextTranslateRequest(BaseModel):
    text: str = Field(..., min_length=1)
    mode: str = Field(default="full")
    domain: str | None = None
    export_format: str | None = None


class SaveToNotebookRequest(BaseModel):
    question_id: int
    content: str = Field(..., min_length=1)
    append: bool = Field(default=True, description="Append to existing notes if true")


class TranslateFromNotebookRequest(BaseModel):
    question_id: int
    mode: str = Field(default="full")
    domain: str | None = None
    export_format: str | None = None
    subtitle_mode: str | None = Field(
        default=None, description="For video materials: original, translated, bilingual"
    )
