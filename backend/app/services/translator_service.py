"""HTTP client for the independent Translator service."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


def _guess_mime(filename: str) -> str:
    import mimetypes

    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


class TranslatorServiceError(Exception):
    """Translator upstream returned an error or is unreachable."""


class TranslatorService:
    """Proxy client — no translation logic, only HTTP forwarding."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.translator_service_url.rstrip("/")
        self.api_key = settings.translator_api_key.strip()
        self.timeout = httpx.Timeout(settings.translator_timeout_seconds)

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key}

    async def health_check(self) -> dict[str, Any]:
        if not self.base_url:
            raise TranslatorServiceError("未配置 Translator 服务地址")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                res = await client.get(f"{self.base_url}/health")
                payload = res.json()
                if res.status_code >= 400 or not payload.get("success"):
                    message = payload.get("message") or f"健康检查失败 ({res.status_code})"
                    raise TranslatorServiceError(message)
                return payload.get("data") or {}
        except httpx.TimeoutException as exc:
            raise TranslatorServiceError("Translator 服务响应超时") from exc
        except httpx.RequestError as exc:
            raise TranslatorServiceError(f"无法连接 Translator 服务: {exc}") from exc

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        files: dict | None = None,
        data: dict | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured:
            raise TranslatorServiceError("Translator 服务未配置（TRANSLATOR_SERVICE_URL / TRANSLATOR_API_KEY）")

        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.request(
                    method,
                    url,
                    headers=self._headers(),
                    json=json,
                    files=files,
                    data=data,
                )
        except httpx.TimeoutException as exc:
            raise TranslatorServiceError("翻译服务处理超时，请稍后重试") from exc
        except httpx.RequestError as exc:
            logger.warning("Translator service unreachable: %s", exc)
            raise TranslatorServiceError("翻译服务暂时不可用") from exc

        try:
            payload = res.json()
        except ValueError as exc:
            raise TranslatorServiceError(f"翻译服务返回无效响应 ({res.status_code})") from exc

        if res.status_code >= 400 or not payload.get("success"):
            raise TranslatorServiceError(self._extract_error_message(payload, res.status_code))

        return payload.get("data") or {}

    @staticmethod
    def _extract_error_message(payload: dict[str, Any], status: int) -> str:
        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message
        detail = payload.get("detail")
        if isinstance(detail, dict):
            nested = detail.get("message")
            if isinstance(nested, str) and nested.strip():
                return nested
        if isinstance(detail, str) and detail.strip():
            return detail
        return f"翻译服务错误 ({status})"

    async def translate_text(
        self,
        text: str,
        *,
        mode: str = "full",
        domain: str | None = None,
        export_format: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"text": text, "mode": mode}
        if domain:
            body["domain"] = domain
        if export_format:
            body["export_format"] = export_format
        return await self._request_json("POST", "/translate/text", json=body)

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
        data: dict[str, str] = {"mode": mode}
        if domain:
            data["domain"] = domain
        if export_format:
            data["export_format"] = export_format
        mime = content_type or _guess_mime(filename)
        files = {"file": (filename, file_bytes, mime)}
        return await self._request_json(
            "POST", "/translate/image", files=files, data=data
        )

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
        data: dict[str, str] = {"mode": mode}
        if domain:
            data["domain"] = domain
        if export_format:
            data["export_format"] = export_format
        mime = content_type or _guess_mime(filename)
        files = {"file": (filename, file_bytes, mime)}
        return await self._request_json(
            "POST", "/translate/document", files=files, data=data
        )

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
        data: dict[str, str] = {"subtitle_mode": subtitle_mode}
        if domain:
            data["domain"] = domain
        if export_format:
            data["export_format"] = export_format
        mime = content_type or _guess_mime(filename)
        files = {"file": (filename, file_bytes, mime)}
        return await self._request_json(
            "POST", "/translate/video", files=files, data=data
        )

    async def get_config(self) -> dict[str, Any]:
        return await self._request_json("GET", "/config")

    def read_local_file(self, relative_path: str) -> tuple[bytes, str]:
        settings = get_settings()
        path = settings.root / relative_path
        if not path.is_file():
            raise TranslatorServiceError("笔记本资料文件不存在")
        return path.read_bytes(), path.name


def get_translator_service() -> TranslatorService:
    return TranslatorService()
