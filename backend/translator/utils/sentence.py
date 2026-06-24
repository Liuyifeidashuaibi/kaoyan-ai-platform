from __future__ import annotations

import re

from translator.core.types import SentencePair

_SENTENCE_PATTERN = re.compile(
    r"(?<=[.!?])\s+(?=[A-Z\"'(])|(?<=[.!?])\s*\n+"
)

# Model often echoes the batch instruction in Chinese — never treat as translation.
_INSTRUCTION_LINE_RE = re.compile(
    r"(以下\s*\d+\s*个|逐句|双语|英文句子|句间空行|禁止|输出与输入无关|英译|译文|对照)"
)


def split_sentences(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    parts = _SENTENCE_PATTERN.split(text)
    sentences = [part.strip() for part in parts if part.strip()]
    return sentences or [text]


def contains_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def is_instruction_line(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    return bool(_INSTRUCTION_LINE_RE.search(stripped))


def is_valid_bilingual_target(source: str, target: str) -> bool:
    src = source.strip()
    tgt = target.strip()
    if not src or not tgt:
        return False
    if is_instruction_line(tgt):
        return False
    if tgt == src:
        return False
    if not contains_chinese(tgt):
        return False
    if contains_chinese(src) and not contains_chinese(tgt):
        return False
    return True


def _filter_valid_pairs(pairs: list[SentencePair]) -> list[SentencePair]:
    return [
        p
        for p in pairs
        if is_valid_bilingual_target(p.source, p.target)
    ]


def parse_bilingual_response(raw: str) -> list[SentencePair]:
    """Parse bilingual output into one pair per sentence."""
    text = raw.strip()
    if not text:
        return []

    pairs: list[SentencePair] = []
    for block in re.split(r"\n\s*\n", text):
        lines = [
            line.strip()
            for line in block.splitlines()
            if line.strip() and not is_instruction_line(line.strip())
        ]
        if len(lines) == 2 and is_valid_bilingual_target(lines[0], lines[1]):
            pairs.append(SentencePair(source=lines[0], target=lines[1]))
        elif len(lines) >= 4 and len(lines) % 2 == 0:
            for i in range(0, len(lines), 2):
                if is_valid_bilingual_target(lines[i], lines[i + 1]):
                    pairs.append(SentencePair(source=lines[i], target=lines[i + 1]))

        elif len(lines) == 1 and " | " in lines[0]:
            source, target = lines[0].split(" | ", 1)
            if is_valid_bilingual_target(source, target):
                pairs.append(
                    SentencePair(source=source.strip(), target=target.strip())
                )

    if pairs:
        return pairs

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not is_instruction_line(line.strip())
    ]
    return _filter_valid_pairs(_parse_alternating_lines(lines))


def parse_bilingual_for_sentences(
    sentences: list[str], raw: str
) -> list[SentencePair]:
    """Map model output onto known sentences; reject prompt echoes and EN echoes."""
    if not sentences:
        return []

    text = raw.strip()
    if not text:
        return []

    pairs = parse_bilingual_response(text)
    if len(pairs) == len(sentences) and all(
        is_valid_bilingual_target(src, pair.target)
        for src, pair in zip(sentences, pairs)
    ):
        return [
            SentencePair(source=src, target=pair.target.strip())
            for src, pair in zip(sentences, pairs)
        ]

    chinese_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
        and contains_chinese(line.strip())
        and not is_instruction_line(line.strip())
    ]
    if len(chinese_lines) == len(sentences):
        mapped = [
            SentencePair(source=src, target=zh)
            for src, zh in zip(sentences, chinese_lines)
            if is_valid_bilingual_target(src, zh)
        ]
        if len(mapped) == len(sentences):
            return mapped

    if pairs:
        by_source = {
            p.source.strip(): p.target.strip()
            for p in pairs
            if is_valid_bilingual_target(p.source, p.target)
        }
        mapped = []
        for src in sentences:
            target = by_source.get(src.strip(), "")
            if target and is_valid_bilingual_target(src, target):
                mapped.append(SentencePair(source=src, target=target))
        if len(mapped) == len(sentences):
            return mapped

    return []


def _parse_alternating_lines(lines: list[str]) -> list[SentencePair]:
    pairs: list[SentencePair] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if contains_chinese(line) and pairs and not contains_chinese(pairs[-1].source):
            candidate = SentencePair(source=pairs[-1].source, target=line)
            if is_valid_bilingual_target(candidate.source, candidate.target):
                pairs[-1] = candidate
            i += 1
            continue
        if (
            i + 1 < len(lines)
            and not contains_chinese(line)
            and contains_chinese(lines[i + 1])
            and is_valid_bilingual_target(line, lines[i + 1])
        ):
            pairs.append(SentencePair(source=line, target=lines[i + 1]))
            i += 2
            continue
        i += 1
    return pairs


def align_pairs_to_sentences(
    sentences: list[str], pairs: list[SentencePair]
) -> list[SentencePair]:
    """Backward-compatible wrapper around sentence-aware parsing."""
    if not sentences:
        return pairs
    if not pairs:
        return []
    raw = "\n\n".join(f"{p.source}\n{p.target}" for p in pairs if p.target.strip())
    return parse_bilingual_for_sentences(sentences, raw)
