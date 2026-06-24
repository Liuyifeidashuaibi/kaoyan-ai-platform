from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ModelProvider(Protocol):
    def translate_text(self, text: str, system_prompt: str, user_prompt: str) -> str: ...

    def translate_with_image(
        self, image_path: Path, system_prompt: str, user_prompt: str
    ) -> str: ...

    def is_available(self) -> bool: ...
