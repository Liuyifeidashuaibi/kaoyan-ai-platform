from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def get_audio_duration(audio_path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return 0.0
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
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
        return float(result.stdout.strip() or "0")
    except (subprocess.CalledProcessError, ValueError):
        return 0.0
