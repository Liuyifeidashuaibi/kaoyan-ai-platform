"""
Agent 编排服务 — RAG 检索 + 模型路由（图片 → VL_MODEL，纯文本 → LLM_MODEL）。

不使用 LangGraph 状态序列化来传递图片对象，直接在本函数内路由，
避免 compiled.invoke() 对 ResolvedImage dataclass 的序列化问题。
"""

import logging
from typing import AsyncGenerator

from app.services.ai_service import get_ai_service
from app.services.rag_service import get_rag_service
from app.utils.image_url import ResolvedImage, log_image_event

logger = logging.getLogger(__name__)


async def run_agent_stream(
    query: str,
    history: list[dict] | None = None,
    image: ResolvedImage | None = None,
) -> AsyncGenerator[str, None]:
    """
    RAG 检索 + 流式生成。

    有图片 → VL_MODEL（chat_with_image_stream）
    纯文本 → LLM_MODEL（chat_stream）
    """
    ai = get_ai_service()

    # ── RAG 检索（同步，不经过 LangGraph，避免 state 序列化问题）
    try:
        rag = get_rag_service()
        rag_context: str = rag.retrieve(query) or ""
    except Exception as exc:
        logger.warning("RAG 检索失败，忽略: %s", exc)
        rag_context = ""

    # ── 路由：直接用参数判断，不依赖 LangGraph state
    if image is not None:
        log_image_event(
            request_type="vision",
            source=image.source_type,
            model=ai.settings.vl_model,
            status="agent_route_vl",
            detail=f"api_url_len={len(image.api_url)}",
        )
        logger.info(
            "[Agent] 路由 → VL_MODEL | image_source=%s | query=%r",
            image.source_type,
            query[:80],
        )
        async for token in ai.chat_with_image_stream(
            text=query,
            image=image,
            history=list(history or []),
            rag_context=rag_context,
        ):
            yield token
    else:
        log_image_event(
            request_type="text",
            source="none",
            model=ai.settings.llm_model,
            status="agent_route_llm",
        )
        logger.info(
            "[Agent] 路由 → LLM_MODEL | query=%r",
            query[:80],
        )
        messages = list(history or [])
        messages.append({"role": "user", "content": query})
        async for token in ai.chat_stream(messages, rag_context):
            yield token
