"""Resize and JPEG-encode images before vision model calls."""

from __future__ import annotations

import tempfile
from pathlib import Path

import fitz


def prepare_image_for_vision(
    image_path: Path,
    max_dimension: int,
    *,
    jpeg_quality: int = 82,
) -> tuple[Path, bool]:
    """Return (path, is_temporary). Always outputs JPEG for vision API payload size."""
    image_path = image_path.resolve()
    if not image_path.is_file():
        return image_path, False

    if max_dimension <= 0:
        return image_path, False

    doc = fitz.open(image_path)
    try:
        page = doc[0]
        longest = max(page.rect.width, page.rect.height)
        scale = 1.0 if longest <= max_dimension else max_dimension / longest
        matrix = fitz.Matrix(scale, scale)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        tmp.close()
        out = Path(tmp.name)
        pixmap.save(str(out), output="jpeg", jpg_quality=jpeg_quality)
        return out, True
    finally:
        doc.close()
