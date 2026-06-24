from __future__ import annotations

from pathlib import Path

from translator.core.bilingual_translator import translate_bilingual_text
from translator.core.text_translator import TextTranslator
from translator.core.types import (
    ImageTranslationResult,
    TranslationDomain,
    TranslationMode,
    TranslationResult,
)
from translator.models.base import ModelProvider
from translator.models.ollama.provider import OllamaProvider
from translator.prompts import full as full_prompts
from translator.prompts.ocr import OCR_SYSTEM_PROMPT, OCR_USER_PROMPT
from translator.utils.config import AppConfig
from translator.utils.image_prep import prepare_image_for_vision


class ImageTranslator:
    """Full: VL single-pass. Bilingual: fast OCR (VL) + draft sentence translation."""

    def __init__(
        self,
        provider: ModelProvider,
        config: AppConfig,
        text_translator: TextTranslator | None = None,
    ) -> None:
        self._provider = provider
        self._config = config
        self._text_translator = text_translator or TextTranslator(provider, config)

    def extract_ocr(self, image_path: Path, source_name: str | None = None) -> str:
        return self._extract_ocr(image_path)

    def translate(
        self,
        image_path: Path,
        mode: TranslationMode,
        domain: TranslationDomain,
        source_name: str | None = None,
    ) -> ImageTranslationResult:
        image_path = image_path.resolve()
        name = source_name or image_path.name
        target = self._config.translation.target_language
        cfg = self._config.translation

        if mode == TranslationMode.FULL and cfg.image_single_pass_full:
            return self._translate_full_single_pass(image_path, domain, target, name)

        if mode == TranslationMode.BILINGUAL:
            return self._translate_bilingual_fast(image_path, domain, target, name)

        ocr_text = self._extract_ocr(image_path)
        text_result = self._text_translator.translate(
            ocr_text,
            mode=mode,
            domain=domain,
            source_name=name,
        )
        return self._to_image_result(text_result, ocr_text)

    def _translate_bilingual_fast(
        self,
        image_path: Path,
        domain: TranslationDomain,
        target: str,
        name: str,
    ) -> ImageTranslationResult:
        ocr_text = self._extract_ocr(image_path)
        pairs = translate_bilingual_text(
            self._provider, self._config, ocr_text, domain, target
        )
        return ImageTranslationResult(
            mode=TranslationMode.BILINGUAL,
            pairs=pairs,
            source_name=name,
            ocr_text=ocr_text,
        )

    def _translate_full_single_pass(
        self,
        image_path: Path,
        domain: TranslationDomain,
        target: str,
        name: str,
    ) -> ImageTranslationResult:
        prepared, cleanup = self._prepare_image(
            image_path, self._config.translation.image_max_dimension
        )
        try:
            system = full_prompts.build_full_image_system_prompt(domain, target)
            user = full_prompts.build_full_image_user_prompt()
            translated = self._provider.translate_with_image(prepared, system, user)
            return ImageTranslationResult(
                mode=TranslationMode.FULL,
                full_text=translated,
                ocr_text=None,
                source_name=name,
            )
        finally:
            self._cleanup(prepared, cleanup)

    def _extract_ocr(self, image_path: Path) -> str:
        tcfg = self._config.translation
        prepared, cleanup = prepare_image_for_vision(
            image_path,
            tcfg.image_ocr_max_dimension,
            jpeg_quality=tcfg.image_jpeg_quality,
        )
        try:
            kwargs = {"ocr": True} if isinstance(self._provider, OllamaProvider) else {}
            return self._provider.translate_with_image(
                prepared, OCR_SYSTEM_PROMPT, OCR_USER_PROMPT, **kwargs
            )
        finally:
            self._cleanup(prepared, cleanup)

    def _prepare_image(self, image_path: Path, max_dim: int) -> tuple[Path, bool]:
        tcfg = self._config.translation
        return prepare_image_for_vision(
            image_path, max_dim, jpeg_quality=tcfg.image_jpeg_quality
        )

    @staticmethod
    def _cleanup(path: Path, is_temp: bool) -> None:
        if is_temp and path.exists():
            path.unlink(missing_ok=True)

    @staticmethod
    def _to_image_result(
        result: TranslationResult, ocr_text: str
    ) -> ImageTranslationResult:
        return ImageTranslationResult(
            mode=result.mode,
            full_text=result.full_text,
            pairs=result.pairs,
            source_name=result.source_name,
            ocr_text=ocr_text,
        )
