from __future__ import annotations

import re

from translator.core.types import SubtitleCue, SubtitleFormat, SubtitleOutputMode


def _format_timestamp_srt(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_timestamp_vtt(seconds: float) -> str:
    return _format_timestamp_srt(seconds).replace(",", ".")


def _wrap_text(text: str, max_chars: int, max_lines: int) -> str:
    words = text.split()
    if not words:
        return ""

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return "\n".join(lines)


def normalize_cues(
    cues: list[SubtitleCue],
    max_chars_per_line: int = 42,
    max_lines: int = 2,
) -> list[SubtitleCue]:
    normalized: list[SubtitleCue] = []
    for cue in cues:
        wrapped = _wrap_text(cue.text, max_chars_per_line, max_lines)
        translation = cue.translation
        if translation:
            translation = _wrap_text(translation, max_chars_per_line, max_lines)
        normalized.append(
            SubtitleCue(
                index=len(normalized) + 1,
                start=cue.start,
                end=cue.end,
                text=wrapped or cue.text,
                translation=translation,
            )
        )
    return normalized


def _render_cue_text(
    cue: SubtitleCue, mode: SubtitleOutputMode
) -> str:
    if mode == SubtitleOutputMode.ORIGINAL:
        return cue.text
    if mode == SubtitleOutputMode.TRANSLATED:
        return cue.translation or cue.text
    if cue.translation:
        return f"{cue.text}\n{cue.translation}"
    return cue.text


def export_subtitles(
    cues: list[SubtitleCue],
    fmt: SubtitleFormat,
    mode: SubtitleOutputMode = SubtitleOutputMode.BILINGUAL,
) -> str:
    if fmt == SubtitleFormat.SRT:
        return _to_srt(cues, mode)
    if fmt == SubtitleFormat.VTT:
        return _to_vtt(cues, mode)
    if fmt == SubtitleFormat.TXT:
        return _to_txt(cues, mode)
    raise ValueError(f"Unsupported subtitle format: {fmt}")


def _to_srt(cues: list[SubtitleCue], mode: SubtitleOutputMode) -> str:
    blocks: list[str] = []
    for cue in cues:
        body = _render_cue_text(cue, mode)
        blocks.append(
            f"{cue.index}\n"
            f"{_format_timestamp_srt(cue.start)} --> {_format_timestamp_srt(cue.end)}\n"
            f"{body}\n"
        )
    return "\n".join(blocks).strip() + "\n"


def _to_vtt(cues: list[SubtitleCue], mode: SubtitleOutputMode) -> str:
    lines = ["WEBVTT", ""]
    for cue in cues:
        body = _render_cue_text(cue, mode)
        lines.append(
            f"{_format_timestamp_vtt(cue.start)} --> {_format_timestamp_vtt(cue.end)}"
        )
        lines.append(body)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _to_txt(cues: list[SubtitleCue], mode: SubtitleOutputMode) -> str:
    parts: list[str] = []
    for cue in cues:
        body = _render_cue_text(cue, mode)
        body = re.sub(r"\s*\n\s*", "\n", body)
        parts.append(body)
    return "\n\n".join(parts).strip() + "\n"
