"""
AI 服务层 — 封装阿里云百炼（DashScope）文本与多模态模型调用。

- 文本对话：qwen-max-latest（OpenAI 兼容模式，流式）
- 图片问答：qwen2.5-vl-72b-instruct（OpenAI 兼容 image_url，流式）
"""

import logging
from typing import AsyncGenerator

import dashscope
from openai import AsyncOpenAI

from app.config import get_settings
from app.utils.image_url import resolve_public_image_url, validate_api_image_url

logger = logging.getLogger(__name__)

# 文本模型回退链
LLM_MODEL_FALLBACKS = (
    "qwen-max-latest",
    "qwen-max",
    "qwen-plus",
    "qwen-turbo",
)

# 视觉模型回退链（预算不足时降级到 7B）
VL_MODEL_FALLBACKS = (
    "qwen2.5-vl-72b-instruct",
    "qwen2.5-vl-7b-instruct",
    "qwen-vl-max",
    "qwen-vl-plus",
)


def _friendly_api_error(exc: Exception) -> str:
    text = str(exc)
    if "access_denied" in text or "403" in text:
        return (
            "千问 API 访问被拒绝（403）。请检查：\n"
            "1. DASHSCOPE_API_KEY 是否正确\n"
            "2. 阿里云百炼控制台是否已开通 qwen-max-latest / qwen2.5-vl 模型\n"
            "3. 尝试在 .env 中将 VL_MODEL 改为 qwen2.5-vl-7b-instruct"
        )
    if "invalid_api_key" in text or "401" in text:
        return "千问 API Key 无效，请检查 .env 中的 DASHSCOPE_API_KEY。"
    return f"对话服务异常: {text}"


SYSTEM_PROMPT = """你是专为考研学生定制的 AI 助手，覆盖数学、英语、政治、专业课全科。

## 回答原则

**先给结论，再解释，最后扩展。** 禁止废话、鸡汤、无意义鼓励、小红书风格表达。

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
        self._resolved_llm_model: str | None = None
        self._resolved_vl_model: str | None = None

    def _llm_models_to_try(self) -> list[str]:
        primary = self.settings.llm_model.strip()
        models: list[str] = []
        for name in [primary, *LLM_MODEL_FALLBACKS]:
            if name and name not in models:
                models.append(name)
        return models

    def _vl_models_to_try(self) -> list[str]:
        primary = self.settings.vl_model.strip()
        models: list[str] = []
        for name in [primary, *VL_MODEL_FALLBACKS]:
            if name and name not in models:
                models.append(name)
        return models

    @property
    def openai_client(self) -> AsyncOpenAI:
        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(
                api_key=self.settings.dashscope_api_key,
                base_url=self.settings.dashscope_base_url,
            )
        return self._openai_client

    def get_public_image_url(self, image_path: str) -> str:
        """解析上传图片的公网/API 可访问 URL。"""
        url = resolve_public_image_url(image_path, self.settings)
        validate_api_image_url(url)
        return url

    def _build_vision_user_text(self, user_text: str) -> str:
        prompt = user_text.strip() or "请识别图片中的考研题目，给出完整解答。"
        return f"{VISION_INSTRUCTION}\n\n【用户要求】\n{prompt}"

    def _system_with_rag(self, rag_context: str = "") -> str:
        content = SYSTEM_PROMPT
        if rag_context:
            content += (
                f"\n\n【知识库参考】\n{rag_context}\n\n"
                "请结合参考资料回答；若无相关内容则凭自身知识解答。"
            )
        return content

    async def analyze_image(
        self,
        image_path: str,
        prompt: str = "请识别这道考研题目，逐步分析并给出详细解答。",
    ) -> str:
        """使用 qwen2.5-vl 分析图片（非流式，供错题本等场景）。"""
        image_url = self.get_public_image_url(image_path)
        user_text = self._build_vision_user_text(prompt)

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": user_text},
                ],
            }
        ]

        chunks: list[str] = []
        async for token in self._vision_stream(messages, rag_context=""):
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
        """流式文本对话（无图片 → qwen-max-latest）。"""
        if not self.settings.dashscope_api_key:
            yield "\n\n[错误] 未配置 DASHSCOPE_API_KEY，请在项目根目录 .env 中设置。"
            return

        api_messages = [
            {"role": "system", "content": self._system_with_rag(rag_context)},
            *messages,
        ]
        models = (
            [self._resolved_llm_model]
            if self._resolved_llm_model
            else self._llm_models_to_try()
        )

        last_error: Exception | None = None
        for model in models:
            if not model:
                continue
            try:
                stream = await self.openai_client.chat.completions.create(
                    model=model,
                    messages=api_messages,
                    stream=True,
                    temperature=0.7,
                    max_tokens=4096,
                )
                self._resolved_llm_model = model
                logger.info("文本模型: %s, messages=%d", model, len(api_messages))
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
                return
            except Exception as exc:
                last_error = exc
                logger.warning("LLM 模型 %s 失败: %s", model, exc)

        logger.exception("流式对话全部模型失败")
        yield f"\n\n[错误] {_friendly_api_error(last_error or Exception('unknown'))}"

    async def _vision_stream(
        self,
        messages: list[dict],
        rag_context: str = "",
    ) -> AsyncGenerator[str, None]:
        """流式视觉对话（有图片 → qwen2.5-vl-*，OpenAI 兼容 image_url）。"""
        if not self.settings.dashscope_api_key:
            yield "\n\n[错误] 未配置 DASHSCOPE_API_KEY。"
            return

        api_messages = [
            {"role": "system", "content": self._system_with_rag(rag_context)},
            *messages,
        ]
        models = (
            [self._resolved_vl_model]
            if self._resolved_vl_model
            else self._vl_models_to_try()
        )

        last_error: Exception | None = None
        for model in models:
            if not model:
                continue
            try:
                stream = await self.openai_client.chat.completions.create(
                    model=model,
                    messages=api_messages,
                    stream=True,
                    temperature=0.7,
                    max_tokens=4096,
                )
                self._resolved_vl_model = model
                logger.info(
                    "视觉模型: %s, 含 image_url=%s",
                    model,
                    self._has_image_in_messages(api_messages),
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
                return
            except Exception as exc:
                last_error = exc
                logger.warning("VL 模型 %s 失败: %s", model, exc)

        logger.exception("视觉流式对话全部模型失败")
        yield f"\n\n[错误] {_friendly_api_error(last_error or Exception('unknown'))}"

    @staticmethod
    def _has_image_in_messages(messages: list[dict]) -> bool:
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "image_url":
                        return True
        return False

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
        image_path: str,
        history: list[dict] | None = None,
        rag_context: str = "",
    ) -> AsyncGenerator[str, None]:
        """
        带图片的流式对话：直接调用 qwen2.5-vl，请求体同时携带 image_url + text。
        """
        image_url = self.get_public_image_url(image_path)
        user_text = self._build_vision_user_text(text)

        msg_list = list(history or [])
        msg_list.append(
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": user_text},
                ],
            }
        )

        logger.info(
            "图片问答路由: model=%s, image=%s",
            self.settings.vl_model,
            image_url[:80] + ("..." if len(image_url) > 80 else ""),
        )

        async for token in self._vision_stream(msg_list, rag_context):
            yield token


_ai_service: AIService | None = None


def get_ai_service() -> AIService:
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service
