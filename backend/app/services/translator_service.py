"""Local translator service — TranslatorAPI embedded directly, no HTTP call."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

# One GPU job at a time (mirrors the original translator server's run_exclusive)
_translate_sem = asyncio.Semaphore(1)

# Singleton — created on first request, never recreated
_api_instance: Any = None
_api_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Serialisers (same output format as translator/server/serializers.py)
# ---------------------------------------------------------------------------


def _serialize_text_result(result: Any) -> dict:
    from translator.core.types import ImageTranslationResult

    payload: dict = {
        "mode": result.mode.value,
        "full_text": result.full_text,
        "pairs": [{"source": p.source, "target": p.target} for p in result.pairs],
        "source_name": result.source_name,
        "kind": result.kind.value,
    }
    if isinstance(result, ImageTranslationResult):
        payload["ocr_text"] = result.ocr_text
    return payload


def _serialize_video_result(result: Any) -> dict:
    return {
        "source_name": result.source_name,
        "detected_language": result.detected_language,
        "mode": result.mode.value,
        "cues": [
            {
                "index": cue.index,
                "start": cue.start,
                "end": cue.end,
                "text": cue.text,
                "translation": cue.translation,
            }
            for cue in result.cues
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_mode(mode: str) -> Any:
    from translator.core.types import TranslationMode

    try:
        return TranslationMode(mode.lower())
    except ValueError:
        return TranslationMode.FULL


def _parse_domain(domain: str | None) -> Any:
    if not domain:
        return None
    from translator.core.types import TranslationDomain

    try:
        return TranslationDomain(domain.lower())
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class TranslatorServiceError(Exception):
    """Raised when local translation fails."""


# ---------------------------------------------------------------------------
# Lazy singleton
# ---------------------------------------------------------------------------


async def _get_api() -> Any:
    """Return the cached TranslatorAPI, initialising on first call."""
    global _api_instance
    if _api_instance is not None:
        return _api_instance
    async with _api_lock:
        if _api_instance is None:
            try:
                from translator.api import TranslatorAPI

                _api_instance = await asyncio.to_thread(TranslatorAPI.create)
                logger.info("TranslatorAPI initialised successfully")
            except Exception as exc:
                raise TranslatorServiceError(
                    f"翻译引擎初始化失败（Ollama 未运行或模型未拉取？）: {exc}"
                ) from exc
    return _api_instance


# ---------------------------------------------------------------------------
# Service — same public interface as the old HTTP proxy
# ---------------------------------------------------------------------------


class TranslatorService:
    """Embedded translation service — runs TranslatorEngine in a thread pool."""

    @property
    def is_configured(self) -> bool:
        # Always "configured"; actual availability depends on Ollama.
        return True

    async def health_check(self) -> dict[str, Any]:
        try:
            api = await _get_api()
            return await asyncio.to_thread(api.health_check)
        except TranslatorServiceError:
            raise
        except Exception as exc:
            raise TranslatorServiceError(str(exc)) from exc

    async def get_config(self) -> dict[str, Any]:
        api = await _get_api()
        cfg = api.engine.config
        return {
            "model": {
                "name": cfg.model.name,
                "main_model": cfg.model.main_model,
                "draft_model": cfg.model.draft_model,
                "base_url": cfg.model.base_url,
            },
            "whisper": {
                "model_size": cfg.whisper.model_size,
                "compute_type": cfg.whisper.compute_type,
                "device": cfg.whisper.device,
            },
            "translation": {
                "target_language": cfg.translation.target_language,
                "single_pass_word_limit": cfg.translation.single_pass_word_limit,
                "max_chunk_words": cfg.translation.max_chunk_words,
                "image_max_dimension": cfg.translation.image_max_dimension,
            },
        }

    async def translate_text(
        self,
        text: str,
        *,
        mode: str = "full",
        domain: str | None = None,
        export_format: str | None = None,
    ) -> dict[str, Any]:
        from translator.exporters import normalize_format

        t_mode = _parse_mode(mode)
        t_domain = _parse_domain(domain)

        api = await _get_api()
        async with _translate_sem:
            result = await asyncio.to_thread(api.translate_text, text, t_mode, t_domain)

        data = _serialize_text_result(result)
        if export_format:
            fmt = normalize_format(export_format)
            data["exported_content"] = await asyncio.to_thread(
                api.export_text, result, fmt
            )
            data["export_format"] = fmt.value
        return data

    async def translate_image(
        self,
        file_bytes: bytes,
        filename: str,
        *,
        mode: str = "full",
        domain: str | None = None,
        export_format: str | None = None,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        from translator.exporters import normalize_format

        t_mode = _parse_mode(mode)
        t_domain = _parse_domain(domain)
        suffix = Path(filename).suffix or ".png"

        api = await _get_api()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp_path = Path(tmp.name)
        try:
            async with _translate_sem:
                result = await asyncio.to_thread(
                    api.translate_image, tmp_path, t_mode, t_domain
                )
        finally:
            tmp_path.unlink(missing_ok=True)

        data = _serialize_text_result(result)
        if export_format:
            fmt = normalize_format(export_format)
            data["exported_content"] = await asyncio.to_thread(
                api.export_text, result, fmt
            )
            data["export_format"] = fmt.value
        return data

    async def translate_document(
        self,
        file_bytes: bytes,
        filename: str,
        *,
        mode: str = "full",
        domain: str | None = None,
        export_format: str | None = None,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        from translator.exporters import normalize_format

        t_mode = _parse_mode(mode)
        t_domain = _parse_domain(domain)
        suffix = Path(filename).suffix or ".pdf"

        api = await _get_api()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp_path = Path(tmp.name)
        try:
            async with _translate_sem:
                result = await asyncio.to_thread(
                    api.translate_document, tmp_path, t_mode, t_domain
                )
        finally:
            tmp_path.unlink(missing_ok=True)

        data = _serialize_text_result(result)
        if export_format:
            fmt = normalize_format(export_format)
            data["exported_content"] = await asyncio.to_thread(
                api.export_text, result, fmt
            )
            data["export_format"] = fmt.value
        return data

    async def translate_video(
        self,
        file_bytes: bytes,
        filename: str,
        *,
        subtitle_mode: str = "bilingual",
        domain: str | None = None,
        export_format: str | None = None,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        from translator.core.types import SubtitleFormat, SubtitleOutputMode

        t_domain = _parse_domain(domain)
        try:
            output_mode = SubtitleOutputMode(subtitle_mode.lower())
        except ValueError:
            output_mode = SubtitleOutputMode.BILINGUAL

        suffix = Path(filename).suffix or ".mp4"

        api = await _get_api()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp_path = Path(tmp.name)
        try:
            async with _translate_sem:
                result = await asyncio.to_thread(
                    api.translate_video, tmp_path, t_domain, output_mode
                )
        finally:
            tmp_path.unlink(missing_ok=True)

        data = _serialize_video_result(result)
        if export_format:
            try:
                subtitle_fmt = SubtitleFormat(export_format.lower().strip())
            except ValueError:
                subtitle_fmt = SubtitleFormat.SRT
            exported = await asyncio.to_thread(
                api.export_subtitles, result, subtitle_fmt, None, output_mode
            )
            data["exported_content"] = exported
            data["export_format"] = subtitle_fmt.value
        return data

    def read_local_file(self, relative_path: str) -> tuple[bytes, str]:
        settings = get_settings()
        path = settings.root / relative_path
        if not path.is_file():
            raise TranslatorServiceError("笔记本资料文件不存在")
        return path.read_bytes(), path.name


def get_translator_service() -> TranslatorService:
    return TranslatorService()
