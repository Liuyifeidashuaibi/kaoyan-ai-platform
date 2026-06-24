"""Request/response schemas for the HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TextTranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="English text to translate")
    mode: str = Field(default="full", description="full or bilingual")
    domain: str | None = Field(default=None, description="textbook, paper, or technical")
    export_format: str | None = Field(
        default=None, description="Optional export: txt or markdown"
    )


class ExportTextRequest(BaseModel):
    mode: str
    full_text: str | None = None
    pairs: list[dict[str, str]] = Field(default_factory=list)
    source_name: str = ""
    kind: str = "text"
    ocr_text: str | None = None
    export_format: str = "markdown"


class ExportSubtitlesRequest(BaseModel):
    source_name: str
    detected_language: str | None = None
    mode: str = "bilingual"
    cues: list[dict] = Field(default_factory=list)
    export_format: str = "srt"
    subtitle_mode: str | None = None
