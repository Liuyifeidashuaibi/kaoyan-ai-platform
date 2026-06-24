from __future__ import annotations

from pathlib import Path


def extension_of(source: Path | str) -> str:
    if isinstance(source, Path):
        return source.suffix.lower()
    if "\n" in source:
        return ""
    return Path(source).suffix.lower()


def is_inline_text(source: Path | str) -> bool:
    if isinstance(source, Path):
        return False
    if "\n" in source:
        return True
    path = Path(source)
    if path.exists():
        return False
    if not path.suffix:
        return True
    return False
