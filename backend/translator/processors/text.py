from pathlib import Path

from translator.core.types import Document, InputKind
from translator.processors.base import InputProcessor
from translator.utils.source import extension_of, is_inline_text

TEXT_EXTENSIONS = {".txt", ".md", ".text"}


class TextProcessor:
    def can_handle(self, source: Path | str) -> bool:
        ext = extension_of(source)
        if ext in TEXT_EXTENSIONS:
            return True
        return is_inline_text(source)

    def extract(self, source: Path | str) -> Document:
        if is_inline_text(source):
            assert isinstance(source, str)
            return Document(
                text=source,
                source_name="inline-text",
                needs_vision=False,
                kind=InputKind.TEXT,
            )

        path = Path(source)
        text = path.read_text(encoding="utf-8")
        return Document(
            text=text,
            source_name=path.name,
            needs_vision=False,
            kind=InputKind.DOCUMENT,
        )


def get_text_processor() -> InputProcessor:
    return TextProcessor()
