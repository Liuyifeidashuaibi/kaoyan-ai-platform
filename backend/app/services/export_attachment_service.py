"""Build translator export attachments (txt / docx / pdf)."""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)

MIME_BY_FORMAT = {
    "txt": "text/plain",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}

PDF_FONT_NAME = "STSong-Light"


def _safe_stem(title: str) -> str:
    stem = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in title.strip())
    stem = stem.strip(" _-") or "translation"
    return stem[:80]


def _register_pdf_font() -> str:
    """Register a Unicode font for PDF export (works in Docker without system fonts)."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont

    settings = get_settings()
    if settings.pdf_font_path.strip():
        path = Path(settings.pdf_font_path.strip())
        if path.is_file():
            font_name = "CustomExport"
            if font_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(font_name, str(path)))
            return font_name

    bundled = settings.root / "data" / "fonts" / "NotoSansSC-Regular.ttf"
    if bundled.is_file():
        font_name = "NotoSansSC"
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, str(bundled)))
        return font_name

    for path in (
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansSC-Regular.ttf"),
    ):
        if path.is_file():
            font_name = "SystemExport"
            if font_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(font_name, str(path)))
            return font_name

    if PDF_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(PDF_FONT_NAME))
    return PDF_FONT_NAME


def build_txt(content: str, title: str) -> tuple[bytes, str, str]:
    body = content.replace("\r\n", "\n")
    if title.strip():
        body = f"{title.strip()}\n\n{body}"
    data = body.encode("utf-8")
    filename = f"{_safe_stem(title)}.txt"
    return data, filename, MIME_BY_FORMAT["txt"]


def build_docx(content: str, title: str) -> tuple[bytes, str, str]:
    from docx import Document

    doc = Document()
    if title.strip():
        doc.add_heading(title.strip(), level=1)
    for block in content.replace("\r\n", "\n").split("\n"):
        doc.add_paragraph(block)
    buf = BytesIO()
    doc.save(buf)
    filename = f"{_safe_stem(title)}.docx"
    return buf.getvalue(), filename, MIME_BY_FORMAT["docx"]


def build_pdf(content: str, title: str) -> tuple[bytes, str, str]:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    font_name = _register_pdf_font()
    buf = BytesIO()
    page_w, page_h = A4
    margin = 40
    line_height = 14

    c = canvas.Canvas(buf, pagesize=A4)
    y = page_h - margin

    def ensure_space(lines: int = 1) -> None:
        nonlocal y
        if y - lines * line_height < margin:
            c.showPage()
            c.setFont(font_name, body_size)
            y = page_h - margin

    if title.strip():
        c.setFont(font_name, 16)
        ensure_space(2)
        c.drawString(margin, y, title.strip())
        y -= line_height * 2

    body_size = 11
    c.setFont(font_name, body_size)
    for line in content.replace("\r\n", "\n").split("\n"):
        ensure_space(1)
        c.drawString(margin, y, line or " ")
        y -= line_height

    c.save()
    filename = f"{_safe_stem(title)}.pdf"
    return buf.getvalue(), filename, MIME_BY_FORMAT["pdf"]


def build_attachment(content: str, export_format: str, title: str) -> tuple[bytes, str, str]:
    fmt = export_format.lower().strip()
    if fmt == "txt":
        return build_txt(content, title)
    if fmt == "docx":
        return build_docx(content, title)
    if fmt == "pdf":
        return build_pdf(content, title)
    raise ValueError(f"Unsupported export format: {export_format}")
