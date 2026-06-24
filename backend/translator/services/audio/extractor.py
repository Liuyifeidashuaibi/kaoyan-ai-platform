from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path

from translator.core.exceptions import DependencyMissingError, FileProcessingError
from translator.utils.config import AppConfig


def find_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise DependencyMissingError(
            "ffmpeg is not installed or not in PATH. "
            "Install ffmpeg to enable video translation."
        )
    return ffmpeg


class AudioExtractor:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def extract(self, video_path: Path) -> Path:
        ffmpeg = find_ffmpeg()
        video_path = video_path.resolve()
        if not video_path.is_file():
            raise FileProcessingError(f"Video file not found: {video_path}")

        output_dir = self._config.cache_dir / "audio"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{video_path.stem}_{uuid.uuid4().hex[:8]}.wav"

        channels = "1"
        command = [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(self._config.video.audio_sample_rate),
            "-ac",
            channels,
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
            raise FileProcessingError(
                f"Failed to extract audio from video: {detail}"
            ) from exc

        if not output_path.is_file():
            raise FileProcessingError("Audio extraction produced no output file.")

        return output_path
