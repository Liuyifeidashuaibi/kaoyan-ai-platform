from __future__ import annotations

import re
from pathlib import Path

from translator.core.types import SubtitleCue
from translator.services.audio.duration import get_audio_duration
from translator.services.whisper.manager import WhisperModelManager
from translator.services.subtitle.segmenter import resplit_cues, resplit_cues_from_words
from translator.utils.config import AppConfig


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\s']", "", text.lower()).strip()


def _is_prompt_echo(text: str, prompt: str | None) -> bool:
    if not prompt or not text.strip():
        return False
    text_n = _normalize(text)
    prompt_n = _normalize(prompt)
    if not text_n or not prompt_n:
        return False
    if text_n in prompt_n or prompt_n in text_n:
        return True
    text_words = set(text_n.split())
    prompt_words = set(prompt_n.split())
    if not text_words:
        return False
    overlap = len(text_words & prompt_words) / len(text_words)
    return overlap >= 0.8


def _score_cues(cues: list[SubtitleCue], prompt: str | None) -> float:
    if not cues:
        return 0.0
    if any(_is_prompt_echo(cue.text, prompt) for cue in cues):
        return 0.0
    text_len = sum(len(cue.text) for cue in cues)
    return len(cues) * 15 + text_len


class WhisperTranscriber:
    def __init__(self, manager: WhisperModelManager, config: AppConfig) -> None:
        self._manager = manager
        self._config = config

    def transcribe(self, audio_path: str) -> tuple[list[SubtitleCue], str | None]:
        whisper_cfg = self._config.whisper
        duration = get_audio_duration(Path(audio_path))

        primary = self._run_pass(audio_path, use_prompt=True)
        secondary = self._run_pass(
            audio_path,
            use_prompt=False,
            language_override="en",
        )

        candidates = [primary, secondary]
        best_cues, best_lang = max(
            candidates,
            key=lambda item: _score_cues(item[0], whisper_cfg.initial_prompt),
        )

        if not best_cues and duration > 5:
            tertiary = self._run_pass(
                audio_path,
                use_prompt=False,
                language_override="en",
                disable_vad=True,
            )
            if _score_cues(tertiary[0], None) > 0:
                return tertiary

        return best_cues, best_lang

    def _run_pass(
        self,
        audio_path: str,
        *,
        use_prompt: bool,
        language_override: str | None = None,
        disable_vad: bool = False,
    ) -> tuple[list[SubtitleCue], str | None]:
        model = self._manager.get_model()
        whisper_cfg = self._config.whisper
        subtitle_cfg = self._config.subtitle

        vad_filter = whisper_cfg.vad_filter and not disable_vad
        vad_parameters = None
        if vad_filter:
            vad_parameters = {
                "min_silence_duration_ms": whisper_cfg.vad_min_silence_ms,
            }

        transcribe_kwargs = {
            "beam_size": whisper_cfg.beam_size,
            "best_of": whisper_cfg.best_of,
            "temperature": whisper_cfg.temperature,
            "language": language_override or whisper_cfg.language,
            "initial_prompt": whisper_cfg.initial_prompt if use_prompt else None,
            "vad_filter": vad_filter,
            "vad_parameters": vad_parameters,
            "word_timestamps": whisper_cfg.word_timestamps,
            "no_speech_threshold": whisper_cfg.no_speech_threshold,
            "compression_ratio_threshold": whisper_cfg.compression_ratio_threshold,
            "log_prob_threshold": whisper_cfg.log_prob_threshold,
            "condition_on_previous_text": whisper_cfg.condition_on_previous_text,
        }
        if whisper_cfg.hallucination_silence_threshold is not None:
            transcribe_kwargs["hallucination_silence_threshold"] = (
                whisper_cfg.hallucination_silence_threshold
            )

        segments, info = model.transcribe(audio_path, **transcribe_kwargs)

        segment_list = list(segments)
        prompt = whisper_cfg.initial_prompt if use_prompt else None

        if whisper_cfg.word_timestamps:
            cues = resplit_cues_from_words(
                segment_list,
                max_gap=subtitle_cfg.word_max_gap,
                max_duration=subtitle_cfg.word_max_duration,
                max_chars=subtitle_cfg.max_cue_chars,
            )
        else:
            cues = [
                SubtitleCue(
                    index=index,
                    start=segment.start,
                    end=segment.end,
                    text=segment.text.strip(),
                )
                for index, segment in enumerate(segment_list, start=1)
                if segment.text.strip()
            ]

        cues = [cue for cue in cues if not _is_prompt_echo(cue.text, prompt)]
        cues = resplit_cues(
            cues,
            max_duration=subtitle_cfg.max_cue_duration,
            max_chars=subtitle_cfg.max_cue_chars,
        )
        cues = [
            SubtitleCue(
                index=index,
                start=cue.start,
                end=cue.end,
                text=cue.text,
                translation=cue.translation,
            )
            for index, cue in enumerate(cues, start=1)
        ]

        language = getattr(info, "language", None)
        return cues, language
