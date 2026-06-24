from pathlib import Path

from translator.core.types import Document, InputKind
from translator.processors.base import InputProcessor
from translator.utils.source import extension_of

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


class ImageProcessor:
    def can_handle(self, source: Path | str) -> bool:
        return extension_of(source) in IMAGE_EXTENSIONS

    def extract(self, source: Path | str) -> Document:
        path = Path(source).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Image not found: {path}")
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError(f"Unsupported image format: {path.suffix}")
        return Document(
            image_path=path,
            source_name=path.name,
            needs_vision=True,
            kind=InputKind.IMAGE,
        )


def get_image_processor() -> InputProcessor:
    return ImageProcessor()
