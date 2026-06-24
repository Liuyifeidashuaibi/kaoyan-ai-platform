from pathlib import Path

import fitz

from translator.core.types import Document, InputKind
from translator.processors.base import InputProcessor
from translator.utils.source import extension_of


class PdfProcessor:
    def can_handle(self, source: Path | str) -> bool:
        return extension_of(source) == ".pdf"

    def extract(self, source: Path | str) -> Document:
        path = Path(source).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"PDF not found: {path}")

        doc = fitz.open(path)
        pages: list[str] = []
        try:
            for page in doc:
                text = page.get_text().strip()
                if text:
                    pages.append(text)
        finally:
            doc.close()

        if not pages:
            raise ValueError(
                f"No extractable text in PDF: {path.name}. "
                "Use document translation to OCR scanned PDFs automatically."
            )

        return Document(
            text="\n\n".join(pages),
            source_name=path.name,
            needs_vision=False,
            kind=InputKind.DOCUMENT,
        )


def get_pdf_processor() -> InputProcessor:
    return PdfProcessor()
