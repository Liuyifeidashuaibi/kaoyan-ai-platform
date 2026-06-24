from __future__ import annotations

import re
import shutil
import subprocess
import uuid
from pathlib import Path

from translator.core.exceptions import FileProcessingError
from translator.services.audio.extractor import find_ffmpeg
from translator.utils.config import AppConfig


def find_ffprobe() -> str | None:
    return shutil.which("ffprobe")


def audio_channel_count(audio_path: Path) -> int:
    ffprobe = find_ffprobe()
    if ffprobe is None:
        return 1
    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=channels",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        return int(result.stdout.strip() or "1")
    except (subprocess.CalledProcessError, ValueError):
        return 1


class AudioEnhancer:
    """Light audio cleanup before Whisper — avoids destructive filters on mono sources."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def enhance(self, audio_path: Path) -> Path:
        video_cfg = self._config.video
        if not video_cfg.enhance_audio:
            return audio_path

        ffmpeg = find_ffmpeg()
        output_dir = self._config.cache_dir / "audio"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{audio_path.stem}_enh_{uuid.uuid4().hex[:8]}.wav"

        channels = audio_channel_count(audio_path)
        filters: list[str] = []
        if video_cfg.vocal_isolation and channels >= 2:
            filters.append("pan=mono|c0=0.5*c0+-0.5*c1")
        if video_cfg.highpass_hz > 0:
            filters.append(f"highpass=f={video_cfg.highpass_hz}")
        if video_cfg.lowpass_hz > 0:
            filters.append(f"lowpass=f={video_cfg.lowpass_hz}")
        if video_cfg.use_dynaudnorm:
            filters.append("dynaudnorm=f=150:g=15")
        elif video_cfg.use_loudnorm:
            filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
        if video_cfg.noise_reduction:
            filters.append("afftdn=nf=-20")

        filter_chain = ",".join(filters) if filters else "anull"
        command = [
            ffmpeg,
            "-y",
            "-i",
            str(audio_path),
            "-af",
            filter_chain,
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(self._config.video.audio_sample_rate),
            "-ac",
            "1",
            str(output_path),
        ]

        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise FileProcessingError(f"Audio enhancement failed: {detail}") from exc

        return output_path
