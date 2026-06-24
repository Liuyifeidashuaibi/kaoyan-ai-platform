"""Public API for external projects to call the Translator Engine."""

from __future__ import annotations

from pathlib import Path

from translator.core.engine import TranslatorEngine
from translator.core.exceptions import TranslatorError
from translator.core.types import (
    ExportFormat,
    ImageTranslationResult,
    SubtitleFormat,
    SubtitleOutputMode,
    TranslationDomain,
    TranslationMode,
    TranslationResult,
    VideoTranslationResult,
)
from translator.exporters import export_result
from translator.utils.config import load_config

__all__ = [
    "TranslatorAPI",
    "TranslatorError",
    "TranslationMode",
    "TranslationDomain",
    "TranslationResult",
    "ImageTranslationResult",
    "VideoTranslationResult",
    "SubtitleFormat",
    "SubtitleOutputMode",
    "ExportFormat",
]


class TranslatorAPI:
    """Stable facade for embedding the engine in other applications."""

    def __init__(self, engine: TranslatorEngine) -> None:
        self._engine = engine

    @classmethod
    def create(cls, config_path: Path | str | None = None) -> "TranslatorAPI":
        path = Path(config_path) if config_path else None
        return cls(TranslatorEngine.from_config(path))

    @property
    def engine(self) -> TranslatorEngine:
        return self._engine

    def translate_text(
        self,
        text: str,
        mode: TranslationMode = TranslationMode.FULL,
        domain: TranslationDomain | None = None,
    ) -> TranslationResult:
        return self._engine.text_translate(text, mode=mode, domain=domain)

    def translate_image(
        self,
        image_path: Path | str,
        mode: TranslationMode = TranslationMode.FULL,
        domain: TranslationDomain | None = None,
    ) -> ImageTranslationResult:
        return self._engine.translate_image(image_path, mode=mode, domain=domain)

    def translate_document(
        self,
        file_path: Path | str,
        mode: TranslationMode = TranslationMode.FULL,
        domain: TranslationDomain | None = None,
    ) -> TranslationResult | ImageTranslationResult:
        return self._engine.translate_file(file_path, mode=mode, domain=domain)

    def translate_video(
        self,
        video_path: Path | str,
        domain: TranslationDomain | None = None,
        subtitle_mode: SubtitleOutputMode = SubtitleOutputMode.BILINGUAL,
    ) -> VideoTranslationResult:
        return self._engine.translate_video(
            video_path, domain=domain, output_mode=subtitle_mode
        )

    def export_text(
        self,
        result: TranslationResult | ImageTranslationResult,
        fmt: ExportFormat = ExportFormat.MARKDOWN,
        output_path: Path | str | None = None,
    ) -> str:
        content = export_result(result, fmt)
        if output_path is not None:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return content

    def export_subtitles(
        self,
        result: VideoTranslationResult,
        fmt: SubtitleFormat = SubtitleFormat.SRT,
        output_path: Path | str | None = None,
        subtitle_mode: SubtitleOutputMode | None = None,
    ) -> str:
        return self._engine.export_video_subtitles(
            result,
            fmt=fmt,
            output_path=Path(output_path) if output_path else None,
            output_mode=subtitle_mode,
        )

    def health_check(self) -> dict[str, str]:
        config = self._engine.config
        return {
            "status": "ok",
            "model": config.model.name,
            "main_model": config.model.main_model,
            "draft_model": config.model.draft_model,
            "ollama_base_url": config.model.base_url,
            "whisper_model": config.whisper.model_size,
            "whisper_compute": config.whisper.compute_type,
        }

    def warmup_models(self) -> None:
        self._engine.warmup()
