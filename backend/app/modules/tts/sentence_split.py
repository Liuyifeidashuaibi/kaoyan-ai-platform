"""长句分句 — 用于 TTS 同步高亮。"""

from __future__ import annotations

import re

from app.modules.tts.schemas import TtsSentence


def split_tts_sentences(text: str) -> list[TtsSentence]:
    stripped = text.strip()
    if not stripped:
        return []

    parts = re.split(r"(?<=[.!?])\s+", stripped)
    sentences: list[TtsSentence] = []
    cursor = 0
    for idx, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        start = stripped.find(part, cursor)
        if start < 0:
            start = cursor
        end = start + len(part)
        sentences.append(TtsSentence(index=idx, text=part, start_char=start, end_char=end))
        cursor = end
    if not sentences:
        sentences.append(TtsSentence(index=0, text=stripped, start_char=0, end_char=len(stripped)))
    return sentences
