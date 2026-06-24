from __future__ import annotations

from pathlib import Path

from translator.core.document_translator import DocumentTranslator
from translator.core.exceptions import ModelNotFoundError
from translator.core.image_translator import ImageTranslator
from translator.core.text_translator import TextTranslator
from translator.core.types import (
    Document,
    ExportFormat,
    ImageTranslationResult,
    SubtitleFormat,
    SubtitleOutputMode,
    TranslationDomain,
    TranslationMode,
    TranslationResult,
    VideoTranslationResult,
)
from translator.core.video_translator import VideoTranslator
from translator.exporters import export_result
from translator.models.base import ModelProvider
from translator.models.ollama.model_check import validate_model_config
from translator.models.registry import create_provider
from translator.services.subtitle.formatter import export_subtitles
from translator.utils.config import AppConfig, Settings, load_config


class TranslatorEngine:
    """Unified local AI translation engine entry point."""

    def __init__(self, provider: ModelProvider, config: AppConfig) -> None:
        self._provider = provider
        self._config = config
        self._text = TextTranslator(provider, config)
        self._image = ImageTranslator(provider, config, self._text)
        self._document = DocumentTranslator(self._text, self._image, config)
        self._video = VideoTranslator(provider, config, self._text)

    @classmethod
    def from_config(cls, config_path: Path | None = None) -> "TranslatorEngine":
        config = load_config(config_path)
        config = Settings().apply_to(config)
        validate_model_config(config.model)
        provider = create_provider(config.model)
        if not provider.is_available():
            raise ModelNotFoundError(
                f"Model provider unavailable at {config.model.base_url}. "
                f"Ensure Ollama is running and '{config.model.name}' is available."
            )
        return cls(provider, config)

    @property
    def config(self) -> AppConfig:
        return self._config

    def warmup(self) -> None:
        warmup_fn = getattr(self._provider, "warmup", None)
        if callable(warmup_fn):
            warmup_fn()

    def text_translate(
        self,
        text: str,
        mode: TranslationMode = TranslationMode.FULL,
        domain: TranslationDomain | None = None,
    ) -> TranslationResult:
        domain = self._resolve_domain(domain)
        return self._text.translate(text, mode=mode, domain=domain)

    def translate_image(
        self,
        image_path: Path | str,
        mode: TranslationMode = TranslationMode.FULL,
        domain: TranslationDomain | None = None,
    ) -> ImageTranslationResult:
        domain = self._resolve_domain(domain)
        return self._image.translate(Path(image_path), mode=mode, domain=domain)

    def translate_file(
        self,
        file_path: Path | str,
        mode: TranslationMode = TranslationMode.FULL,
        domain: TranslationDomain | None = None,
    ) -> TranslationResult | ImageTranslationResult:
        path = Path(file_path)
        suffix = path.suffix.lower()
        domain = self._resolve_domain(domain)

        if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
            return self.translate_image(path, mode=mode, domain=domain)
        if suffix in {".mp4", ".mkv", ".mov"}:
            raise ValueError(
                "Video files require translate_video(). Use the video command or API."
            )
        return self._document.translate(path, mode=mode, domain=domain)

    def translate_video(
        self,
        video_path: Path | str,
        domain: TranslationDomain | None = None,
        output_mode: SubtitleOutputMode = SubtitleOutputMode.BILINGUAL,
    ) -> VideoTranslationResult:
        domain = self._resolve_domain(domain)
        return self._video.translate(
            Path(video_path), domain=domain, output_mode=output_mode
        )

    def translate_document(
        self,
        document: Document,
        mode: TranslationMode,
        domain: TranslationDomain | None = None,
    ) -> TranslationResult | ImageTranslationResult:
        """Route a processed Document through the appropriate translator."""
        domain = self._resolve_domain(domain)

        if document.kind.value == "video" or document.video_path:
            raise ValueError("Use translate_video() for video inputs.")
        if document.needs_vision and document.image_path:
            return self._image.translate(
                document.image_path,
                mode=mode,
                domain=domain,
                source_name=document.source_name,
            )
        if not document.text or not document.text.strip():
            raise ValueError("Document has no text to translate")
        return self._text.translate(
            document.text,
            mode=mode,
            domain=domain,
            source_name=document.source_name,
        )

    def translate_and_export(
        self,
        document: Document,
        mode: TranslationMode,
        export_format: ExportFormat,
        output_path: Path | None = None,
        domain: TranslationDomain | None = None,
    ) -> tuple[TranslationResult | ImageTranslationResult, str]:
        result = self.translate_document(document, mode=mode, domain=domain)
        content = export_result(result, export_format)
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
        return result, content

    def export_video_subtitles(
        self,
        result: VideoTranslationResult,
        fmt: SubtitleFormat,
        output_path: Path | None = None,
        output_mode: SubtitleOutputMode | None = None,
    ) -> str:
        mode = output_mode or result.mode
        content = export_subtitles(result.cues, fmt=fmt, mode=mode)
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
        return content

    def _resolve_domain(self, domain: TranslationDomain | None) -> TranslationDomain:
        if domain is not None:
            return domain
        return TranslationDomain(self._config.translation.default_domain)


class TranslationEngine(TranslatorEngine):
    """Backward-compatible alias for the unified engine."""

    def __init__(self, provider: ModelProvider, config: AppConfig) -> None:
        super().__init__(provider, config)
