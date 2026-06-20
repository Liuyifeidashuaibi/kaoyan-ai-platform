"""
Redis Key 前缀与 TTL — 全部带过期时间，避免永久占用内存。

本地单机 4090 测试环境默认值；可通过 .env 覆盖。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


# --- Key 前缀 ---
PREFIX_SCHOOLS = "kaoyan:schools:"
PREFIX_SCORE_LINES = "kaoyan:score_lines:"
PREFIX_CHAT_QA = "kaoyan:chat_qa:"
PREFIX_TRANSLATOR = "kaoyan:translator:"
PREFIX_MEMBERSHIP = "kaoyan:membership:"
PREFIX_TASK = "kaoyan:task:"


def schools_list_key(page: int, keyword: str | None, tag: str | None, page_size: int) -> str:
    payload = f"list:{page}:{keyword or ''}:{tag or ''}:{page_size}"
    return PREFIX_SCHOOLS + hashlib.md5(payload.encode()).hexdigest()


def school_detail_key(school_id: str) -> str:
    return f"{PREFIX_SCHOOLS}detail:{school_id}"


def score_lines_key(**params: Any) -> str:
    raw = json.dumps(params, sort_keys=True, ensure_ascii=False)
    return PREFIX_SCORE_LINES + hashlib.md5(raw.encode()).hexdigest()


def chat_qa_key(normalized_query_md5: str) -> str:
    return f"{PREFIX_CHAT_QA}{normalized_query_md5}"


def translator_key(kind: str, content_hash: str, **params: Any) -> str:
    raw = json.dumps({"kind": kind, "hash": content_hash, **params}, sort_keys=True)
    return PREFIX_TRANSLATOR + hashlib.md5(raw.encode()).hexdigest()


def membership_quota_key(user_id: str) -> str:
    return f"{PREFIX_MEMBERSHIP}quota:{user_id}"


def task_key(task_id: str) -> str:
    return f"{PREFIX_TASK}{task_id}"


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
