"""
数学试卷专项处理 — 逐题答案解析 + 考点标注 + LaTeX 公式支持。

处理链:
1. 接收分片 (Shard)
2. 调用 AIService 为每道题生成答案 + 解析 + 考点
3. 汇总逐题结果
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.exam.sharded_processor import Shard, ShardResult

logger = logging.getLogger(__name__)

# 数学试卷解析专用 system prompt
MATH_EXAM_SYSTEM_PROMPT = """你是考研数学阅卷专家。请按以下格式输出每道题的解析：

## 第X题

### 答案
直接给出最终答案（选择题给选项字母，填空题给数值/表达式）

### 考点
列出本题考查的核心知识点（2-4个）

### 解题步骤
1. 第一步...
2. 第二步...
...

### 易错点
指出常见错误

---

要求：
- 数学公式使用 LaTeX：行内 $...$，独立 $$...$$
- 选择题需说明排除其他选项的理由
- 解答题需完整推导过程
- 语言简洁，不废话"""


async def process_math_shard(shard: Shard) -> ShardResult:
    """
    处理数学试卷的一个分片：逐题生成答案解析。

    :param shard: 待处理分片
    :return: 分片处理结果
    """
    from app.services.ai_service import get_ai_service

    ai = get_ai_service()

    result_questions: list[dict[str, Any]] = []
    output_parts: list[str] = []

    # 构建分片提示
    questions_text = shard.text
    prompt = (
        f"请解析以下考研数学试卷中的 {len(shard.questions)} 道题目：\n\n"
        f"{questions_text}\n\n"
        "请严格按照指定格式逐题输出解析。"
    )

    # 调用 AI 生成解析
    try:
        messages = [
            {"role": "system", "content": MATH_EXAM_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        ai_response = await ai.chat_complete(messages)

        # 解析 AI 输出，提取每题结果
        parsed_answers = _parse_math_response(ai_response, shard.questions)

        for q in shard.questions:
            q_id = q.get("id", "")
            stem = q.get("stem", "")
            q_type = q.get("_section_type", "other")
            q_title = q.get("_section_title", "")

            answer_data = parsed_answers.get(q_id, {})

            result_q: dict[str, Any] = {
                "id": q_id,
                "type": q_type,
                "section_title": q_title,
                "stem": stem,
                "options": q.get("options", []),
                "answer": answer_data.get("answer", ""),
                "analysis": answer_data.get("analysis", ""),
                "key_points": answer_data.get("key_points", ""),
                "common_mistakes": answer_data.get("common_mistakes", ""),
            }
            result_questions.append(result_q)

            # 构建输出
            output_parts.append(f"[第{q_id}题] {stem[:80]}...")
            if answer_data.get("answer"):
                output_parts.append(f"答案: {answer_data['answer']}")
            output_parts.append("")

    except Exception as exc:
        logger.error("数学分片 %d 处理失败: %s", shard.index, exc)
        return ShardResult(
            index=shard.index,
            success=False,
            error=str(exc),
        )

    return ShardResult(
        index=shard.index,
        output="\n".join(output_parts),
        questions=result_questions,
        success=True,
    )


async def analyze_math_paper(
    ocr_text: str,
    parsed_structure: dict[str, Any],
) -> dict[str, Any]:
    """
    同步（非 Celery）数学试卷解析入口。

    :param ocr_text: OCR 识别文本
    :param parsed_structure: ExamParser 解析结果
    :return: 解析结果结构
    """
    from app.services.exam.sharded_processor import (
        create_shards,
        process_shards_parallel,
        merge_shard_results,
    )

    shards = create_shards(parsed_structure)
    results = await process_shards_parallel(shards, process_math_shard)
    merged = merge_shard_results(results)

    return {
        "questions": merged.get("questions", []),
        "output": merged.get("output", ""),
        "total_questions": len(merged.get("questions", [])),
        "errors": merged.get("errors", []),
    }


def _parse_math_response(
    ai_response: str,
    questions: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    """
    解析 AI 输出，提取每题的答案/解析/考点。

    尝试按 "## 第X题" 格式拆分，若拆分失败则整段作为第一题的答案。
    """
    import re

    parsed: dict[str, dict[str, str]] = {}

    # 按 "## 第X题" 或 "### 第X题" 拆分
    sections = re.split(r"#{2,3}\s*第\s*([^\s#]+)\s*题", ai_response)

    if len(sections) > 2:
        # sections[0] 是前导文本，之后交替出现 (题号, 内容)
        for i in range(1, len(sections) - 1, 2):
            q_id_raw = sections[i].strip()
            q_content = sections[i + 1].strip() if i + 1 < len(sections) else ""

            # 标准化题号
            q_id = _normalize_question_id(q_id_raw, questions)

            # 提取各部分
            answer = _extract_section(q_content, "答案")
            analysis = _extract_section(q_content, "解题步骤") or _extract_section(q_content, "解析")
            key_points = _extract_section(q_content, "考点")
            mistakes = _extract_section(q_content, "易错点")

            parsed[q_id] = {
                "answer": answer,
                "analysis": analysis,
                "key_points": key_points,
                "common_mistakes": mistakes,
            }
    else:
        # 无法拆分，整段作为第一题的答案
        if questions:
            first_id = questions[0].get("id", "1")
            parsed[first_id] = {
                "answer": "",
                "analysis": ai_response,
                "key_points": "",
                "common_mistakes": "",
            }

    return parsed


def _normalize_question_id(raw: str, questions: list[dict[str, Any]]) -> str:
    """将题号标准化（如 "一" → "1", "2" → "2"）。"""
    # 中文数字映射
    cn_map = {
        "一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
        "六": "6", "七": "7", "八": "8", "九": "9", "十": "10",
    }
    normalized = raw.strip()
    if normalized in cn_map:
        normalized = cn_map[normalized]

    # 尝试匹配现有题目 ID
    for q in questions:
        if q.get("id") == normalized:
            return normalized
        if q.get("id") == raw.strip():
            return raw.strip()

    return normalized


def _extract_section(content: str, section_name: str) -> str:
    """从题目内容中提取指定小节。"""
    import re

    # 匹配 "### 答案" 到下一个 "###" 之间的内容
    pattern = rf"###\s*{re.escape(section_name)}\s*\n(.*?)(?=###|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 尝试无 ### 的简单模式
    pattern2 = rf"{re.escape(section_name)}[：:]\s*(.+?)(?=\n(?:答案|考点|解题|易错)|\Z)"
    match2 = re.search(pattern2, content, re.DOTALL)
    if match2:
        return match2.group(1).strip()

    return ""
