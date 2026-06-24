from pathlib import Path

from translator.core.exceptions import UnsupportedFormatError
from translator.core.types import Document, InputKind
from translator.processors.base import InputProcessor
from translator.processors.docx import DocxProcessor
from translator.processors.image import ImageProcessor
from translator.processors.pdf import PdfProcessor
from translator.processors.text import TextProcessor
from translator.processors.video import VideoProcessor

_PROCESSORS: list[InputProcessor] = [
    VideoProcessor(),
    ImageProcessor(),
    DocxProcessor(),
    PdfProcessor(),
    TextProcessor(),
]


def resolve_processor(source: Path | str) -> InputProcessor:
    for processor in _PROCESSORS:
        if processor.can_handle(source):
            return processor
    raise UnsupportedFormatError(f"No processor available for: {source}")


def extract_document(source: Path | str) -> Document:
    return resolve_processor(source).extract(source)


def detect_input_kind(source: Path | str) -> InputKind:
    processor = resolve_processor(source)
    document = processor.extract(source)
    return document.kind
