"""
双语翻译结果 Redis 缓存 — 相同文本/文件内容 + 参数命中后直接返回，跳过 Translator 上游。
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings
from app.infrastructure.cache import keys
from app.infrastructure.cache.redis_client import cache_get_json, cache_set_json
from app.services.translator_service import TranslatorService, get_translator_service

logger = logging.getLogger(__name__)


class CachedTranslatorFacade:
    """包装 TranslatorService，对可重复请求做 Redis 缓存。"""

    def __init__(self, inner: TranslatorService | None = None) -> None:
        self._inner = inner or get_translator_service()
        self._ttl = get_settings().cache_ttl_translator

    async def health_check(self) -> dict[str, Any]:
        return await self._inner.health_check()

    async def get_config(self) -> dict[str, Any]:
        return await self._inner.get_config()

    @property
    def is_configured(self) -> bool:
        return self._inner.is_configured

    def read_local_file(self, relative_path: str) -> tuple[bytes, str]:
        return self._inner.read_local_file(relative_path)

    async def translate_text(
        self,
        text: str,
        *,
        mode: str = "full",
        domain: str | None = None,
        export_format: str | None = None,
    ) -> dict[str, Any]:
        content_hash = keys.content_hash(text.encode("utf-8"))
        cache_key = keys.translator_key(
            "text", content_hash, mode=mode, domain=domain or "", export=export_format or ""
        )
        cached = cache_get_json(cache_key)
        if cached is not None:
            logger.debug("translator cache hit text")
            return cached

        data = await self._inner.translate_text(
            text, mode=mode, domain=domain, export_format=export_format
        )
        pairs = data.get("pairs") or []
        if mode == "bilingual" and text.strip() and not pairs:
            return data
        cache_set_json(cache_key, data, self._ttl)
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
        content_hash = keys.content_hash(file_bytes)
        cache_key = keys.translator_key(
            "image", content_hash, mode=mode, domain=domain or "", export=export_format or ""
        )
        cached = cache_get_json(cache_key)
        if cached is not None:
            return cached

        data = await self._inner.translate_image(
            file_bytes,
            filename,
            mode=mode,
            domain=domain,
            export_format=export_format,
            content_type=content_type,
        )
        if mode == "bilingual" and not (data.get("pairs") or []):
            return data
        cache_set_json(cache_key, data, self._ttl)
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
        content_hash = keys.content_hash(file_bytes)
        cache_key = keys.translator_key(
            "document", content_hash, mode=mode, domain=domain or "", export=export_format or ""
        )
        cached = cache_get_json(cache_key)
        if cached is not None:
            return cached

        data = await self._inner.translate_document(
            file_bytes,
            filename,
            mode=mode,
            domain=domain,
            export_format=export_format,
            content_type=content_type,
        )
        if mode == "bilingual" and not (data.get("pairs") or []):
            return data
        cache_set_json(cache_key, data, self._ttl)
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
        # 视频体积大、处理慢，仍缓存相同文件+参数的结果
        content_hash = keys.content_hash(file_bytes)
        cache_key = keys.translator_key(
            "video",
            content_hash,
            subtitle_mode=subtitle_mode,
            domain=domain or "",
            export=export_format or "",
        )
        cached = cache_get_json(cache_key)
        if cached is not None:
            return cached

        data = await self._inner.translate_video(
            file_bytes,
            filename,
            subtitle_mode=subtitle_mode,
            domain=domain,
            export_format=export_format,
            content_type=content_type,
        )
        cache_set_json(cache_key, data, self._ttl)
        return data


_facade: CachedTranslatorFacade | None = None


def get_cached_translator_facade() -> CachedTranslatorFacade:
    global _facade
    if _facade is None:
        _facade = CachedTranslatorFacade()
    return _facade
