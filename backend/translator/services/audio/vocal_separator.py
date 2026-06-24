from __future__ import annotations

import importlib.util
import subprocess
import sys
import uuid
from pathlib import Path

import numpy as np
import soundfile as sf

from translator.core.exceptions import DependencyMissingError, FileProcessingError
from translator.utils.config import AppConfig


def is_demucs_installed() -> bool:
    return importlib.util.find_spec("demucs") is not None


def install_demucs() -> None:
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "demucs>=4.0.0",
                "soundfile>=0.12",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.CalledProcessError as exc:
        output = (exc.stderr or exc.stdout or "").strip()
        raise DependencyMissingError(
            f"Failed to install demucs automatically: {output}"
        ) from exc


def ensure_demucs() -> None:
    if not is_demucs_installed():
        install_demucs()
    if not is_demucs_installed():
        raise DependencyMissingError("demucs installation did not succeed.")


def resolve_demucs_device(config_device: str) -> str:
    if config_device.lower() != "cuda":
        return "cpu"
    import torch  # lazy: only needed when demucs is active

    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _resample_mono(data: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate:
        return data
    if data.ndim == 1:
        data = data[:, np.newaxis]
    source_len = data.shape[0]
    target_len = max(1, int(round(source_len * target_rate / source_rate)))
    x_old = np.linspace(0.0, 1.0, source_len)
    x_new = np.linspace(0.0, 1.0, target_len)
    channels = []
    for channel in range(data.shape[1]):
        channels.append(np.interp(x_new, x_old, data[:, channel]))
    return np.stack(channels, axis=1)


class VocalSeparator:
    """Separate vocals from mixed audio using demucs before Whisper."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._model = None
        self._model_name: str | None = None

    def separate(self, audio_path: Path) -> Path:
        video_cfg = self._config.video
        if not video_cfg.vocal_separation:
            return audio_path

        import torch  # lazy: only needed when demucs is active
        from demucs.apply import apply_model
        from demucs.audio import convert_audio

        ensure_demucs()
        audio_path = audio_path.resolve()
        device = resolve_demucs_device(video_cfg.demucs_device)
        model_name = video_cfg.demucs_model
        model = self._get_model(model_name)

        try:
            data, sample_rate = sf.read(str(audio_path), always_2d=True)
            waveform = torch.from_numpy(data.T).float()
        except Exception as exc:
            raise FileProcessingError(
                f"Failed to load audio for demucs: {exc}"
            ) from exc

        waveform = convert_audio(
            waveform, sample_rate, model.samplerate, model.audio_channels
        )
        reference = waveform.mean(0)
        waveform = (waveform - reference.mean()) / (reference.std() + 1e-8)

        with torch.no_grad():
            sources = apply_model(
                model,
                waveform[None],
                device=device,
                shifts=video_cfg.demucs_shifts,
                split=True,
                overlap=0.25,
                progress=False,
            )[0]

        sources = sources * reference.std() + reference.mean()
        vocals = sources[model.sources.index("vocals")].cpu().numpy().T

        target_rate = self._config.video.audio_sample_rate
        vocals = _resample_mono(vocals, model.samplerate, target_rate)

        final_path = (
            self._config.cache_dir
            / "audio"
            / f"{audio_path.stem}_vocals_{uuid.uuid4().hex[:8]}.wav"
        )
        final_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(final_path), vocals, target_rate)
        return final_path

    def _get_model(self, model_name: str):
        from demucs.pretrained import get_model  # lazy

        if self._model is None or self._model_name != model_name:
            self._model = get_model(model_name)
            self._model.eval()
            self._model_name = model_name
        return self._model
