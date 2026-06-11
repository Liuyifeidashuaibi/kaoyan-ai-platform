"""
图片处理 — 内存 Base64 直传 / 公网 HTTPS 链接校验，供 DashScope qwen-vl 使用。

禁止拼接 localhost、内网 IP、PUBLIC_BASE_URL 等任何形式的内网可访问地址。
"""

from __future__ import annotations

import base64
import ipaddress
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from app.config import Settings

logger = logging.getLogger(__name__)

# 仅允许常见图片 MIME（不含 bmp）
ALLOWED_IMAGE_MIMES = frozenset(
    {"image/jpeg", "image/png", "image/gif", "image/webp"}
)
ALLOWED_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp"})

# 文件头魔数校验
_IMAGE_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"RIFF", "image/webp"),  # 需额外检查 WEBP
]

HTTPS_URL_PATTERN = re.compile(
    r"https://[^\s<>\"']+",
    re.IGNORECASE,
)

ImageSourceType = Literal[
    "upload_base64", "https_link", "content_link", "legacy_disk"
]


class ImageProcessingError(Exception):
    """图片处理业务异常，message 可直接返回前端。"""

    def __init__(self, message: str, *, log_detail: str = "") -> None:
        super().__init__(message)
        self.user_message = message
        self.log_detail = log_detail


@dataclass(frozen=True)
class ResolvedImage:
    """解析后的图片载荷，api_url 可直接填入 qwen-vl image_url 字段。"""

    api_url: str
    source_type: ImageSourceType
    storage_ref: str | None  # 写入 DB 的 image_path（https 或错题本磁盘路径）


def log_image_event(
    *,
    request_type: str,
    source: str,
    model: str,
    status: str,
    detail: str = "",
) -> None:
    extra = f" | {detail}" if detail else ""
    logger.info(
        "[图片处理] 请求类型=%s | 图片来源=%s | 模型=%s | 状态=%s%s",
        request_type,
        source,
        model,
        status,
        extra,
    )


def _mime_to_data_url_prefix(mime: str) -> str:
    if mime == "image/jpeg":
        return "data:image/jpeg;base64,"
    if mime == "image/png":
        return "data:image/png;base64,"
    if mime == "image/gif":
        return "data:image/gif;base64,"
    if mime == "image/webp":
        return "data:image/webp;base64,"
    raise ImageProcessingError("不支持的图片格式，仅允许 jpg、jpeg、png、gif、webp。")


def detect_image_mime(content: bytes, filename: str | None = None) -> str:
    """通过魔数 + 扩展名双重校验图片类型，拦截伪装的可执行文件等。"""
    if not content:
        raise ImageProcessingError("图片文件为空或已损坏，请重新上传。")

    if filename:
        ext = Path(filename).suffix.lower()
        if ext and ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise ImageProcessingError(
                "仅支持 jpg、jpeg、png、gif、webp 图片格式，"
                "请勿上传可执行文件、文档或压缩包。"
            )

    detected: str | None = None
    for sig, mime in _IMAGE_SIGNATURES:
        if content.startswith(sig):
            detected = mime
            break

    if detected == "image/webp":
        if len(content) < 12 or content[8:12] != b"WEBP":
            detected = None

    if not detected:
        raise ImageProcessingError(
            "无法识别图片格式，文件可能已损坏或不是合法图片。"
            "仅支持 jpg、jpeg、png、gif、webp。"
        )

    if filename:
        ext = Path(filename).suffix.lower()
        ext_mime = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(ext)
        if ext_mime and ext_mime != detected:
            raise ImageProcessingError(
                "文件扩展名与内容不匹配，请勿上传伪装的可执行文件或文档。"
            )

    return detected


def bytes_to_qwen_image_url(content: bytes, mime: str) -> str:
    """按阿里云 qwen-vl OpenAI 兼容规范组装 data URL。"""
    try:
        b64 = base64.b64encode(content).decode("ascii")
    except Exception as exc:
        raise ImageProcessingError(
            "图片转 Base64 失败，请换一张图片重试。",
            log_detail=str(exc),
        ) from exc
    return f"{_mime_to_data_url_prefix(mime)}{b64}"


def validate_upload_bytes(
    content: bytes,
    filename: str | None,
    *,
    max_bytes: int,
) -> ResolvedImage:
    """本地上传：内存转 Base64，不落盘。"""
    if len(content) > max_bytes:
        mb = max_bytes // (1024 * 1024)
        raise ImageProcessingError(
            f"图片过大（超过 {mb}MB），请压缩后重试。"
        )
    mime = detect_image_mime(content, filename)
    api_url = bytes_to_qwen_image_url(content, mime)
    log_image_event(
        request_type="vision",
        source="upload_base64",
        model="-",
        status="resolved",
        detail=f"bytes={len(content)}, mime={mime}",
    )
    return ResolvedImage(
        api_url=api_url,
        source_type="upload_base64",
        storage_ref=None,
    )


def _is_forbidden_host(hostname: str) -> bool:
    if not hostname:
        return True
    host = hostname.lower().rstrip(".")
    if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        return True
    if host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return bool(ip.is_private or ip.is_loopback or ip.is_link_local)
    except ValueError:
        return False


def validate_public_https_url(url: str) -> str:
    """
    校验用户输入的公网 HTTPS 图片链接。
    仅放行 https:// 开头且非内网/本机地址的链接。
    """
    raw = (url or "").strip()
    if not raw:
        raise ImageProcessingError("图片链接不能为空。")

    if raw.lower().startswith(("http://", "blob:", "file:", "data:")):
        raise ImageProcessingError(
            "仅支持 https:// 开头的公网图片链接。"
            "localhost、内网地址、http 非加密链接均不可用。"
        )

    if not raw.lower().startswith("https://"):
        raise ImageProcessingError(
            "图片链接必须以 https:// 开头，且为可公网访问的地址。"
        )

    parsed = urlparse(raw)
    if parsed.scheme != "https":
        raise ImageProcessingError("仅支持 HTTPS 加密的公网图片链接。")

    if _is_forbidden_host(parsed.hostname or ""):
        raise ImageProcessingError(
            "该链接指向本机或内网地址，无法用于图片识别。"
            "请使用可公网访问的 https:// 图片链接。"
        )

    log_image_event(
        request_type="vision",
        source="https_link",
        model="-",
        status="validated",
        detail=raw[:120],
    )
    return raw


def extract_https_image_url_from_text(text: str) -> str | None:
    """从用户消息文本中提取首个合法 https 图片链接。"""
    for match in HTTPS_URL_PATTERN.finditer(text):
        candidate = match.group(0).rstrip(".,;:!?)】」\"'")
        try:
            return validate_public_https_url(candidate)
        except ImageProcessingError:
            continue
    return None


def resolve_legacy_disk_image(relative_path: str, settings: Settings) -> ResolvedImage:
    """
    错题本等已落盘图片：读取本地文件转 Base64，不拼接任何公网 URL。
    仅允许项目 uploads/ 目录下的相对路径。
    """
    normalized = relative_path.replace("\\", "/").lstrip("/")
    if not normalized.startswith("uploads/"):
        raise ImageProcessingError("非法图片路径，仅允许访问已上传的错题图片。")

    full_path = (settings.root / normalized).resolve()
    uploads_root = (settings.root / "uploads").resolve()
    try:
        full_path.relative_to(uploads_root)
    except ValueError as exc:
        raise ImageProcessingError("非法图片路径。") from exc

    if not full_path.is_file():
        raise ImageProcessingError("图片文件不存在或已被删除，请重新上传。")

    try:
        content = full_path.read_bytes()
    except OSError as exc:
        raise ImageProcessingError(
            "读取图片文件失败，文件可能已损坏。",
            log_detail=str(exc),
        ) from exc

    mime = detect_image_mime(content, full_path.name)
    api_url = bytes_to_qwen_image_url(content, mime)
    log_image_event(
        request_type="vision",
        source="legacy_disk",
        model="-",
        status="resolved",
        detail=normalized,
    )
    return ResolvedImage(
        api_url=api_url,
        source_type="legacy_disk",
        storage_ref=normalized,
    )


async def resolve_chat_image(
    *,
    content: str,
    image_bytes: bytes | None,
    image_filename: str | None,
    image_url_field: str | None,
    image_path_legacy: str | None,
    settings: Settings,
) -> ResolvedImage | None:
    """
    统一解析聊天图片输入，按优先级：
    1. 本地上传二进制  2. 表单 image_url  3. 错题本磁盘路径  4. 消息内 https 链接
    """
    max_bytes = settings.max_image_upload_bytes

    if image_bytes:
        return validate_upload_bytes(
            image_bytes, image_filename, max_bytes=max_bytes
        )

    if image_url_field and image_url_field.strip():
        url = validate_public_https_url(image_url_field.strip())
        return ResolvedImage(
            api_url=url,
            source_type="https_link",
            storage_ref=url,
        )

    if image_path_legacy and image_path_legacy.strip():
        return resolve_legacy_disk_image(image_path_legacy.strip(), settings)

    url_from_text = extract_https_image_url_from_text(content)
    if url_from_text:
        return ResolvedImage(
            api_url=url_from_text,
            source_type="content_link",
            storage_ref=url_from_text,
        )

    return None
