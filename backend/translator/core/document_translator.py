from __future__ import annotations

from pathlib import Path

from translator.core.exceptions import FileProcessingError
from translator.core.image_translator import ImageTranslator
from translator.core.text_translator import TextTranslator
from translator.core.types import InputKind, TranslationDomain, TranslationMode, TranslationResult
from translator.processors import extract_document
from translator.services.pdf.scanned import render_pdf_pages
from translator.utils.config import AppConfig
from translator.utils.source import extension_of


class DocumentTranslator:
    """Extract text from PDF/DOCX/TXT, with scanned-PDF OCR fallback."""

    def __init__(
        self,
        text_translator: TextTranslator,
        image_translator: ImageTranslator,
        config: AppConfig,
    ) -> None:
        self._text_translator = text_translator
        self._image_translator = image_translator
        self._config = config

    def translate(
        self,
        file_path: Path,
        mode: TranslationMode,
        domain: TranslationDomain,
    ) -> TranslationResult:
        path = Path(file_path)
        text, source_name = self._extract_text(path)

        result = self._text_translator.translate(
            text,
            mode=mode,
            domain=domain,
            source_name=source_name,
        )
        result.kind = InputKind.DOCUMENT
        return result

    def _extract_text(self, path: Path) -> tuple[str, str]:
        if extension_of(path) == ".pdf":
            try:
                document = extract_document(path)
                if document.text and document.text.strip():
                    return document.text, document.source_name
            except (ValueError, FileProcessingError):
                pass
            return self._ocr_scanned_pdf(path), path.name

        document = extract_document(path)
        if not document.text or not document.text.strip():
            raise FileProcessingError(f"No extractable text in document: {path.name}")
        return document.text, document.source_name

    def _ocr_scanned_pdf(self, path: Path) -> str:
        page_images = render_pdf_pages(path, self._config.cache_dir)
        ocr_parts: list[str] = []
        try:
            for index, image_path in enumerate(page_images, start=1):
                page_text = self._image_translator.extract_ocr(
                    image_path, source_name=f"{path.name}#page{index}"
                )
                if page_text.strip():
                    ocr_parts.append(page_text.strip())
        finally:
            for image_path in page_images:
                image_path.unlink(missing_ok=True)
            parent = page_images[0].parent if page_images else None
            if parent and parent.exists():
                try:
                    parent.rmdir()
                except OSError:
                    pass

        if not ocr_parts:
            raise FileProcessingError(
                f"OCR produced no text for scanned PDF: {path.name}"
            )
        return "\n\n".join(ocr_parts)
