"""
增强翻译 Facade — 复用 TranslatorService + 英文纠错，不修改 translator 核心逻辑。
"""

from __future__ import annotations

import logging

from app.infrastructure.cache.translator_cache import get_cached_translator_facade
from app.modules.en_learn.correction_service import align_errors_to_original, correct_english
from app.modules.en_learn.schemas import EnLearnTranslateResult, ErrorItem, SentencePairOut
from app.services.translator_service import TranslatorServiceError

logger = logging.getLogger(__name__)


class EnLearnFacade:
    def __init__(self) -> None:
        self._translator = get_cached_translator_facade()

    async def translate_text(self, text: str, *, mode: str = "bilingual") -> EnLearnTranslateResult:
        original = text.strip()
        corrected, errors = await correct_english(original)
        errors = align_errors_to_original(original, corrected, errors)

        try:
            data = await self._translator.translate_text(corrected, mode=mode)
        except TranslatorServiceError as exc:
            raise exc

        pairs_raw = data.get("pairs") or []
        pairs = [
            SentencePairOut(source=p.get("source", ""), target=p.get("target", ""))
            for p in pairs_raw
            if p.get("source") or p.get("target")
        ]
        chinese = data.get("full_text") or ""
        if not chinese and pairs:
            chinese = "\n\n".join(p.target for p in pairs if p.target)

        return EnLearnTranslateResult(
            original_text=original,
            corrected_text=corrected,
            error_list=errors,
            mode=mode,
            pairs=pairs,
            full_text=data.get("full_text"),
            chinese_text=chinese or None,
        )


    async def translate_image_enhanced(
        self, file_bytes: bytes, filename: str, *, mode: str = "bilingual", content_type: str | None = None
    ) -> dict:
        data = await self._translator.translate_image(
            file_bytes, filename, mode=mode, content_type=content_type
        )
        ocr_text = (data.get("ocr_text") or "").strip()
        image_full_text = (data.get("full_text") or "").strip()
        # Full single-pass image translation returns Chinese in full_text but no ocr_text.
        single_pass_full = mode == "full" and not ocr_text and bool(image_full_text)

        if not ocr_text:
            if single_pass_full:
                ocr_data = await self._translator.translate_image(
                    file_bytes,
                    filename,
                    mode="bilingual",
                    content_type=content_type,
                )
                ocr_text = (ocr_data.get("ocr_text") or "").strip()
            if not ocr_text:
                raise TranslatorServiceError("未能识别图片英文内容")

        if single_pass_full:
            original = ocr_text
            corrected, errors = await correct_english(original)
            errors = align_errors_to_original(original, corrected, errors)
            enhanced = EnLearnTranslateResult(
                original_text=original,
                corrected_text=corrected,
                error_list=errors,
                mode=mode,
                pairs=[],
                full_text=image_full_text,
                chinese_text=image_full_text,
            )
        else:
            enhanced = await self.translate_text(ocr_text, mode=mode)

        payload = enhanced.model_dump()
        payload["ocr_text"] = ocr_text
        payload["kind"] = "image"
        return payload


_facade: EnLearnFacade | None = None


def get_en_learn_facade() -> EnLearnFacade:
    global _facade
    if _facade is None:
        _facade = EnLearnFacade()
    return _facade
