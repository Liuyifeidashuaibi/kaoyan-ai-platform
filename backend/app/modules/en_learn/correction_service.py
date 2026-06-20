"""
英文拼写/语法纠错 — 本地 Ollama 千问，返回 error_list 与修正文本。
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.modules.en_learn.schemas import ErrorItem
from app.modules.shared.ollama_client import ollama_chat_json

logger = logging.getLogger(__name__)


async def correct_english(text: str) -> tuple[str, list[ErrorItem]]:
    """校验英文并输出修正标准英文 + 错误列表（字符位置）。"""
    stripped = text.strip()
    if not stripped:
        return "", []

    system = (
        "你是考研英语纠错助手。检查拼写与语法，输出严格 JSON（无 markdown）。"
        "字段：corrected_text（完整修正英文）、errors 数组，每项含 word、correction、start、end。"
        "start/end 为 corrected_text 中被修正词的位置；若无错误 errors=[]，corrected_text 与原文相同。"
    )
    user = f"请纠错：\n{stripped}"

    try:
        data = await ollama_chat_json(system, user, timeout=180.0)
    except Exception as exc:
        logger.warning("英文纠错失败，回退原文: %s", exc)
        return stripped, []

    corrected = (data.get("corrected_text") or stripped).strip()
    errors_raw = data.get("errors") or data.get("error_list") or []
    errors = _normalize_errors(corrected, errors_raw, stripped)
    return corrected or stripped, errors


def _normalize_errors(
    corrected: str,
    raw: list[Any],
    original: str,
) -> list[ErrorItem]:
    items: list[ErrorItem] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        word = str(item.get("word") or "").strip()
        correction = str(item.get("correction") or "").strip()
        if not word or not correction or word == correction:
            continue
        start = item.get("start")
        end = item.get("end")
        if not isinstance(start, int) or not isinstance(end, int):
            pos = corrected.lower().find(correction.lower())
            if pos < 0:
                pos = original.lower().find(word.lower())
            if pos < 0:
                continue
            start, end = pos, pos + len(correction)
        items.append(
            ErrorItem(word=word, correction=correction, start=start, end=end)
        )
    return items


def align_errors_to_original(
    original: str, corrected: str, errors: list[ErrorItem]
) -> list[ErrorItem]:
    """将纠错位置映射回原文展示（简单词级对齐）。"""
    if original == corrected or not errors:
        return errors
    mapped: list[ErrorItem] = []
    for err in errors:
        idx = original.lower().find(err.word.lower())
        if idx >= 0:
            mapped.append(
                ErrorItem(
                    word=err.word,
                    correction=err.correction,
                    start=idx,
                    end=idx + len(err.word),
                )
            )
        else:
            mapped.append(err)
    return mapped
