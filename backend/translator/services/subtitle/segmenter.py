from __future__ import annotations

import re

from translator.core.types import SubtitleCue


def resplit_cues(
    cues: list[SubtitleCue],
    *,
    max_duration: float = 4.5,
    max_chars: int = 72,
) -> list[SubtitleCue]:
    """Split overly long Whisper segments for readability and accuracy."""
    result: list[SubtitleCue] = []

    for cue in cues:
        duration = cue.end - cue.start
        text = cue.text.strip()
        if duration <= max_duration and len(text) <= max_chars:
            result.append(cue)
            continue

        clauses = _split_clauses(text)
        if len(clauses) <= 1:
            result.append(cue)
            continue

        step = duration / len(clauses)
        for index, clause in enumerate(clauses):
            start = cue.start + step * index
            end = cue.start + step * (index + 1)
            result.append(
                SubtitleCue(
                    index=0,
                    start=start,
                    end=end,
                    text=clause,
                    translation=cue.translation,
                )
            )

    for index, cue in enumerate(result, start=1):
        result[index - 1] = SubtitleCue(
            index=index,
            start=cue.start,
            end=cue.end,
            text=cue.text,
            translation=cue.translation,
        )
    return result


def resplit_cues_from_words(
    segments: list,
    *,
    max_gap: float = 0.35,
    max_duration: float = 4.0,
    max_chars: int = 64,
) -> list[SubtitleCue]:
    """Build subtitle cues from Whisper word timestamps."""
    cues: list[SubtitleCue] = []
    bucket: list = []
    bucket_start: float | None = None
    bucket_end: float | None = None

    def flush() -> None:
        nonlocal bucket, bucket_start, bucket_end
        if not bucket:
            return
        text = _normalize_spaces("".join(word.word for word in bucket))
        if text:
            cues.append(
                SubtitleCue(
                    index=len(cues) + 1,
                    start=bucket_start or bucket[0].start,
                    end=bucket_end or bucket[-1].end,
                    text=text,
                )
            )
        bucket = []
        bucket_start = None
        bucket_end = None

    for segment in segments:
        words = getattr(segment, "words", None) or []
        if not words:
            text = getattr(segment, "text", "").strip()
            if text:
                cues.append(
                    SubtitleCue(
                        index=len(cues) + 1,
                        start=segment.start,
                        end=segment.end,
                        text=text,
                    )
                )
            continue

        for word in words:
            token = word.word.strip()
            if not token:
                continue

            gap = 0.0
            if bucket_end is not None:
                gap = max(0.0, word.start - bucket_end)
            current_duration = 0.0
            if bucket_start is not None:
                current_duration = word.end - bucket_start
            current_text = "".join(w.word for w in bucket)

            if bucket and (
                gap > max_gap
                or current_duration > max_duration
                or len(current_text) + len(token) > max_chars
            ):
                flush()

            if bucket_start is None:
                bucket_start = word.start
            bucket.append(word)
            bucket_end = word.end

    flush()
    return cues


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _split_clauses(text: str) -> list[str]:
    parts = re.split(r"(?<=[,.!?;])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]
