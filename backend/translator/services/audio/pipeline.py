from __future__ import annotations

import logging
from pathlib import Path

from translator.services.audio.enhancer import AudioEnhancer
from translator.services.audio.extractor import AudioExtractor
from translator.services.audio.vocal_separator import VocalSeparator
from translator.utils.config import AppConfig

logger = logging.getLogger(__name__)


class AudioPipeline:
    """Extract → demucs vocals (with fallback) → resample/enhance for Whisper."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._extractor = AudioExtractor(config)
        self._separator = VocalSeparator(config)
        self._enhancer = AudioEnhancer(config)

    def prepare(self, video_path: Path) -> tuple[Path, list[Path]]:
        """Return whisper-ready audio and temp files to clean up."""
        cleanup: list[Path] = []
        raw = self._extractor.extract(video_path)
        cleanup.append(raw)

        separated = self._separate_with_fallback(raw)
        if separated != raw:
            cleanup.append(separated)

        final = self._enhancer.enhance(separated)
        if final != separated:
            cleanup.append(final)

        return final, cleanup

    def _separate_with_fallback(self, audio_path: Path) -> Path:
        if not self._config.video.vocal_separation:
            return audio_path
        try:
            return self._separator.separate(audio_path)
        except Exception as exc:
            logger.warning("demucs vocal separation failed, using raw audio: %s", exc)
            return audio_path
