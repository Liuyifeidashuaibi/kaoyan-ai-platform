"""
Qwen3-TTS 合成逻辑 — 供 CLI 与 tts_host_server 共用。
"""

from __future__ import annotations

import io
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

Accent = Literal["us", "uk"]
Voice = Literal["female", "male"]

_MODEL: object | None = None
_MODEL_PATH: str | None = None


def resolve_model_path(explicit: str | None = None) -> Path:
    if explicit:
        p = Path(explicit)
    else:
        p = Path(
            os.environ.get(
                "QWEN3_TTS_MODEL",
                "data/tts/qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
            )
        )
    if not p.is_absolute():
        root = Path(os.environ.get("PROJECT_ROOT", Path(__file__).resolve().parents[1]))
        p = root / p
    return p


def _speaker_for(accent: Accent, voice: Voice) -> tuple[str, str]:
    """Map UI accent/voice to Qwen3 0.6B CustomVoice speaker (no instruct on 0.6B)."""
    # English native: Ryan (male), Aiden (male). Cross-lang female: Serena.
    if voice == "male":
        return "Ryan", ""
    return "Serena", ""


def _load_model(model_path: Path):
    global _MODEL, _MODEL_PATH
    key = str(model_path.resolve())
    if _MODEL is not None and _MODEL_PATH == key:
        return _MODEL

    import torch
    from qwen_tts import Qwen3TTSModel

    if not model_path.is_dir():
        raise FileNotFoundError(f"Qwen3-TTS model not found: {model_path}")

    if torch.cuda.is_available():
        device_map = "cuda:0"
        dtype = torch.bfloat16
    else:
        device_map = "cpu"
        dtype = torch.float32

    logger.info("Loading Qwen3-TTS from %s (%s)", model_path, device_map)
    model = Qwen3TTSModel.from_pretrained(
        str(model_path),
        device_map=device_map,
        dtype=dtype,
    )
    _MODEL = model
    _MODEL_PATH = key
    return model


def synthesize_wav(
    text: str,
    *,
    accent: Accent = "us",
    speed: float = 1.0,
    voice: Voice = "female",
    model_path: str | Path | None = None,
) -> bytes:
    import soundfile as sf

    path = resolve_model_path(str(model_path) if model_path else None)
    model = _load_model(path)
    speaker, instruct = _speaker_for(accent, voice)

    kwargs: dict = {
        "text": text,
        "language": "English",
        "speaker": speaker,
    }
    if instruct:
        kwargs["instruct"] = instruct

    try:
        wavs, sr = model.generate_custom_voice(**kwargs)
    except TypeError:
        kwargs.pop("instruct", None)
        wavs, sr = model.generate_custom_voice(**kwargs)

    audio = wavs[0] if isinstance(wavs, list) else wavs
    if speed != 1.0 and speed > 0:
        import numpy as np

        target_len = max(int(len(audio) / max(speed, 0.1)), 1)
        x_old = np.linspace(0, 1, num=len(audio), endpoint=False)
        x_new = np.linspace(0, 1, num=target_len, endpoint=False)
        audio = np.interp(x_new, x_old, audio).astype(audio.dtype)

    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    return buf.getvalue()


def is_qwen_available(model_path: str | Path | None = None) -> bool:
    try:
        import qwen_tts  # noqa: F401
    except ImportError:
        return False
    path = resolve_model_path(str(model_path) if model_path else None)
    return (path / "config.json").is_file()
