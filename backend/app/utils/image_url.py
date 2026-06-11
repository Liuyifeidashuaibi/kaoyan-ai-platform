"""
图片 URL 解析 — 为 DashScope 视觉模型生成可访问的图片地址。

视觉模型要求公网 HTTPS URL；本地开发无 PUBLIC_BASE_URL 时回退为 base64 data URL。
禁止向 API 传递 blob: / file: / localhost: 地址。
"""

import base64
import logging
from pathlib import Path
from urllib.parse import urlparse

from app.config import Settings

logger = logging.getLogger(__name__)

FORBIDDEN_URL_PREFIXES = ("blob:", "file:")
FORBIDDEN_URL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0")


def _is_forbidden_api_url(url: str) -> bool:
    if not url:
        return True
    lower = url.lower()
    if lower.startswith(FORBIDDEN_URL_PREFIXES):
        return True
    if lower.startswith("data:"):
        return False
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host in FORBIDDEN_URL_HOSTS:
        return True
    if parsed.scheme not in ("http", "https", "data"):
        return True
    return False


def _to_base64_data_url(full_path: Path) -> str:
    suffix = full_path.suffix.lower().lstrip(".")
    mime = "jpeg" if suffix in ("jpg", "jpeg") else suffix or "png"
    b64 = base64.b64encode(full_path.read_bytes()).decode("utf-8")
    return f"data:image/{mime};base64,{b64}"


def resolve_public_image_url(relative_path: str, settings: Settings) -> str:
    """
    将相对上传路径转为 DashScope 可读取的图片 URL。

    优先使用 PUBLIC_BASE_URL 生成 HTTPS 公网地址；
    未配置时回退 base64（仅适合本地开发）。
    """
    normalized = relative_path.replace("\\", "/").lstrip("/")
    full_path = settings.root / normalized
    if not full_path.exists():
        raise FileNotFoundError(f"图片不存在: {relative_path}")

    public_base = settings.public_base_url.strip().rstrip("/")
    if public_base:
        if not public_base.startswith("https://"):
            logger.warning(
                "PUBLIC_BASE_URL 建议使用 HTTPS，当前值: %s", public_base
            )
        url = f"{public_base}/{normalized}"
        if _is_forbidden_api_url(url):
            raise ValueError(f"图片 URL 不可用（含 localhost/file/blob）: {url}")
        logger.info("视觉模型图片 URL: %s", url)
        return url

    logger.warning(
        "未配置 PUBLIC_BASE_URL，使用 base64 传递图片（生产环境请配置公网 HTTPS 地址）"
    )
    return _to_base64_data_url(full_path)


def validate_api_image_url(url: str) -> None:
    """发送前校验，确保不会把无效地址传给 DashScope。"""
    if _is_forbidden_api_url(url):
        raise ValueError(
            f"禁止向视觉模型传递 blob/file/localhost 地址: {url[:80]}"
        )
