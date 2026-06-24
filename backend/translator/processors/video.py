from pathlib import Path

from translator.core.types import Document, InputKind
from translator.processors.base import InputProcessor
from translator.utils.source import extension_of

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov"}


class VideoProcessor:
    def can_handle(self, source: Path | str) -> bool:
        return extension_of(source) in VIDEO_EXTENSIONS

    def extract(self, source: Path | str) -> Document:
        path = Path(source).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Video not found: {path}")
        return Document(
            video_path=path,
            source_name=path.name,
            needs_vision=False,
            kind=InputKind.VIDEO,
        )


def get_video_processor() -> InputProcessor:
    return VideoProcessor()
