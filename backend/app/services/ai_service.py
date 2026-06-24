"""
AI 服务层 — 封装阿里云百炼（DashScope）文本与多模态模型调用。

- 纯文本：LLM_MODEL（流式）
- 含图片：VL_MODEL（Base64 / 公网 HTTPS 直传，流式）
"""

import asyncio
import logging
from typing import AsyncGenerator

import dashscope
from openai import AsyncOpenAI

from app.config import get_settings
from app.utils.image_url import (
    ImageProcessingError,
    ResolvedImage,
    log_image_event,
    resolve_legacy_disk_image,
)

logger = logging.getLogger(__name__)


def _is_retriable_model_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        k in text
        for k in (
            "403",
            "access_denied",
            "access denied",
            "free tier",
            "quota",
            "exhausted",
            "insufficient",
        )
    )


def _friendly_api_error(exc: Exception) -> str:
    text = str(exc)
    if "timeout" in text.lower() or isinstance(exc, asyncio.TimeoutError):
        return "模型响应超时，请稍后重试或缩短问题内容。"
    if _is_retriable_model_error(exc):
        return (
            "千问 API 访问被拒绝（403），常见原因是当前模型免费额度已用尽。\n"
            "请在 .env 中将 LLM_MODEL 改为 qwen3.5-plus 或 qwen-turbo，"
            "或配置 LLM_FALLBACK_MODELS 作为备用模型链。"
        )
    if "invalid_api_key" in text or "401" in text:
        return "千问 API Key 无效，请检查 .env 中的 DASHSCOPE_API_KEY。"
    return f"对话服务异常: {text}"


SYSTEM_PROMPT = """你是专为考研学生定制的 AI 助手，覆盖数学、英语、政治、专业课全科。

## 回答原则

**先给结论，再解释，最后扩展。** 禁止废话、鸡汤、无意义鼓励、小红书风格表达。

**多轮对话**：用户可能在上一轮已上传图片（正文含「[图片内容]」或「[沿用上文图片]」）。追问如「第二题」「继续解答」时，务必结合历史消息与图片文字作答，勿声称用户未上传图片。

示例：
- 用户问「2+2=？」→ 直接答「2+2=4」，再一句话解释即可
- 用户上传题目图片 → 先识别题意，直接给出答案，再分步解析

## 长度控制

- 简单问题（计算、定义）：50 字以内
- 普通问题：200～500 字
- 复杂题目：分层展开，使用二级标题

## 格式规范

- 数学公式：行内用 `$...$`，独立公式必须用 `$$...$$`（禁止纯文本公式）
- 代码：用 ``` 包裹

## 分科解析模板

**数学题**（按顺序输出）：
## 答案
## 考点
## 解题步骤
## 易错点
## 提速技巧

**英语题**：
## 正确答案
## 文章定位
## 选项分析
## 高频考点
## 解题技巧

**政治题**：
## 标准答案
## 理论依据
## 考点分析
## 记忆技巧

**专业课**：
## 答案
## 核心知识点
## 解题思路
## 易错点

简单计算题可省略模板，直接给结论。"""


VISION_INSTRUCTION = """你可以直接看到用户上传的图片（题目截图、试卷拍照、错题本图片等）。

请自动完成：
1. 识别图片中的题目文字、公式、选项、图形（含手写）
2. 若用户指定题号（如「第一题」「第3题」「解答选择题」），只处理对应题目
3. 若用户说「分析整张试卷」「总结本页知识点」「找出错题」，按指令执行
4. 无需用户重复描述题目内容"""


class AIService:
    """百炼模型调用封装。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.dashscope_api_key:
            logger.warning("DASHSCOPE_API_KEY 未配置，AI 功能不可用")
        dashscope.api_key = self.settings.dashscope_api_key
        self._openai_client: AsyncOpenAI | None = None

    @property
    def openai_client(self) -> AsyncOpenAI:
        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(
                api_key=self.settings.dashscope_api_key,
                base_url=self.settings.dashscope_base_url,
                timeout=self.settings.model_timeout_seconds,
            )
        return self._openai_client

    def _build_vision_user_text(self, user_text: str) -> str:
        prompt = user_text.strip() or "请识别图片中的考研题目，给出完整解答。"
        return f"{VISION_INSTRUCTION}\n\n【用户要求】\n{prompt}"

    def _llm_model_chain(self) -> list[str]:
        chain: list[str] = []
        for name in (
            self.settings.llm_model,
            *self.settings.llm_fallback_models.split(","),
        ):
            model = name.strip()
            if model and model not in chain:
                chain.append(model)
        return chain or ["qwen3.5-plus", "qwen-turbo"]

    def _dashscope_extra_body(self, model: str) -> dict | None:
        """千问思考/推理模型需显式 enable_thinking；普通 qwen3.5 默认关闭以加快首字。"""
        name = model.lower()
        if "-thinking" in name or "deepseek-r1" in name:
            return {"enable_thinking": True}
        if self.settings.llm_enable_thinking:
            return None
        if name.startswith("qwen3") or "qwen3.5" in name or "qwen3.6" in name or "qwen3.7" in name:
            return {"enable_thinking": False}
        return None

    def _system_with_rag(self, rag_context: str = "") -> str:
        content = SYSTEM_PROMPT
        if rag_context:
            content += (
                f"\n\n【知识库参考】\n{rag_context}\n\n"
                "请结合参考资料回答；若无相关内容则凭自身知识解答。"
            )
        return content

    def _resolve_image_for_api(self, image_path: str) -> str:
        """错题本等非聊天场景：磁盘图片转 Base64。"""
        return resolve_legacy_disk_image(image_path, self.settings).api_url

    async def analyze_image(
        self,
        image_path: str,
        prompt: str = "请识别这道考研题目，逐步分析并给出详细解答。",
    ) -> str:
        """使用 VL 模型分析磁盘图片（非流式，供错题本等场景）。"""
        try:
            image_api_url = self._resolve_image_for_api(image_path)
        except ImageProcessingError as exc:
            log_image_event(
                request_type="vision",
                source="legacy_disk",
                model=self.settings.vl_model,
                status="failed",
                detail=exc.log_detail or str(exc),
            )
            return f"[错误] {exc.user_message}"

        user_text = self._build_vision_user_text(prompt)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_api_url}},
                    {"type": "text", "text": user_text},
                ],
            }
        ]

        chunks: list[str] = []
        async for token in self._vision_stream(
            messages, rag_context="", source_label="legacy_disk"
        ):
            chunks.append(token)
        result = "".join(chunks)
        if result.startswith("\n\n[错误]"):
            return result.strip()
        return result

    async def chat_stream(
        self,
        messages: list[dict],
        rag_context: str = "",
    ) -> AsyncGenerator[str, None]:
        """流式文本对话（无图片 → LLM_MODEL）。"""
        if not self.settings.dashscope_api_key:
            yield "\n\n[错误] 未配置 DASHSCOPE_API_KEY，请在项目根目录 .env 中设置。"
            return

        api_messages = [
            {"role": "system", "content": self._system_with_rag(rag_context)},
            *messages,
        ]
        last_exc: Exception | None = None
        for model in self._llm_model_chain():
            extra = self._dashscope_extra_body(model)
            try:
                stream = await asyncio.wait_for(
                    self.openai_client.chat.completions.create(
                        model=model,
                        messages=api_messages,
                        stream=True,
                        temperature=self.settings.llm_temperature,
                        max_tokens=self.settings.llm_max_tokens,
                        **({"extra_body": extra} if extra else {}),
                    ),
                    timeout=self.settings.model_timeout_seconds,
                )
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
                return
            except Exception as exc:
                last_exc = exc
                if _is_retriable_model_error(exc):
                    logger.warning("LLM 模型 %s 不可用，尝试备用: %s", model, exc)
                    continue
                log_image_event(
                    request_type="text",
                    source="none",
                    model=model,
                    status="failed",
                    detail=str(exc),
                )
                logger.error("LLM 调用失败: %s", exc)
                yield f"\n\n[错误] {_friendly_api_error(exc)}"
                return

        if last_exc is not None:
            logger.error("LLM 全部模型不可用: %s", last_exc)
            yield f"\n\n[错误] {_friendly_api_error(last_exc)}"

    async def _vision_stream(
        self,
        messages: list[dict],
        rag_context: str = "",
        *,
        source_label: str = "unknown",
    ) -> AsyncGenerator[str, None]:
        """流式视觉对话（有图片 → VL_MODEL）。"""
        if not self.settings.dashscope_api_key:
            yield "\n\n[错误] 未配置 DASHSCOPE_API_KEY。"
            return

        api_messages = [
            {"role": "system", "content": self._system_with_rag(rag_context)},
            *messages,
        ]
        model = self.settings.vl_model.strip()
        extra = self._dashscope_extra_body(model)

        try:
            stream = await asyncio.wait_for(
                self.openai_client.chat.completions.create(
                    model=model,
                    messages=api_messages,
                    stream=True,
                    temperature=0.01,
                    max_tokens=1500,
                    **({"extra_body": extra} if extra else {}),
                ),
                timeout=self.settings.model_timeout_seconds,
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
            return
        except Exception as exc:
            log_image_event(
                request_type="vision",
                source=source_label,
                model=model,
                status="failed",
                detail=str(exc),
            )
            logger.error("VL 调用失败: %s", exc)
            yield f"\n\n[错误] {_friendly_api_error(exc)}"

    async def chat_complete(
        self,
        messages: list[dict],
        rag_context: str = "",
    ) -> str:
        chunks: list[str] = []
        async for token in self.chat_stream(messages, rag_context):
            chunks.append(token)
        return "".join(chunks)

    async def chat_with_image_stream(
        self,
        text: str,
        image: ResolvedImage,
        history: list[dict] | None = None,
        rag_context: str = "",
    ) -> AsyncGenerator[str, None]:
        """带图片的流式对话：强制 VL_MODEL。"""
        user_text = self._build_vision_user_text(text)

        msg_list = list(history or [])
        msg_list.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image.api_url},
                    },
                    {"type": "text", "text": user_text},
                ],
            }
        )

        log_image_event(
            request_type="vision",
            source=image.source_type,
            model=self.settings.vl_model,
            status="routed",
        )

        async for token in self._vision_stream(
            msg_list,
            rag_context,
            source_label=image.source_type,
        ):
            yield token


_ai_service: AIService | None = None


def get_ai_service() -> AIService:
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service
