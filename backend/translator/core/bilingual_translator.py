from __future__ import annotations

from translator.core.types import TranslationDomain, SentencePair
from translator.models.ollama.provider import OllamaProvider
from translator.prompts import bilingual as bilingual_prompts
from translator.prompts import full as full_prompts
from translator.utils.config import AppConfig
from translator.utils.sentence import (
    contains_chinese,
    is_valid_bilingual_target,
    parse_bilingual_for_sentences,
    parse_bilingual_response,
    split_sentences,
)
from translator.utils.word_split import count_english_words


def translate_bilingual_text(
    provider,
    config: AppConfig,
    text: str,
    domain: TranslationDomain,
    target: str,
) -> list[SentencePair]:
    """Sentence-level bilingual with full-mode fallback for long or incomplete outputs."""
    sentences = split_sentences(text)
    if not sentences:
        return []

    system = bilingual_prompts.build_bilingual_system_prompt(domain, target)
    batch_size = max(1, config.translation.bilingual_sentence_batch_size)
    pairs: list[SentencePair] = []

    for offset in range(0, len(sentences), batch_size):
        batch = sentences[offset : offset + batch_size]
        batch_pairs = _translate_batch(provider, config, system, batch, domain, target)
        pairs.extend(batch_pairs)

    return pairs


def _translate_batch(
    provider,
    config: AppConfig,
    system: str,
    batch: list[str],
    domain: TranslationDomain,
    target_lang: str,
) -> list[SentencePair]:
    if any(_should_use_full_target(sentence, config) for sentence in batch):
        return [
            pair
            for sentence in batch
            if (pair := _translate_with_full_target(provider, domain, target_lang, sentence))
        ]

    user = bilingual_prompts.build_bilingual_batch_user_prompt(batch)
    payload = "\n\n".join(batch)
    raw = _translate_bilingual_call(provider, config, system, user, payload)
    batch_pairs = parse_bilingual_for_sentences(batch, raw)
    if len(batch_pairs) == len(batch) and all(
        is_translation_complete(src, pair.target)
        for src, pair in zip(batch, batch_pairs)
    ):
        return batch_pairs

    return [
        pair
        for sentence in batch
        if (pair := _translate_single_sentence(
            provider, config, system, sentence, domain, target_lang
        ))
    ]


def _translate_single_sentence(
    provider,
    config: AppConfig,
    system: str,
    sentence: str,
    domain: TranslationDomain,
    target_lang: str,
) -> SentencePair | None:
    if _should_use_full_target(sentence, config):
        return _translate_with_full_target(provider, domain, target_lang, sentence)

    user = bilingual_prompts.build_bilingual_batch_user_prompt([sentence])
    raw = _translate_bilingual_call(provider, config, system, user, sentence)
    parsed = parse_bilingual_for_sentences([sentence], raw)
    if parsed and is_translation_complete(sentence, parsed[0].target):
        return SentencePair(source=sentence, target=parsed[0].target.strip())

    response_pairs = parse_bilingual_response(raw)
    for pair in response_pairs:
        if is_translation_complete(sentence, pair.target):
            return SentencePair(source=sentence, target=pair.target.strip())

    return _translate_with_full_target(provider, domain, target_lang, sentence)


def _translate_with_full_target(
    provider,
    domain: TranslationDomain,
    target_lang: str,
    sentence: str,
) -> SentencePair | None:
    translated = _translate_full_sentence(provider, domain, target_lang, sentence)
    if translated and is_translation_complete(sentence, translated):
        return SentencePair(source=sentence, target=translated)
    if translated and is_valid_bilingual_target(sentence, translated):
        return SentencePair(source=sentence, target=translated)
    return None


def _should_use_full_target(sentence: str, config: AppConfig) -> bool:
    limit = config.translation.bilingual_single_pass_sentence_limit
    return count_english_words(sentence) > limit


def is_translation_complete(source: str, target: str) -> bool:
    """Reject partial zh outputs that only cover the opening clause of a long sentence."""
    if not is_valid_bilingual_target(source, target):
        return False

    src_words = count_english_words(source)
    if src_words <= 15:
        return True

    tgt_chars = len("".join(target.split()))
    min_chars = max(16, int(src_words * 1.4))
    if tgt_chars < min_chars:
        return False

    if target.rstrip().endswith(("，", ",")) and tgt_chars < int(src_words * 2.2):
        return False

    return True


def _translate_full_sentence(
    provider,
    domain: TranslationDomain,
    target_lang: str,
    sentence: str,
) -> str:
    system = full_prompts.build_full_system_prompt(domain, target_lang)
    user = full_prompts.build_full_user_prompt()
    translated = provider.translate_text(sentence, system, user).strip()
    if not translated or not contains_chinese(translated):
        return ""
    return translated


def _translate_bilingual_call(
    provider,
    config: AppConfig,
    system: str,
    user: str,
    text: str,
) -> str:
    if config.translation.use_draft_for_bilingual and isinstance(
        provider, OllamaProvider
    ):
        return provider.translate_text_draft(text, system, user)
    return provider.translate_text(text, system, user)
