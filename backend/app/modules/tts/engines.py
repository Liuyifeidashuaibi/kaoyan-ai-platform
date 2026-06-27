"""
TTS 引擎抽象 — Qwen3-TTS（GPU 宿主机）优先，Piper（CPU）兜底。
"""

from __future__ import annotations

import io
import logging
import struct
import wave
from abc import ABC, abstractmethod
from pathlib import Path

import httpx
import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)

# Piper 是可选依赖（仅 CPU TTS 兜底用），缺失时不应阻断后端启动。
# 这里改为惰性导入，真正用到 Piper 引擎时才 import。
PiperVoice = None  # type: ignore[assignment]
SynthesisConfig = None  # type: ignore[assignment]
try:
    from piper import PiperVoice as _PiperVoice
    from piper.config import SynthesisConfig as _SynthesisConfig

    PiperVoice = _PiperVoice
    SynthesisConfig = _SynthesisConfig
except ImportError:
    logger.info("piper 未安装，Piper TTS 引擎不可用（不阻断后端启动）")

_voice_cache: dict[str, "PiperVoice"] = {}


class TTSEngine(ABC):
    name: str = "base"

    @abstractmethod
    def synthesize(
        self,
        text: str,
        *,
        accent: str = "us",
        speed: float = 1.0,
        voice: str = "female",
    ) -> bytes:
        """返回 WAV 二进制。"""


def _load_piper_voice(model_path: Path) -> PiperVoice | None:
    key = str(model_path.resolve())
    if key in _voice_cache:
        return _voice_cache[key]
    if not model_path.is_file():
        return None
    try:
        voice = PiperVoice.load(str(model_path))
        _voice_cache[key] = voice
        return voice
    except Exception as exc:
        logger.warning("Piper 模型加载失败 %s: %s", model_path, exc)
        return None


def _chunks_to_wav(chunks, speed: float) -> bytes:
    arrays = [c.audio_float_array for c in chunks if c.audio_float_array.size]
    if not arrays:
        return b""
    audio = np.concatenate(arrays)
    if speed != 1.0 and speed > 0:
        target_len = max(int(len(audio) / max(speed, 0.1)), 1)
        x_old = np.linspace(0, 1, num=len(audio), endpoint=False)
        x_new = np.linspace(0, 1, num=target_len, endpoint=False)
        audio = np.interp(x_new, x_old, audio).astype(np.float32)

    sample_rate = chunks[0].sample_rate
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


class PiperTTSEngine(TTSEngine):
    name = "piper"

    def synthesize(
        self,
        text: str,
        *,
        accent: str = "us",
        speed: float = 1.0,
        voice: str = "female",
    ) -> bytes:
        settings = get_settings()
        model = settings.piper_model_us_female
        if accent == "uk":
            model = settings.piper_model_uk_female
        if voice == "male":
            model = (
                settings.piper_model_us_male
                if accent == "us"
                else settings.piper_model_uk_male
            )
        model_path = Path(model)
        if not model_path.is_absolute():
            model_path = settings.root / model

        piper_voice = _load_piper_voice(model_path)
        if piper_voice is None:
            return _synthesize_wav_beep(text, speed)

        syn_config = SynthesisConfig(
            length_scale=1.0 / max(speed, 0.1) if speed != 1.0 else 1.0
        )
        try:
            chunks = list(piper_voice.synthesize(text, syn_config=syn_config))
            wav = _chunks_to_wav(chunks, speed=1.0)
            if wav:
                return wav
        except Exception as exc:
            logger.warning("Piper 合成失败: %s", exc)
        return _synthesize_wav_beep(text, speed)


class Qwen3TTSEngine(TTSEngine):
    """Qwen3-TTS — 优先调用宿主机 GPU 服务，否则 subprocess 脚本。"""

    name = "qwen3-tts"

    def synthesize(
        self,
        text: str,
        *,
        accent: str = "us",
        speed: float = 1.0,
        voice: str = "female",
    ) -> bytes:
        settings = get_settings()
        host_url = (settings.qwen3_tts_host_url or "").rstrip("/")
        if host_url:
            return self._synthesize_via_host(
                host_url, text, accent=accent, speed=speed, voice=voice
            )
        return self._synthesize_via_script(
            settings, text, accent=accent, speed=speed, voice=voice
        )

    def _synthesize_via_host(
        self,
        host_url: str,
        text: str,
        *,
        accent: str,
        speed: float,
        voice: str,
    ) -> bytes:
        url = f"{host_url}/synthesize"
        with httpx.Client(timeout=300.0) as client:
            resp = client.post(
                url,
                json={
                    "text": text,
                    "accent": accent,
                    "speed": speed,
                    "voice": voice,
                },
            )
            if resp.status_code != 200:
                raise RuntimeError(resp.text[:300])
            if not resp.content:
                raise RuntimeError("empty TTS response")
            return resp.content

    def _synthesize_via_script(
        self,
        settings,
        text: str,
        *,
        accent: str,
        speed: float,
        voice: str,
    ) -> bytes:
        import subprocess
        import sys

        script = settings.qwen3_tts_script
        script_path = Path(script)
        if not script_path.is_absolute():
            script_path = settings.root / script
        if not script_path.is_file():
            raise RuntimeError("Qwen3-TTS 脚本未配置")

        cmd = [
            sys.executable,
            str(script_path),
            "--text",
            text,
            "--accent",
            accent,
            "--speed",
            str(speed),
            "--voice",
            voice,
        ]
        if settings.qwen3_tts_model:
            cmd.extend(["--model", settings.qwen3_tts_model])

        proc = subprocess.run(cmd, capture_output=True, check=False, timeout=300)
        if proc.returncode != 0 or not proc.stdout:
            err = proc.stderr.decode(errors="ignore")[:300]
            raise RuntimeError(err or "Qwen3-TTS script failed")
        return proc.stdout


def _synthesize_wav_beep(text: str, speed: float) -> bytes:
    """极简 CPU 兜底：短 beep WAV。"""
    import math

    duration = min(max(len(text.split()) * 0.15 / max(speed, 0.1), 0.3), 30.0)
    sample_rate = 22050
    n_samples = int(sample_rate * duration)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            val = int(800 * math.sin(2 * math.pi * 440 * i / sample_rate))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(frames)
    return buf.getvalue()


class TTSService:
    def __init__(self) -> None:
        self._qwen = Qwen3TTSEngine()
        self._piper = PiperTTSEngine()

    @staticmethod
    def _is_real_wav(data: bytes) -> bool:
        return len(data) > 500 and data[:4] == b"RIFF"

    def synthesize_wav(
        self,
        text: str,
        *,
        accent: str = "us",
        speed: float = 1.0,
        voice: str = "female",
    ) -> tuple[bytes, str]:
        settings = get_settings()

        def _try_piper() -> tuple[bytes, str] | None:
            data = self._piper.synthesize(
                text, accent=accent, speed=speed, voice=voice
            )
            if self._is_real_wav(data):
                return data, self._piper.name
            return None

        def _try_qwen() -> tuple[bytes, str] | None:
            if not settings.qwen3_tts_enabled:
                return None
            try:
                data = self._qwen.synthesize(
                    text, accent=accent, speed=speed, voice=voice
                )
                if self._is_real_wav(data):
                    return data, self._qwen.name
            except Exception as exc:
                logger.warning("Qwen3-TTS 失败: %s", exc)
            return None

        # 默认 Piper 优先（秒级）；Qwen3 作高质量备选
        if settings.tts_prefer_piper:
            hit = _try_piper()
            if hit:
                return hit
            hit = _try_qwen()
            if hit:
                return hit
        else:
            hit = _try_qwen()
            if hit:
                return hit
            hit = _try_piper()
            if hit:
                return hit

        data = self._piper.synthesize(text, accent=accent, speed=speed, voice=voice)
        return data, self._piper.name


_service: TTSService | None = None


def get_tts_service() -> TTSService:
    global _service
    if _service is None:
        _service = TTSService()
    return _service
