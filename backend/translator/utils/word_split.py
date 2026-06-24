"""English word counting and paragraph/sentence-aware chunking for translation."""

from __future__ import annotations

import re

from translator.utils.sentence import split_sentences

_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def count_english_words(text: str) -> int:
    return len(_WORD_RE.findall(text))


def split_for_translation(
    text: str,
    *,
    single_pass_word_limit: int = 1000,
    max_chunk_words: int = 800,
) -> list[str]:
    """Split long English text into semantic chunks by paragraph and sentence."""
    stripped = text.strip()
    if not stripped:
        return []

    if count_english_words(stripped) <= single_pass_word_limit:
        return [stripped]

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", stripped) if p.strip()]
    chunks: list[str] = []
    current = ""
    current_words = 0

    def flush() -> None:
        nonlocal current, current_words
        if current.strip():
            chunks.append(current.strip())
        current = ""
        current_words = 0

    def append_paragraph(para: str) -> None:
        nonlocal current, current_words
        para_words = count_english_words(para)
        if current and current_words + para_words > max_chunk_words:
            flush()
        current = f"{current}\n\n{para}".strip() if current else para
        current_words += para_words

    for paragraph in paragraphs:
        para_words = count_english_words(paragraph)
        if para_words <= max_chunk_words:
            append_paragraph(paragraph)
            continue

        flush()
        sentences = split_sentences(paragraph)
        block = ""
        block_words = 0
        for sentence in sentences:
            sentence_words = count_english_words(sentence)
            if block and block_words + sentence_words > max_chunk_words:
                chunks.append(block.strip())
                block = sentence
                block_words = sentence_words
            else:
                block = f"{block} {sentence}".strip() if block else sentence
                block_words += sentence_words
        if block.strip():
            chunks.append(block.strip())

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [stripped]
