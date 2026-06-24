"""
英语试卷专项处理 — 翻译 + 双语对照 + 学习模式适配。

处理链:
1. 接收分片 (Shard)
2. 调用 TranslatorService 翻译每个分片
3. 汇总生成双语结果
4. 返回带翻译对的题目列表
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.exam.sharded_processor import Shard, ShardResult

logger = logging.getLogger(__name__)


async def process_english_shard(shard: Shard) -> ShardResult:
    """
    处理英语试卷的一个分片：翻译 + 双语生成。

    :param shard: 待处理分片
    :return: 分片处理结果
    """
    from app.services.translator_service import get_translator_service

    translator = get_translator_service()

    result_questions: list[dict[str, Any]] = []
    output_parts: list[str] = []

    for q in shard.questions:
        stem = q.get("stem", "")
        options = q.get("options", [])
        q_type = q.get("_section_type", "other")
        q_title = q.get("_section_title", "")

        if not stem.strip():
            continue

        # 构建待翻译文本
        translate_text_parts = [stem]
        if options:
            translate_text_parts.extend(options)

        translate_text = "\n".join(translate_text_parts)

        # 调用翻译服务
        try:
            translation_data = await translator.translate_text(
                translate_text,
                mode="bilingual",
                domain="paper",
            )

            # 提取翻译对
            pairs = translation_data.get("pairs", [])
            translated_stem = ""
            translated_options: list[str] = []

            if pairs:
                # 第一个 pair 对应题干翻译
                stem_pair = pairs[0] if pairs else None
                if stem_pair:
                    translated_stem = stem_pair.get("target", "")

                # 后续 pairs 对应选项翻译
                option_pairs = pairs[1:] if len(pairs) > 1 else []
                for i, opt in enumerate(options):
                    if i < len(option_pairs):
                        translated_opt = option_pairs[i].get("target", "")
                        # 保留选项标签 (A. B. C. D.)
                        label = opt.split(".")[0].strip() if "." in opt else ""
                        translated_options.append(f"{label}. {translated_opt}" if label else translated_opt)
                    else:
                        translated_options.append(opt)
            else:
                # 无 pairs 时使用 full_text
                translated_stem = translation_data.get("full_text", "")

            # 构建结果题目
            result_q: dict[str, Any] = {
                "id": q.get("id", ""),
                "type": q_type,
                "section_title": q_title,
                "stem": stem,
                "stem_translated": translated_stem,
                "options": options,
                "options_translated": translated_options,
                "pairs": pairs,
            }
            result_questions.append(result_q)

            # 构建输出文本
            output_parts.append(f"[第{q.get('id', '')}题]")
            output_parts.append(f"原文: {stem}")
            output_parts.append(f"译文: {translated_stem}")
            if options:
                for opt, opt_t in zip(options, translated_options or options):
                    output_parts.append(f"  {opt}")
                    output_parts.append(f"  {opt_t}")
            output_parts.append("")

        except Exception as exc:
            logger.error("翻译题目 %s 失败: %s", q.get("id", "?"), exc)
            # 失败时保留原文
            result_q = {
                "id": q.get("id", ""),
                "type": q_type,
                "section_title": q_title,
                "stem": stem,
                "stem_translated": "",
                "options": options,
                "options_translated": [],
                "pairs": [],
                "error": str(exc),
            }
            result_questions.append(result_q)

    return ShardResult(
        index=shard.index,
        output="\n".join(output_parts),
        questions=result_questions,
        success=True,
    )


async def translate_english_paper(
    ocr_text: str,
    parsed_structure: dict[str, Any],
    *,
    mode: str = "bilingual",
) -> dict[str, Any]:
    """
    同步（非 Celery）英语试卷翻译入口。

    :param ocr_text: OCR 识别文本
    :param parsed_structure: ExamParser 解析结果
    :param mode: 翻译模式 (full/bilingual)
    :return: 翻译结果结构
    """
    from app.services.exam.sharded_processor import (
        create_shards,
        process_shards_parallel,
        merge_shard_results,
    )

    shards = create_shards(parsed_structure)
    results = await process_shards_parallel(shards, process_english_shard)
    merged = merge_shard_results(results)

    # 提取词汇信息（考研英语核心词）
    vocabulary = _extract_vocabulary(merged.get("questions", []))

    return {
        "mode": mode,
        "questions": merged.get("questions", []),
        "output": merged.get("output", ""),
        "vocabulary": vocabulary,
        "total_questions": len(merged.get("questions", [])),
        "errors": merged.get("errors", []),
    }


def _extract_vocabulary(questions: list[dict[str, Any]]) -> list[dict[str, str]]:
    """从英语试卷题目中提取生词列表（简化版，基于词频/长度判断）。"""
    words_set: set[str] = set()
    vocabulary: list[dict[str, str]] = []

    # 常见考研核心词（简化判断：6+ 字母的英文词）
    for q in questions:
        stem = q.get("stem", "")
        # 简单分词
        import re
        words = re.findall(r"\b[a-zA-Z]{6,}\b", stem)
        for w in words:
            w_lower = w.lower()
            if w_lower not in words_set:
                words_set.add(w_lower)
                vocabulary.append({
                    "word": w_lower,
                    "context": stem[:100] + "..." if len(stem) > 100 else stem,
                })

    # 限制返回数量
    return vocabulary[:100]
