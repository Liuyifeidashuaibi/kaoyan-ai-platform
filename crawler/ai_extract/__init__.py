"""AI 结构化抽取 — 仅用于公告正文，不用于页面发现。"""

from __future__ import annotations

import logging
import re
from typing import Any

log = logging.getLogger("crawler.ai_extract")


def extract_structured(content: str, *, year: int | None = None, school: str = "") -> list[dict[str, Any]]:
    """调用千问从公告正文抽取复试分数线。"""
    import asyncio
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from llm_parser import qwen_extract_scores  # noqa: WPS433

    yr = year or 2025
    try:
        rows = asyncio.run(qwen_extract_scores(content, yr, majors_hint=school))
    except Exception as exc:
        log.error("AI 抽取失败: %s", exc)
        return []

    out: list[dict[str, Any]] = []
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        return []

    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append({
            "school": row.get("school") or school,
            "college": row.get("college") or "",
            "major": row.get("major") or row.get("name") or "",
            "major_code": _norm_code(row.get("major_code") or row.get("code")),
            "year": str(row.get("year") or yr),
            "score_line": {
                "total_score": row.get("total_score"),
                "politics_score": row.get("politics_score"),
                "english_score": row.get("english_score"),
                "major_one_score": row.get("professional1_score"),
                "major_two_score": row.get("professional2_score"),
            },
            "source_confidence": 0.85,
        })
    return out


def extract_admission_records(
    content: str,
    *,
    year: int | None = None,
    school: str = "",
    content_hash: str | None = None,
) -> list[dict[str, Any]]:
    """规则解析优先，AI 补充。"""
    import asyncio
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from llm_parser import qwen_extract_admissions  # noqa: WPS433
    from parsers.admission_table import parse_admission_table_text  # noqa: WPS433

    yr = year or 2025
    rule_rows = parse_admission_table_text(content, school=school, year=yr)

    try:
        rows = asyncio.run(
            qwen_extract_admissions(content, yr, majors_hint=school, content_hash=content_hash)
        )
    except Exception as exc:
        log.error("拟录取 AI 抽取失败: %s", exc)
        return rule_rows

    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        return rule_rows

    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        initial = _to_int(row.get("initial_score") or row.get("total_score"))
        if initial is None:
            continue
        out.append({
            "school": row.get("school") or school,
            "college": row.get("college") or "",
            "major": row.get("major") or row.get("name") or "",
            "major_code": _norm_code(row.get("major_code") or row.get("code")),
            "year": int(row.get("year") or yr),
            "candidate_no": _clean_text(row.get("candidate_no")),
            "candidate_name": _clean_text(row.get("candidate_name") or row.get("name")),
            "initial_score": initial,
            "retest_score": _to_int(row.get("retest_score")),
            "final_score": _to_int(row.get("final_score")),
            "admission_status": row.get("admission_status") or "拟录取",
        })

    if len(out) >= len(rule_rows):
        return out
    # 合并去重
    seen: set[tuple] = set()
    merged: list[dict[str, Any]] = []
    for r in out + rule_rows:
        key = (r.get("major_code"), r.get("initial_score"), r.get("candidate_no"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(r)
    return merged


def _norm_code(code: Any) -> str:
    if not code:
        return ""
    digits = re.sub(r"\D", "", str(code))
    return digits[:6] if len(digits) >= 6 else ""


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
