from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

from translator.core.exceptions import DependencyMissingError, ModelDownloadError
from translator.utils.config import AppConfig, WhisperConfig


def is_faster_whisper_installed() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def install_faster_whisper() -> None:
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "faster-whisper>=1.0.0"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        output = (exc.stderr or exc.stdout or "").strip()
        raise ModelDownloadError(
            f"Failed to install faster-whisper automatically: {output}"
        ) from exc


def ensure_faster_whisper() -> None:
    if not is_faster_whisper_installed():
        install_faster_whisper()
    if not is_faster_whisper_installed():
        raise DependencyMissingError("faster-whisper installation did not succeed.")


def whisper_model_cached(model_dir: Path, model_size: str) -> bool:
    if not model_dir.exists():
        return False
    # faster-whisper stores model artifacts under nested folders
    patterns = (f"*{model_size}*", "model.bin", "config.json")
    for pattern in patterns:
        if list(model_dir.rglob(pattern)):
            return True
    return any(model_dir.iterdir()) if model_dir.is_dir() else False


def resolve_whisper_device(config: WhisperConfig) -> tuple[str, str]:
    if config.device.lower() != "cuda":
        return "cpu", "int8"

    try:
        import torch

        if torch.cuda.is_available():
            return "cuda", config.compute_type
    except ImportError:
        pass
    return "cpu", "int8"


class WhisperModelManager:
    """Ensure faster-whisper and the medium model are ready."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._model = None

    @property
    def model_dir(self) -> Path:
        path = self._config.whisper_model_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ensure_ready(self) -> None:
        ensure_faster_whisper()
        self._load_model()

    def get_model(self):
        if self._model is None:
            self.ensure_ready()
        return self._model

    def _load_model(self) -> None:
        from faster_whisper import WhisperModel

        whisper_cfg = self._config.whisper
        device, compute_type = resolve_whisper_device(whisper_cfg)
        model_size = whisper_cfg.model_size

        if model_size != "medium":
            raise ValueError("Whisper model size must be 'medium'.")

        try:
            self._model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
                download_root=str(self.model_dir),
            )
        except Exception as exc:
            raise ModelDownloadError(
                f"Failed to load Whisper '{model_size}' model: {exc}"
            ) from exc
