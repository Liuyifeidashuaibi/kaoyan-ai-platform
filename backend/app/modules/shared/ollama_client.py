"""
本地 Ollama 轻量调用 — 用于生词 AI 补全、英文纠错（不上传外网）。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


async def ollama_chat_json(
    system: str,
    user: str,
    *,
    model: str | None = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    settings = get_settings()
    base = settings.ollama_base_url.rstrip("/")
    model_name = model or settings.ollama_text_model
    payload = {
        "model": model_name,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {"temperature": 0.1, "num_predict": 1024},
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
        res = await client.post(f"{base}/api/chat", json=payload)
        res.raise_for_status()
        content = res.json().get("message", {}).get("content", "")
    return _extract_json(content)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    logger.warning("Ollama 返回非 JSON: %s", text[:200])
    return {}
