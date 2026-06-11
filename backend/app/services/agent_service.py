"""
LangGraph Agent 编排服务。

工作流：
  接收用户输入 → RAG 检索 → 判断是否有图片 → 选择文本/多模态路径 → 流式生成回复
"""

import logging
from typing import AsyncGenerator, TypedDict

from langgraph.graph import END, StateGraph

from app.services.ai_service import get_ai_service
from app.services.rag_service import get_rag_service

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """Agent 状态定义。"""

    query: str
    image_path: str | None
    history: list[dict]
    rag_context: str
    has_image: bool
    response: str


def _retrieve_node(state: AgentState) -> AgentState:
    """节点：RAG 知识库检索（用户错题优先）。"""
    rag = get_rag_service()
    context = rag.retrieve(state["query"])
    return {**state, "rag_context": context}


def _route_node(state: AgentState) -> AgentState:
    """节点：判断是否需要图片处理。"""
    has_image = bool(state.get("image_path"))
    return {**state, "has_image": has_image}


async def run_agent_stream(
    query: str,
    history: list[dict] | None = None,
    image_path: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    执行 LangGraph Agent 并流式返回 token。

    图结构：retrieve → route → (stream with image / stream text only)
    """
    # 构建并编译 LangGraph 工作流
    graph = StateGraph(AgentState)
    graph.add_node("retrieve", _retrieve_node)
    graph.add_node("route", _route_node)
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "route")
    graph.add_edge("route", END)
    compiled = graph.compile()

    # 运行检索与路由节点（同步部分）
    initial: AgentState = {
        "query": query,
        "image_path": image_path,
        "history": history or [],
        "rag_context": "",
        "has_image": False,
        "response": "",
    }
    result = compiled.invoke(initial)

    ai = get_ai_service()
    rag_context = result.get("rag_context", "")

    # 根据是否有图片选择不同的流式生成路径
    if result.get("has_image") and image_path:
        logger.info("路由: 图片问答 → %s", ai.settings.vl_model)
        async for token in ai.chat_with_image_stream(
            text=query,
            image_path=image_path,
            history=result.get("history"),
            rag_context=rag_context,
        ):
            yield token
    else:
        logger.info("路由: 文本问答 → %s", ai.settings.llm_model)
        messages = list(result.get("history") or [])
        messages.append({"role": "user", "content": query})
        async for token in ai.chat_stream(messages, rag_context):
            yield token
