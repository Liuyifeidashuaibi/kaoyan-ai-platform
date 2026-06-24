from __future__ import annotations

from pathlib import Path
from typing import Protocol

from translator.core.types import Document


class InputProcessor(Protocol):
    def can_handle(self, source: Path | str) -> bool: ...

    def extract(self, source: Path | str) -> Document: ...
