"""音频格式检测与 ASR 结果解析。"""

from __future__ import annotations

import struct
from pathlib import Path


def detect_asr_format(audio_bytes: bytes, filename: str) -> tuple[str, int]:
    """
    推断 DashScope Recognition 所需的 format 与 sample_rate。
    浏览器录音应为 16kHz WAV。
    """
    suffix = Path(filename).suffix.lower().lstrip(".")
    if audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
        rate = 16000
        if len(audio_bytes) >= 28:
            rate = struct.unpack_from("<I", audio_bytes, 24)[0] or 16000
        return "wav", int(rate)
    if suffix in ("wav",):
        return "wav", 16000
    if suffix in ("mp3",):
        return "mp3", 16000
    if suffix in ("webm",):
        return "webm", 48000
    if suffix in ("ogg", "opus"):
        return "opus", 48000
    return suffix or "wav", 16000


def is_silent_wav(audio_bytes: bytes, threshold: int = 80) -> bool:
    """检测 WAV 是否近似静音（避免空录音调用 ASR）。"""
    if len(audio_bytes) < 64 or audio_bytes[:4] != b"RIFF":
        return len(audio_bytes) < 512
    try:
        data_offset = 44
        if len(audio_bytes) <= data_offset + 2:
            return True
        peak = 0
        step = max(2, (len(audio_bytes) - data_offset) // 2000 * 2)
        for i in range(data_offset, len(audio_bytes) - 1, step):
            sample = struct.unpack_from("<h", audio_bytes, i)[0]
            peak = max(peak, abs(sample))
        return peak < threshold
    except struct.error:
        return False


def extract_recognition_text(result) -> str:
    """从 DashScope RecognitionResult 提取完整文本。"""
    sentence = result.get_sentence() if hasattr(result, "get_sentence") else None
    if sentence is None and getattr(result, "output", None):
        sentence = result.output.get("sentence")

    if isinstance(sentence, dict):
        return str(sentence.get("text", "")).strip()
    if isinstance(sentence, list):
        parts: list[str] = []
        for item in sentence:
            if isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
        return "".join(parts).strip()
    return ""
