from __future__ import annotations

from translator.core.bilingual_translator import translate_bilingual_text
from translator.core.types import (
    TranslationDomain,
    TranslationMode,
    TranslationResult,
)
from translator.models.base import ModelProvider
from translator.prompts import full as full_prompts
from translator.utils.config import AppConfig
from translator.utils.word_split import split_for_translation


class TextTranslator:
    """Translate plain text with word-count-aware chunking (serial inference)."""

    def __init__(self, provider: ModelProvider, config: AppConfig) -> None:
        self._provider = provider
        self._config = config

    def translate(
        self,
        text: str,
        mode: TranslationMode,
        domain: TranslationDomain,
        source_name: str = "inline-text",
    ) -> TranslationResult:
        target = self._config.translation.target_language
        if mode == TranslationMode.FULL:
            translated = self._translate_full(text, domain, target)
            return TranslationResult(
                mode=mode,
                full_text=translated,
                source_name=source_name,
            )
        pairs = translate_bilingual_text(
            self._provider, self._config, text, domain, target
        )
        return TranslationResult(
            mode=TranslationMode.BILINGUAL,
            pairs=pairs,
            source_name=source_name,
        )

    def _translate_full(
        self, text: str, domain: TranslationDomain, target: str
    ) -> str:
        system = full_prompts.build_full_system_prompt(domain, target)
        user = full_prompts.build_full_user_prompt()
        chunks = self._split_text(text)
        if len(chunks) == 1:
            return self._provider.translate_text(chunks[0], system, user)
        parts = [
            self._provider.translate_text(chunk, system, user) for chunk in chunks
        ]
        return "\n\n".join(part for part in parts if part)

    def _split_text(self, text: str) -> list[str]:
        cfg = self._config.translation
        return split_for_translation(
            text,
            single_pass_word_limit=cfg.single_pass_word_limit,
            max_chunk_words=cfg.max_chunk_words,
        )
