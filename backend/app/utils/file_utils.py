"""
文件处理工具 — 学习资料保存、类型识别、路径校验等。
"""

import uuid
from pathlib import Path

# 允许上传的图片扩展名（错题本等落盘场景）
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

ALLOWED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".webm",
    ".mov",
    ".avi",
    ".mkv",
    ".m4v",
    ".3gp",
    ".wmv",
}

MIME_TO_EXTENSION: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    "video/x-matroska": ".mkv",
    "video/3gpp": ".3gp",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mp4": ".m4a",
    "audio/ogg": ".ogg",
    "audio/aac": ".aac",
    "audio/flac": ".flac",
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
}

ALLOWED_DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".txt",
    ".md",
    ".csv",
}

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac"}

ALLOWED_LEARNING_MATERIAL_EXTENSIONS = (
    ALLOWED_IMAGE_EXTENSIONS
    | ALLOWED_VIDEO_EXTENSIONS
    | ALLOWED_DOCUMENT_EXTENSIONS
    | ALLOWED_AUDIO_EXTENSIONS
)

FILE_TYPE_LABELS = {
    "image": "图片",
    "video": "视频",
    "document": "文档",
    "audio": "音频",
    "other": "其他",
}


def ensure_dir(path: Path) -> Path:
    """确保目录存在，不存在则创建。"""
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_upload_image(
    content: bytes,
    upload_dir: Path,
    original_filename: str,
    project_root: Path | None = None,
) -> str:
    """
    将上传的图片保存到本地，返回相对项目根的路径字符串。

    文件名使用 UUID 避免冲突。
    """
    ensure_dir(upload_dir)
    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        ext = ".png"
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = upload_dir / filename
    filepath.write_bytes(content)
    if project_root:
        return str(filepath.relative_to(project_root)).replace("\\", "/")
    return str(filepath).replace("\\", "/")


def is_allowed_image(filename: str) -> bool:
    """检查文件扩展名是否为允许的图片格式。"""
    return Path(filename).suffix.lower() in ALLOWED_IMAGE_EXTENSIONS


def detect_file_type(filename: str) -> str:
    """根据扩展名识别学习资料类型。"""
    ext = Path(filename).suffix.lower()
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return "image"
    if ext in ALLOWED_VIDEO_EXTENSIONS:
        return "video"
    if ext in ALLOWED_DOCUMENT_EXTENSIONS:
        return "document"
    if ext in ALLOWED_AUDIO_EXTENSIONS:
        return "audio"
    return "other"


def normalize_upload_filename(
    filename: str | None,
    content_type: str | None = None,
) -> str | None:
    """补全缺失扩展名的上传文件名（部分浏览器只给 MIME 不给后缀）。"""
    name = (filename or "").strip()
    if name and Path(name).suffix:
        return name

    mime = (content_type or "").split(";")[0].strip().lower()
    ext = MIME_TO_EXTENSION.get(mime)
    if not ext:
        return name or None

    stem = Path(name).stem if name else "upload"
    if not stem or stem == name:
        stem = "upload"
    return f"{stem}{ext}"


def is_allowed_learning_material(
    filename: str | None,
    content_type: str | None = None,
) -> bool:
    """检查文件扩展名是否为允许的学习资料格式。"""
    resolved = normalize_upload_filename(filename, content_type)
    if not resolved:
        return False
    return Path(resolved).suffix.lower() in ALLOWED_LEARNING_MATERIAL_EXTENSIONS


def save_upload_file(
    content: bytes,
    upload_dir: Path,
    original_filename: str,
    project_root: Path | None = None,
) -> str:
    """保存任意学习资料到本地，返回相对项目根的路径字符串。"""
    ensure_dir(upload_dir)
    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_LEARNING_MATERIAL_EXTENSIONS:
        ext = ".bin"
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = upload_dir / filename
    filepath.write_bytes(content)
    if project_root:
        return str(filepath.relative_to(project_root)).replace("\\", "/")
    return str(filepath).replace("\\", "/")
