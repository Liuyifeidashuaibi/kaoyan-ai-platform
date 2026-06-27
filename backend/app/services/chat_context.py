"""
聊天多轮上下文 — 历史截断、图片 OCR 持久化与追问时沿用上文图片。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.config import Settings, get_settings
from app.database import ChatMessage
from app.services.media_service import MediaService
from app.utils.image_url import ImageProcessingError, ResolvedImage, resolve_legacy_disk_image

logger = logging.getLogger(__name__)

IMAGE_OCR_MARKER = "[图片内容]"
CARRY_IMAGE_MARKER = "[沿用上文图片]"

_FOLLOW_UP_HINT = re.compile(
    r"第[一二三四五六七八九十百\d]+[题问]|这题|那题|上一题|上面|图中|图片|刚才|"
    r"继续|上文|前面|同样|还有|另外|再|解答|解析|多少|什么|为什么|怎么",
    re.I,
)


@dataclass
class PreparedTurn:
    """单轮用户输入整理结果。"""

    llm_query: str
    db_content: str


def extract_ocr_from_content(content: str) -> str:
    if not content or IMAGE_OCR_MARKER not in content:
        return ""
    _, _, tail = content.partition(IMAGE_OCR_MARKER)
    return tail.strip()


def strip_ocr_for_display(content: str) -> str:
    """前端展示用：去掉 OCR 与沿用上文标记，只保留用户输入的文字。"""
    if not content:
        return ""
    text = content
    for marker in (IMAGE_OCR_MARKER, CARRY_IMAGE_MARKER):
        if marker in text:
            text = text.split(marker, 1)[0]
    return text.strip()


def _user_turns_after_image(messages: list[ChatMessage], anchor: ChatMessage) -> int:
    """
    图片消息之后已发生的用户轮次 + 当前正在发送的 1 轮。
    （prepare 时当前消息尚未入库，故 +1）
    """
    try:
        idx = next(i for i, m in enumerate(messages) if m.id == anchor.id)
    except StopIteration:
        return 0
    prior_user = sum(1 for m in messages[idx + 1 :] if m.role == "user")
    return prior_user + 1


def find_latest_image_message(
    messages: list[ChatMessage],
    max_user_turns: int,
) -> ChatMessage | None:
    """最近一条带图片或已 OCR 的用户消息。"""
    _ = max_user_turns  # 保留参数供后续按轮次过滤扩展
    for m in reversed(messages):
        if m.role != "user":
            continue
        if m.image_path or IMAGE_OCR_MARKER in (m.content or ""):
            return m
    return None


def build_history_for_llm(
    messages: list[ChatMessage],
    settings: Settings | None = None,
) -> list[dict]:
    """
    构建 LLM 多轮历史：保留最近 N 轮，总字符上限内从旧到新。
    """
    s = settings or get_settings()
    relevant = [m for m in messages if m.role in ("user", "assistant")]
    max_msgs = s.chat_history_max_turns * 2
    if len(relevant) > max_msgs:
        relevant = relevant[-max_msgs:]

    # Agent 文件标记 — 历史中剥离，避免污染 LLM 上下文
    _AGENT_MARKER = "__AGENT_FILES__"

    # 从最新往旧累积，超限时丢弃更旧消息，确保追问仍在上下文中
    history_rev: list[dict] = []
    total_chars = 0
    for m in reversed(relevant):
        text = (m.content or "").strip()
        if not text:
            continue
        # 剥离 Agent 文件标记（仅 assistant 消息）
        if m.role == "assistant" and _AGENT_MARKER in text:
            text = text.split(_AGENT_MARKER, 1)[0].rstrip()
        if m.role == "assistant" and len(text) > s.chat_assistant_msg_max_chars:
            text = text[: s.chat_assistant_msg_max_chars].rstrip() + "…"
        if total_chars + len(text) > s.chat_history_max_chars:
            break
        history_rev.append({"role": m.role, "content": text})
        total_chars += len(text)
    history_rev.reverse()
    return history_rev


def _should_carry_image(
    query: str,
    turns_after_image: int,
    max_turns: int,
) -> bool:
    if turns_after_image > max_turns:
        return False
    if _FOLLOW_UP_HINT.search(query):
        return True
    return turns_after_image <= max(3, max_turns // 2)


async def prepare_user_turn(
    messages: list[ChatMessage],
    user_content: str,
    image: ResolvedImage | None,
    image_bytes: bytes | None,
    media: MediaService,
    settings: Settings | None = None,
) -> PreparedTurn:
    """
    整理本轮用户输入：
    - 新图片：OCR 写入内容并入库，供后续多轮引用
    - 纯文字追问：在合理窗口内自动附带上文图片 OCR
    """
    s = settings or get_settings()
    text = user_content.strip()

    if image is not None:
        try:
            ocr = await media.extract_image_text(image, image_bytes)
        except Exception as exc:
            logger.error("首轮图片 OCR 失败: %s", exc)
            raise
        ocr = ocr[: s.chat_image_ocr_max_chars]
        user_part = text or "请根据图片内容回答。"
        combined = f"{user_part}\n\n{IMAGE_OCR_MARKER}\n{ocr}"
        return PreparedTurn(llm_query=combined, db_content=combined)

    if not text:
        return PreparedTurn(llm_query="", db_content="")

    img_msg = find_latest_image_message(messages, s.chat_image_context_turns)
    if not img_msg:
        return PreparedTurn(llm_query=text, db_content=text)

    turns_after = _user_turns_after_image(messages, img_msg)
    if not _should_carry_image(text, turns_after, s.chat_image_context_turns):
        return PreparedTurn(llm_query=text, db_content=text)

    ocr = extract_ocr_from_content(img_msg.content or "")
    if not ocr and img_msg.image_path:
        try:
            resolved = resolve_legacy_disk_image(img_msg.image_path, s)
            ocr = await media.extract_image_text(resolved, None)
            ocr = ocr[: s.chat_image_ocr_max_chars]
        except (ImageProcessingError, Exception) as exc:
            logger.warning("追问沿用上文图片 OCR 失败: %s", exc)
            ocr = ""

    if not ocr:
        return PreparedTurn(llm_query=text, db_content=text)

    llm_query = (
        f"{text}\n\n{CARRY_IMAGE_MARKER}\n{IMAGE_OCR_MARKER}\n"
        f"{ocr[: s.chat_image_ocr_max_chars]}"
    )
    return PreparedTurn(llm_query=llm_query, db_content=text)
