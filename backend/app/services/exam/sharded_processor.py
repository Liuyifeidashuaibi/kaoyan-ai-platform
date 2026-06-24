"""
分片并行处理引擎 — Token 估算 → 分片 → 并行 AI 处理 → 结果合并。

阈值判断：总 Token ≤ 12K 直接整卷处理；超过阈值自动分片。
分片规则：以完整题目为单位，8-10 道小题 / 1 篇阅读为一个分片。
并行执行：复用现有 AIService + asyncio.gather。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from app.config import get_settings

logger = logging.getLogger(__name__)

# 粗略 token 估算：中文 ≈ 1.5 token/字，英文 ≈ 0.75 token/word
# 平均取 ~1 token/char (中文) 或 chars/3.5 (混合)
_CHARS_PER_TOKEN = 3.5


def estimate_tokens(text: str) -> int:
    """粗略估算文本的 token 数量。"""
    if not text:
        return 0
    # 中文字符占比高时按 1 token/char，否则按 chars/3.5
    chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    total_chars = len(text)
    if chinese_chars > total_chars * 0.3:
        return total_chars  # 中文按 1:1
    return int(total_chars / _CHARS_PER_TOKEN)


@dataclass
class Shard:
    """一个处理分片。"""
    index: int
    questions: list[dict[str, Any]]  # 该分片包含的题目列表
    text: str = ""                   # 拼接后的分片文本
    token_estimate: int = 0


@dataclass
class ShardResult:
    """单个分片的处理结果。"""
    index: int
    output: str = ""
    questions: list[dict[str, Any]] = field(default_factory=list)
    success: bool = True
    error: str | None = None


def create_shards(
    parsed_structure: dict[str, Any],
    *,
    threshold_tokens: int | None = None,
    questions_per_chunk: int | None = None,
) -> list[Shard]:
    """
    将结构化试卷拆分为处理分片。

    :param parsed_structure: ExamParser.parse().to_dict() 的输出
    :param threshold_tokens: 分片 token 阈值（默认 12K）
    :param questions_per_chunk: 每片题目数上限
    """
    settings = get_settings()
    threshold = threshold_tokens or settings.exam_shard_threshold_tokens
    per_chunk = questions_per_chunk or settings.exam_shard_questions_per_chunk

    sections = parsed_structure.get("sections", [])

    # 计算总 token
    all_text = ""
    all_questions: list[dict[str, Any]] = []
    for sec in sections:
        for q in sec.get("questions", []):
            q_text = _question_to_text(q, sec.get("title", ""))
            all_text += q_text + "\n"
            q["_section_type"] = sec.get("type", "other")
            q["_section_title"] = sec.get("title", "")
            all_questions.append(q)

    total_tokens = estimate_tokens(all_text)
    logger.info(
        "试卷分片: %d 题, ~%d tokens, 阈值 %d",
        len(all_questions), total_tokens, threshold,
    )

    # 小卷直接整卷处理
    if total_tokens <= threshold:
        shard = Shard(
            index=0,
            questions=all_questions,
            text=all_text,
            token_estimate=total_tokens,
        )
        return [shard]

    # 大卷按题目数分片
    shards: list[Shard] = []
    current_shard_questions: list[dict] = []
    current_text = ""
    shard_idx = 0

    for q in all_questions:
        q_type = q.get("_section_type", "other")
        q_text = _question_to_text(q, q.get("_section_title", ""))

        # 阅读理解整篇作为一个分片
        if q_type == "reading" and not current_shard_questions:
            shard = Shard(
                index=shard_idx,
                questions=[q],
                text=q_text,
                token_estimate=estimate_tokens(q_text),
            )
            shards.append(shard)
            shard_idx += 1
            continue

        current_shard_questions.append(q)
        current_text += q_text + "\n"

        if len(current_shard_questions) >= per_chunk:
            shard = Shard(
                index=shard_idx,
                questions=current_shard_questions,
                text=current_text,
                token_estimate=estimate_tokens(current_text),
            )
            shards.append(shard)
            shard_idx += 1
            current_shard_questions = []
            current_text = ""

    # 最后一个分片
    if current_shard_questions:
        shard = Shard(
            index=shard_idx,
            questions=current_shard_questions,
            text=current_text,
            token_estimate=estimate_tokens(current_text),
        )
        shards.append(shard)

    logger.info("拆分为 %d 个分片", len(shards))
    return shards


async def process_shards_parallel(
    shards: list[Shard],
    processor: Callable[[Shard], Awaitable[ShardResult]],
    *,
    max_concurrent: int = 3,
) -> list[ShardResult]:
    """
    并行处理多个分片。

    :param shards: 分片列表
    :param processor: 异步处理函数 (Shard) -> ShardResult
    :param max_concurrent: 最大并发数
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _process_with_limit(shard: Shard) -> ShardResult:
        async with semaphore:
            try:
                return await processor(shard)
            except Exception as exc:
                logger.error("分片 %d 处理失败: %s", shard.index, exc)
                return ShardResult(
                    index=shard.index,
                    success=False,
                    error=str(exc),
                )

    results = await asyncio.gather(
        *[_process_with_limit(s) for s in shards],
        return_exceptions=False,
    )

    # 按分片顺序排序
    sorted_results = sorted(results, key=lambda r: r.index)
    return sorted_results


def merge_shard_results(results: list[ShardResult]) -> dict[str, Any]:
    """合并所有分片的处理结果。"""
    merged_output = ""
    all_questions: list[dict[str, Any]] = []
    errors: list[str] = []

    for r in results:
        if r.success:
            merged_output += r.output + "\n\n"
            all_questions.extend(r.questions)
        else:
            errors.append(f"分片 {r.index}: {r.error}")

    return {
        "output": merged_output.strip(),
        "questions": all_questions,
        "errors": errors,
        "total_shards": len(results),
        "success_shards": sum(1 for r in results if r.success),
    }


def _question_to_text(question: dict[str, Any], section_title: str = "") -> str:
    """将单道题目转为可处理的文本。"""
    parts = []
    if section_title:
        parts.append(f"[{section_title}]")
    q_id = question.get("id", "")
    stem = question.get("stem", "")
    parts.append(f"第{q_id}题: {stem}")
    options = question.get("options", [])
    if options:
        parts.append("\n".join(options))
    sub_qs = question.get("sub_questions", [])
    if sub_qs:
        parts.append("小题:")
        parts.append("\n".join(sub_qs))
    return "\n".join(parts)
