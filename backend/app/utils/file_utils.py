"""
文件处理工具 — 图片保存、路径校验等。
"""

import uuid
from pathlib import Path

# 允许上传的图片扩展名（错题本等落盘场景）
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


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
