from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class TranslationMode(str, Enum):
    FULL = "full"
    BILINGUAL = "bilingual"


class TranslationDomain(str, Enum):
    TEXTBOOK = "textbook"
    PAPER = "paper"
    TECHNICAL = "technical"


class ExportFormat(str, Enum):
    TXT = "txt"
    MARKDOWN = "markdown"


class SubtitleFormat(str, Enum):
    SRT = "srt"
    VTT = "vtt"
    TXT = "txt"


class SubtitleOutputMode(str, Enum):
    ORIGINAL = "original"
    TRANSLATED = "translated"
    BILINGUAL = "bilingual"


class InputKind(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    VIDEO = "video"


class Document(BaseModel):
    """Unified input document after processing."""

    text: str | None = None
    image_path: Path | None = None
    video_path: Path | None = None
    source_name: str = ""
    needs_vision: bool = False
    kind: InputKind = InputKind.TEXT

    model_config = {"arbitrary_types_allowed": True}


class SentencePair(BaseModel):
    source: str
    target: str


class TranslationResult(BaseModel):
    mode: TranslationMode
    full_text: str | None = None
    pairs: list[SentencePair] = Field(default_factory=list)
    source_name: str = ""
    kind: InputKind = InputKind.TEXT

    @property
    def is_bilingual(self) -> bool:
        return self.mode == TranslationMode.BILINGUAL


class ImageTranslationResult(TranslationResult):
    ocr_text: str | None = None
    kind: InputKind = InputKind.IMAGE


class SubtitleCue(BaseModel):
    index: int
    start: float
    end: float
    text: str
    translation: str | None = None


class VideoTranslationResult(BaseModel):
    source_name: str
    cues: list[SubtitleCue] = Field(default_factory=list)
    detected_language: str | None = None
    mode: SubtitleOutputMode = SubtitleOutputMode.BILINGUAL
