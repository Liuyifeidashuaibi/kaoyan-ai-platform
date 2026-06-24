from __future__ import annotations

import uuid
from pathlib import Path

import fitz

from translator.core.exceptions import FileProcessingError


def render_pdf_pages(pdf_path: Path, cache_dir: Path, dpi: int = 150) -> list[Path]:
    """Render PDF pages to PNG images for scanned-document OCR."""
    pdf_path = pdf_path.resolve()
    if not pdf_path.is_file():
        raise FileProcessingError(f"PDF not found: {pdf_path}")

    output_dir = cache_dir / "pdf_pages" / f"{pdf_path.stem}_{uuid.uuid4().hex[:8]}"
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    image_paths: list[Path] = []
    try:
        if len(doc) == 0:
            raise FileProcessingError(f"PDF has no pages: {pdf_path.name}")

        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)
        for page in doc:
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image_path = output_dir / f"page_{page.number + 1:04d}.png"
            pixmap.save(str(image_path))
            image_paths.append(image_path)
    finally:
        doc.close()

    return image_paths
