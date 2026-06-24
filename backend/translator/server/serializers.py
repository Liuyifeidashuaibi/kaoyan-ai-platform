"""Convert engine result objects to JSON-serializable dicts."""

from __future__ import annotations

from translator.core.types import (
    ImageTranslationResult,
    TranslationResult,
    VideoTranslationResult,
)


def serialize_translation_result(result: TranslationResult | ImageTranslationResult) -> dict:
    payload: dict = {
        "mode": result.mode.value,
        "full_text": result.full_text,
        "pairs": [{"source": p.source, "target": p.target} for p in result.pairs],
        "source_name": result.source_name,
        "kind": result.kind.value,
    }
    if isinstance(result, ImageTranslationResult):
        payload["ocr_text"] = result.ocr_text
    return payload


def serialize_video_result(result: VideoTranslationResult) -> dict:
    return {
        "source_name": result.source_name,
        "detected_language": result.detected_language,
        "mode": result.mode.value,
        "cues": [
            {
                "index": cue.index,
                "start": cue.start,
                "end": cue.end,
                "text": cue.text,
                "translation": cue.translation,
            }
            for cue in result.cues
        ],
    }
