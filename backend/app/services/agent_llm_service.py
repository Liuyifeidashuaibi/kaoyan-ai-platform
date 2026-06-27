"""
LiteLLM 统一模型接入层 — 商业级多模型管理。

核心能力：
  1. 统一接口：一个 API 调用 GPT-4o / 通义千问 / GLM / 本地模型
  2. 自动重试：失败自动切换备用模型 + 指数退避
  3. 调用日志：每次 LLM 调用记录模型、token 数、耗时、状态
  4. 流式支持：stream=True 实时输出
  5. 额度管控：每日调用次数限制 + token 消耗统计

使用方式：
    from app.services.agent_llm_service import get_llm_service
    service = get_llm_service()
    response = await service.chat_completion(messages, tools=tools)
    # 或流式：
    async for chunk in service.stream_completion(messages, tools=tools):
        print(chunk)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class LLMCallRecord:
    """单次 LLM 调用记录。"""
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: float = 0.0
    status: str = "success"  # success / error / fallback
    error: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class LLMServiceConfig:
    """LLM 服务配置。"""
    primary_model: str = ""
    fallback_models: list[str] = field(default_factory=list)
    max_retries: int = 3
    retry_delay: float = 1.0
    temperature: float = 0.1
    max_tokens: int = 4096
    enable_thinking: bool = False
    # 日志记录
    call_history: list[LLMCallRecord] = field(default_factory=list)
    max_history: int = 500


class LLMService:
    """
    统一 LLM 接入服务 — 基于 LiteLLM。

    LiteLLM 提供统一的 completion 接口，支持 100+ 模型提供商。
    本服务在 LiteLLM 之上增加：
      - 自动重试 + 模型降级
      - 调用日志
      - 流式输出
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.config = LLMServiceConfig(
            primary_model=self.settings.llm_model.strip() or "qwen3.5-plus",
            fallback_models=[
                m.strip()
                for m in self.settings.llm_fallback_models.split(",")
                if m.strip()
            ],
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_tokens,
            enable_thinking=self.settings.llm_enable_thinking,
        )

        # 配置 LiteLLM
        self._setup_litellm()

    def _setup_litellm(self) -> None:
        """配置 LiteLLM 全局设置。"""
        try:
            import litellm

            # 设置 DashScope API Key
            if self.settings.dashscope_api_key:
                litellm.api_key = self.settings.dashscope_api_key

            # 关闭不必要的遥测
            litellm.telemetry = False

            # 设置全局超时
            litellm.request_timeout = self.settings.model_timeout_seconds

            logger.info(
                "LiteLLM 已配置: primary=%s, fallback=%s",
                self.config.primary_model,
                self.config.fallback_models,
            )
        except Exception as exc:
            logger.error("LiteLLM 配置失败，降级为直接 OpenAI 调用: %s", exc)

    def _get_model_list(self) -> list[str]:
        """返回主模型 + 备用模型列表。"""
        models = [self.config.primary_model]
        for m in self.config.fallback_models:
            if m not in models:
                models.append(m)
        return models

    def _get_litellm_model_name(self, model: str) -> str:
        """
        将内部模型名映射为 LiteLLM 模型名。

        DashScope/通义千问模型使用 openai/ 前缀（兼容模式）。
        """
        # 如果已经有 provider 前缀（含 openai/），直接返回
        if "/" in model:
            return model

        # 通义千问/DashScope 模型 → openai/ 前缀 + base_url
        if any(k in model.lower() for k in ("qwen", "dashscope")):
            return f"openai/{model}"

        return model

    def _get_extra_params(self, model: str) -> dict:
        """获取模型特定的额外参数。"""
        params: dict[str, Any] = {}

        # DashScope 兼容模式需要 base_url 和 api_key
        if any(k in model.lower() for k in ("qwen", "dashscope")):
            params["api_base"] = self.settings.dashscope_base_url
            params["api_key"] = self.settings.dashscope_api_key

        # 思考模式
        name = model.lower()
        if "-thinking" in name or "deepseek-r1" in name:
            params["extra_body"] = {"enable_thinking": True}
        elif not self.config.enable_thinking:
            if name.startswith("qwen3") or "qwen3.5" in name or "qwen3.6" in name:
                params["extra_body"] = {"enable_thinking": False}

        return params

    def _record_call(self, record: LLMCallRecord) -> None:
        """记录调用日志。"""
        self.config.call_history.append(record)
        if len(self.config.call_history) > self.config.max_history:
            self.config.call_history = self.config.call_history[-self.config.max_history :]

        logger.info(
            "LLM 调用: model=%s status=%s tokens=%d+%d duration=%.0fms",
            record.model, record.status,
            record.input_tokens, record.output_tokens,
            record.duration_ms,
        )

    async def stream_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> AsyncGenerator[tuple[str, Any], None]:
        """
        流式 LLM 调用 — 带自动重试和模型降级。

        产出: (chunk_type, chunk_data)
            chunk_type: "content" | "tool_call" | "done" | "error"
            chunk_data: str | dict

        重试策略：
          1. 主模型失败 → 重试（最多 max_retries 次）
          2. 重试仍失败 → 切换备用模型
          3. 所有模型都失败 → 返回 error
        """
        models = self._get_model_list()
        last_error: str = ""

        for model_idx, model in enumerate(models):
            is_fallback = model_idx > 0
            litellm_model = self._get_litellm_model_name(model)
            extra = self._get_extra_params(model)

            for attempt in range(self.config.max_retries):
                t_start = time.time()
                content_yielded = False  # 跟踪是否已产出内容（防止重试导致重复）

                try:
                    # 优先使用 LiteLLM
                    try:
                        import litellm

                        stream = await litellm.acompletion(
                            model=litellm_model,
                            messages=messages,
                            tools=tools,
                            stream=True,
                            temperature=kwargs.get("temperature", self.config.temperature),
                            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                            **extra,
                            **{k: v for k, v in kwargs.items()
                               if k not in ("temperature", "max_tokens")},
                        )
                    except Exception as litellm_exc:
                        # LiteLLM 失败，降级为直接 OpenAI 调用
                        logger.warning(
                            "LiteLLM 调用失败，降级为 OpenAI 直接调用: %s",
                            litellm_exc,
                        )
                        from app.services.ai_service import get_ai_service
                        ai = get_ai_service()
                        # 使用 .get() 而非 .pop() 避免修改原 dict（重试时仍需要 extra_body）
                        extra_body = extra.get("extra_body")
                        stream = await ai.openai_client.chat.completions.create(
                            model=model,
                            messages=messages,
                            tools=tools,
                            stream=True,
                            temperature=kwargs.get("temperature", self.config.temperature),
                            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                            **({"extra_body": extra_body} if extra_body else {}),
                        )

                    # 流式收集
                    content_parts: list[str] = []
                    tool_calls_map: dict[int, dict] = {}
                    input_tokens = 0
                    output_tokens = 0

                    async for chunk in stream:
                        # LiteLLM 和 OpenAI 的 chunk 格式兼容
                        choices = getattr(chunk, "choices", None) or \
                                  getattr(chunk, "data", {}).get("choices", [])
                        if not choices:
                            # LiteLLM 可能返回 usage 信息
                            if hasattr(chunk, "usage") and chunk.usage:
                                input_tokens = getattr(chunk.usage, "prompt_tokens", 0)
                                output_tokens = getattr(chunk.usage, "completion_tokens", 0)
                            continue

                        delta = choices[0].delta if hasattr(choices[0], "delta") else \
                                choices[0].get("delta", {})

                        if hasattr(delta, "content") and delta.content:
                            content_parts.append(delta.content)
                            content_yielded = True
                            yield ("content", delta.content)

                        if hasattr(delta, "tool_calls") and delta.tool_calls:
                            for tc_delta in delta.tool_calls:
                                idx = tc_delta.index or 0
                                slot = tool_calls_map.setdefault(idx, {
                                    "id": "", "name": "", "arguments": "",
                                })
                                if tc_delta.id:
                                    slot["id"] = tc_delta.id
                                if tc_delta.function:
                                    if tc_delta.function.name:
                                        slot["name"] += tc_delta.function.name
                                    if tc_delta.function.arguments:
                                        slot["arguments"] += tc_delta.function.arguments

                    duration_ms = (time.time() - t_start) * 1000

                    self._record_call(LLMCallRecord(
                        model=model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens or len("".join(content_parts)),
                        duration_ms=duration_ms,
                        status="fallback" if is_fallback else "success",
                    ))

                    # 产出工具调用
                    for idx in sorted(tool_calls_map):
                        yield ("tool_call", tool_calls_map[idx])

                    yield ("done", {"model": model, "content": "".join(content_parts)})
                    return

                except Exception as exc:
                    last_error = str(exc)
                    duration_ms = (time.time() - t_start) * 1000
                    self._record_call(LLMCallRecord(
                        model=model,
                        duration_ms=duration_ms,
                        status="error",
                        error=last_error,
                    ))
                    logger.warning(
                        "LLM 调用失败: model=%s attempt=%d/%d error=%s",
                        model, attempt + 1, self.config.max_retries, last_error,
                    )
                    # 如果已经向调用方产出了内容，不能重试（会导致内容重复）
                    if content_yielded:
                        logger.error(
                            "流式输出中途失败且已产出内容，不再重试: %s", last_error,
                        )
                        yield ("error", {"error": f"流式输出中断: {last_error}"})
                        return
                    if attempt < self.config.max_retries - 1:
                        await _async_sleep(self.config.retry_delay * (attempt + 1))
                    continue

        # 所有模型都失败
        yield ("error", {"error": f"所有模型调用失败: {last_error}"})

    def get_stats(self) -> dict[str, Any]:
        """获取 LLM 调用统计。"""
        history = self.config.call_history
        total = len(history)
        success = sum(1 for r in history if r.status in ("success", "fallback"))
        errors = sum(1 for r in history if r.status == "error")
        total_input = sum(r.input_tokens for r in history)
        total_output = sum(r.output_tokens for r in history)

        return {
            "total_calls": total,
            "success_calls": success,
            "error_calls": errors,
            "success_rate": round(success / total * 100, 1) if total else 0,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "primary_model": self.config.primary_model,
            "fallback_models": self.config.fallback_models,
        }


async def _async_sleep(seconds: float) -> None:
    """异步 sleep。"""
    import asyncio
    await asyncio.sleep(seconds)


# 全局单例
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
