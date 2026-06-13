"""
Agent 编排 — 串行多模态流水线 + RAG + 降级策略。

顺序：语音 ASR → 图片 OCR → 合并文字 → 缓存 → 向量检索 → LLM 文本生成 →（可选）TTS
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import AsyncGenerator

from app.services.ai_service import get_ai_service
from app.services.media_service import get_media_service
from app.services.rag_service import get_rag_service
from app.services.response_cache import get_response_cache
from app.utils.image_url import ResolvedImage
from app.utils.text_utils import trim_user_query

logger = logging.getLogger(__name__)


@dataclass
class AgentResultMeta:
    """流式结束时的元数据（如 TTS）。"""

    warnings: list[str] = field(default_factory=list)
    audio_base64: str | None = None


async def run_agent_stream(
    query: str,
    history: list[dict] | None = None,
    image: ResolvedImage | None = None,
    *,
    audio_bytes: bytes | None = None,
    audio_filename: str = "audio.wav",
    image_bytes: bytes | None = None,
    enable_tts: bool = False,
    use_history_cache: bool = True,
) -> AsyncGenerator[str, None]:
    """
    多模态 RAG 聊天主流程。yield SSE token 字符串；
    若启用 TTS，在文本流结束后通过特殊 JSON 块返回音频（由 chat_service 转发）。
    """
    media = get_media_service()
    ai = get_ai_service()
    warnings: list[str] = []
    parts: list[str] = []

    # 1. 语音 → 文本
    if audio_bytes:
        try:
            asr_text = await media.transcribe_audio(audio_bytes, audio_filename)
            if asr_text:
                parts.append(asr_text)
        except Exception as exc:
            logger.error("ASR 失败: %s", exc)
            detail = str(exc).strip()
            if "未检测到有效人声" in detail or "语音文件为空" in detail:
                warnings.append(detail)
            else:
                warnings.append("语音解析失败，已保留图片与文字输入")

    # 2. 图片 OCR（仅当上游未预处理；多轮场景由 chat_context 注入）
    if image is not None and "[图片内容]" not in query:
        try:
            ocr_text = await media.extract_image_text(image, image_bytes)
            if ocr_text:
                parts.append(f"[图片内容]\n{ocr_text}")
        except Exception as exc:
            logger.error("视觉 OCR 失败: %s", exc)
            warnings.append("图片解析失败，已保留语音与文字输入")

    # 3. 用户文字
    if query.strip():
        parts.append(query.strip())

    full_query = trim_user_query("\n\n".join(parts), ai.settings.max_query_chars)
    if not full_query:
        yield "\n\n[提示] 请输入文字、上传图片或录制语音后再提问。"
        return

    if warnings:
        yield "⚠️ " + "；".join(warnings) + "\n\n"

    # 4. 高频提问缓存（仅首轮无历史时启用，避免多轮误命中）
    cache = get_response_cache()
    has_history = bool(history)
    if use_history_cache and not has_history:
        cached = cache.get(full_query)
        if cached:
            for ch in cached:
                yield ch
            return

    # 5. RAG 检索（失败则降级为纯 LLM）
    rag_context = ""
    try:
        rag = get_rag_service()
        rag_context = rag.retrieve(full_query) or ""
    except Exception as exc:
        logger.error("RAG 检索失败，降级纯 LLM: %s", exc)

    # 6. LLM 文本生成（不再把图片直传 LLM）
    messages = list(history or [])
    messages.append({"role": "user", "content": full_query})

    collected: list[str] = []
    try:
        async for token in ai.chat_stream(messages, rag_context):
            collected.append(token)
            yield token
    except Exception as exc:
        logger.error("LLM 失败: %s", exc)
        yield "\n\n[提示] 回答生成失败，请稍后重试。"
        return

    answer = "".join(collected)
    if use_history_cache and not has_history and answer and not answer.startswith("\n\n[错误]"):
        cache.set(full_query, answer)

    # 7. 可选 TTS（流结束后由上层读取 meta；此处 yield 特殊标记供 chat_service 解析）
    if enable_tts and answer:
        audio = await media.synthesize_speech(answer)
        if audio:
            import base64

            meta = {"tts_audio_base64": base64.b64encode(audio).decode()}
            yield f"\n\n__META__{json.dumps(meta, ensure_ascii=False)}"
