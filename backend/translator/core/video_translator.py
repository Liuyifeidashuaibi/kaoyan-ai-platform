from __future__ import annotations

from pathlib import Path

from translator.core.exceptions import ModelNotFoundError, TranslationFailedError
from translator.core.text_translator import TextTranslator
from translator.core.types import (
    SubtitleCue,
    SubtitleOutputMode,
    TranslationDomain,
    TranslationMode,
    VideoTranslationResult,
)
from translator.models.base import ModelProvider
from translator.services.audio.pipeline import AudioPipeline
from translator.services.subtitle.formatter import normalize_cues
from translator.services.whisper.manager import WhisperModelManager
from translator.services.whisper.transcriber import WhisperTranscriber
from translator.utils.config import AppConfig


class VideoTranslator:
    """Video -> audio pipeline -> Whisper medium -> optional translation."""

    def __init__(
        self,
        provider: ModelProvider,
        config: AppConfig,
        text_translator: TextTranslator,
        whisper_manager: WhisperModelManager | None = None,
    ) -> None:
        self._provider = provider
        self._config = config
        self._text_translator = text_translator
        self._whisper_manager = whisper_manager or WhisperModelManager(config)
        self._audio_pipeline = AudioPipeline(config)
        self._transcriber = WhisperTranscriber(self._whisper_manager, config)

    def translate(
        self,
        video_path: Path,
        domain: TranslationDomain,
        output_mode: SubtitleOutputMode = SubtitleOutputMode.BILINGUAL,
    ) -> VideoTranslationResult:
        needs_translation = output_mode != SubtitleOutputMode.ORIGINAL
        if needs_translation and not self._provider.is_available():
            raise ModelNotFoundError(
                "Qwen model provider is not available for subtitle translation."
            )

        video_path = video_path.resolve()
        self._whisper_manager.ensure_ready()

        cleanup: list[Path] = []
        try:
            whisper_audio, cleanup = self._audio_pipeline.prepare(video_path)
            cues, language = self._transcriber.transcribe(str(whisper_audio))
            if not cues:
                raise TranslationFailedError(
                    "No speech detected in video audio after transcription."
                )

            cues = normalize_cues(
                cues,
                max_chars_per_line=self._config.subtitle.max_chars_per_line,
                max_lines=self._config.subtitle.max_lines,
            )

            if needs_translation:
                cues = self._translate_cues(cues, domain)

            return VideoTranslationResult(
                source_name=video_path.name,
                cues=cues,
                detected_language=language,
                mode=output_mode,
            )
        except TranslationFailedError:
            raise
        except Exception as exc:
            raise TranslationFailedError(f"Video translation failed: {exc}") from exc
        finally:
            for path in cleanup:
                if path.exists():
                    path.unlink(missing_ok=True)

    def _translate_cues(
        self, cues: list[SubtitleCue], domain: TranslationDomain
    ) -> list[SubtitleCue]:
        if not cues:
            return []

        batch_size = 10
        translated: list[SubtitleCue] = []
        for offset in range(0, len(cues), batch_size):
            batch = cues[offset : offset + batch_size]
            batch_map = self._translate_cue_batch(batch, domain)
            for cue in batch:
                translation = batch_map.get(cue.index, cue.text)
                translated.append(
                    SubtitleCue(
                        index=cue.index,
                        start=cue.start,
                        end=cue.end,
                        text=cue.text,
                        translation=translation,
                    )
                )
        return translated

    def _translate_cue_batch(
        self, cues: list[SubtitleCue], domain: TranslationDomain
    ) -> dict[int, str]:
        if len(cues) == 1:
            result = self._text_translator.translate(
                cues[0].text,
                mode=TranslationMode.FULL,
                domain=domain,
                source_name=f"subtitle-{cues[0].index}",
            )
            return {cues[0].index: (result.full_text or cues[0].text).strip()}

        numbered_lines = [f"[{cue.index}] {cue.text}" for cue in cues]
        payload = "\n".join(numbered_lines)
        system = (
            "You translate subtitle lines into natural Chinese. "
            "Keep the [id] prefix on each line and translate only the text after it. "
            "Return the same number of lines in the same order."
        )
        user = "Translate the following subtitle lines:"
        raw = self._provider.translate_text(payload, system, user)

        mapping: dict[int, str] = {}
        for line in raw.splitlines():
            line = line.strip()
            if not line.startswith("["):
                continue
            closing = line.find("]")
            if closing <= 1:
                continue
            try:
                cue_id = int(line[1:closing])
            except ValueError:
                continue
            mapping[cue_id] = line[closing + 1 :].strip()

        if len(mapping) < len(cues):
            for cue in cues:
                if cue.index not in mapping:
                    single = self._text_translator.translate(
                        cue.text,
                        mode=TranslationMode.FULL,
                        domain=domain,
                        source_name=f"subtitle-{cue.index}",
                    )
                    mapping[cue.index] = (single.full_text or cue.text).strip()
        return mapping
