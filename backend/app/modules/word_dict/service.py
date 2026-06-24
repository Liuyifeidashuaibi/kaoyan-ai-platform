"""
ECDICT 词库查询服务 — 本地优先，AI 补全后永久写入 word_lib。
"""

from __future__ import annotations

import logging
import re
from typing import Literal

from sqlalchemy import collate
from sqlalchemy.orm import Session

from app.modules.shared.ollama_client import ollama_chat_json
from app.modules.word_dict.models import WordLibEntry
from app.modules.word_dict.schemas import WordBrief, WordDetail

logger = logging.getLogger(__name__)

_KAOYAN_TAGS = ("zk", "gk", "cet4", "cet6", "ky", "考研", "ielts", "toefl", "gre")

# ECDICT pos 缩写 → 学习模式展示
_POS_LABELS: dict[str, str] = {
    "n": "n.",
    "v": "v.",
    "vt": "vt.",
    "vi": "vi.",
    "a": "adj.",
    "adj": "adj.",
    "adv": "adv.",
    "prep": "prep.",
    "conj": "conj.",
    "pron": "pron.",
    "art": "art.",
    "int": "int.",
    "num": "num.",
    "aux": "aux.",
}

# 词性释义行：n. / v. / adj. 等
_LEARN_LINE = re.compile(
    r"^(?:n\.|v\.|vt\.|vi\.|a\.|adj\.|adv\.|prep\.|conj\.|pron\.|art\.|int\.|num\.|aux\.|pl\.|sing\.)",
    re.I,
)
# 领域标签行：[计] [医] [俚] 等
_DOMAIN_TAG_LINE = re.compile(r"^\[[^\]]+\]")
_POS_PREFIX = re.compile(
    r"^(?:n\.|v\.|vt\.|vi\.|a\.|adj\.|adv\.|prep\.|conj\.|pron\.|art\.|int\.|num\.|aux\.|pl\.|sing\.)\s*",
    re.I,
)


def _normalize_word(word: str) -> str:
    return re.sub(r"[^a-zA-Z'-]", "", word.strip().lower())


def _first_line(text: str | None, max_len: int = 120) -> str:
    if not text:
        return ""
    line = text.strip().splitlines()[0].strip()
    if len(line) > max_len:
        return line[: max_len - 1] + "…"
    return line


def _parse_pos_labels(pos_raw: str | None) -> str | None:
    """ECDICT pos 如 n:100/v:6 → n. / v.（去掉语料频次数字）。"""
    if not pos_raw:
        return None
    labels: list[str] = []
    for part in pos_raw.split("/"):
        key = part.split(":")[0].strip().lower()
        label = _POS_LABELS.get(key)
        if label and label not in labels:
            labels.append(label)
    return " / ".join(labels) if labels else None


def _has_cjk(text: str | None) -> bool:
    return bool(text and re.search(r"[\u4e00-\u9fff]", text))


def _gloss_from_line(line: str) -> str:
    """去掉 [计] 标签与 n./v. 前缀，保留中文释义。"""
    text = re.sub(r"^\[[^\]]+\]\s*", "", line.strip())
    text = _POS_PREFIX.sub("", text).strip()
    return text or line.strip()


def _learning_translation_lines(translation: str | None) -> list[str]:
    """提取中文释义行（含仅存在于 [计] 等领域标签行中的释义）。"""
    if not translation:
        return []
    kept: list[str] = []
    for ln in translation.splitlines():
        line = ln.strip()
        if not line:
            continue
        if _LEARN_LINE.match(line):
            kept.append(line)
            continue
        if _DOMAIN_TAG_LINE.match(line):
            chinese = _gloss_from_line(line)
            if _has_cjk(chinese):
                kept.append(chinese)
            continue
        if _has_cjk(line):
            kept.append(line)
    return kept


def _pick_kaoyan_gloss(entry: WordLibEntry) -> str:
    if entry.kaoyan_gloss:
        gloss = _first_line(entry.kaoyan_gloss, 160)
        if gloss and _has_cjk(gloss):
            return _first_line(_gloss_from_line(gloss), 160)
    lines = _learning_translation_lines(entry.translation)
    if lines:
        return _first_line(_gloss_from_line(lines[0]), 160)
    if entry.definition and _has_cjk(entry.definition):
        return _first_line(entry.definition, 160)
    return ""


def _parse_pos(entry: WordLibEntry) -> str | None:
    return _parse_pos_labels(entry.pos)


def _format_translation_for_detail(entry: WordLibEntry) -> str | None:
    lines = _learning_translation_lines(entry.translation)
    if not lines:
        return None
    primary = _pick_kaoyan_gloss(entry)
    extra = [ln for ln in lines if _gloss_from_line(ln) != primary]
    if not extra:
        return None
    return "\n".join(extra[:6])


def _lookup_local(db: Session, word: str) -> WordLibEntry | None:
    norm = _normalize_word(word)
    if not norm:
        return None
    # 使用 NOCASE 索引；func.lower(word) 会导致 340 万行全表扫描（~500ms–1.5s）
    return (
        db.query(WordLibEntry)
        .filter(collate(WordLibEntry.word, "NOCASE") == norm)
        .first()
    )


class WordDictService:
    """双层查询：word_lib → Ollama 考研释义 → 写回缓存。"""

    async def query(
        self,
        db: Session,
        word: str,
        mode: Literal["hover", "detail"] = "hover",
    ) -> WordBrief | WordDetail | None:
        norm = _normalize_word(word)
        if not norm or len(norm) < 2:
            return None

        entry = _lookup_local(db, norm)
        if entry:
            gloss = _pick_kaoyan_gloss(entry)
            source = "ai_cache" if entry.ai_generated else "local"
            if mode == "hover":
                if not gloss.strip():
                    return WordBrief(
                        word=entry.word,
                        phonetic=entry.phonetic,
                        pos=_parse_pos(entry),
                        gloss="",
                        source="missing",
                    )
                return WordBrief(
                    word=entry.word,
                    phonetic=entry.phonetic,
                    pos=_parse_pos(entry),
                    gloss=gloss,
                    source=source,
                )
            if gloss.strip() or not entry.ai_generated:
                return self._to_detail(entry, source)
            # ai_cache 无中文释义时，detail 模式重新 AI 补全

        # hover 仅本地库，避免 Ollama 阻塞导致长时间「查询中」
        if mode == "hover":
            return WordBrief(
                word=norm,
                phonetic=None,
                pos=None,
                gloss="",
                source="missing",
            )

        ai_data = await self._ai_lookup(norm)
        if not ai_data:
            return None

        entry = self._persist_ai_entry(db, norm, ai_data)
        if mode == "hover":
            return WordBrief(
                word=entry.word,
                phonetic=entry.phonetic,
                pos=_parse_pos(entry),
                gloss=_pick_kaoyan_gloss(entry),
                source="ai",
            )
        return self._to_detail(entry, "ai")

    def _to_detail(self, entry: WordLibEntry, source: str) -> WordDetail:
        phrases: list[str] = []
        if entry.detail:
            phrases = [ln.strip() for ln in entry.detail.splitlines() if ln.strip()][:8]
        return WordDetail(
            word=entry.word,
            phonetic=entry.phonetic,
            pos=_parse_pos_labels(entry.pos),
            translation=_format_translation_for_detail(entry),
            definition=None,
            tag=None,
            collins=None,
            oxford=None,
            exchange=None,
            detail=entry.detail,
            kaoyan_gloss=entry.kaoyan_gloss or _pick_kaoyan_gloss(entry),
            kaoyan_phrases=phrases,
            source=source,
        )

    async def _ai_lookup(self, word: str) -> dict | None:
        system = (
            "你是考研英语词典助手。仅输出 JSON，不要 markdown。"
            "释义只保留考研/四六级/学术阅读常见含义，过滤口语俚语与古义。"
        )
        user = (
            f'解析单词 "{word}"，返回 JSON：'
            '{"phonetic":"国际音标","pos":"词性缩写如 n./v.","translation":"多行中文释义",'
            '"kaoyan_gloss":"一行考研核心释义","kaoyan_phrases":["真题搭配1","搭配2"],'
            '"tag":"ky cet4 等标签"}'
        )
        try:
            data = await ollama_chat_json(system, user)
            if not data.get("kaoyan_gloss") and not data.get("translation"):
                return None
            return data
        except Exception as exc:
            logger.warning("生词 AI 解析失败 %s: %s", word, exc)
            return None

    def _persist_ai_entry(self, db: Session, word: str, data: dict) -> WordLibEntry:
        phrases = data.get("kaoyan_phrases") or []
        detail = "\n".join(phrases) if isinstance(phrases, list) else str(phrases)
        entry = WordLibEntry(
            word=word,
            phonetic=data.get("phonetic"),
            translation=data.get("translation"),
            pos=data.get("pos"),
            tag=data.get("tag") or "ky ai",
            kaoyan_gloss=data.get("kaoyan_gloss") or _first_line(data.get("translation", "")),
            detail=detail or None,
            ai_generated=1,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry


_service: WordDictService | None = None


def get_word_dict_service() -> WordDictService:
    global _service
    if _service is None:
        _service = WordDictService()
    return _service
