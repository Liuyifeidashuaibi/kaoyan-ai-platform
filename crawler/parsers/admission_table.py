"""规则解析拟录取名单表格（AI 兜底）。"""

from __future__ import annotations

import re
from typing import Any

_SCORE_RE = re.compile(r"\b(\d{2,3})\b")
_CODE_RE = re.compile(r"\b(\d{6})\b")


def parse_admission_table_text(
    text: str,
    *,
    school: str = "",
    year: int = 2025,
) -> list[dict[str, Any]]:
    """
    从纯文本/表格文本中规则提取拟录取记录。
    适用于 HTML 表格转文本或 Excel 转 TSV。
    """
    if not text or len(text) < 40:
        return []

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    rows: list[dict[str, Any]] = []

    for line in lines:
        if not any(k in line for k in ("拟录取", "录取", "总分", "初试", "成绩", "专业")):
            # 行内需有分数特征
            if not _SCORE_RE.search(line):
                continue
        codes = _CODE_RE.findall(line)
        scores = [int(s) for s in _SCORE_RE.findall(line) if 200 <= int(s) <= 500]
        if not scores:
            continue
        # 通常最后一列或最大合理值为初试总分
        initial = max(scores) if scores else None
        if initial is None or initial < 200:
            continue

        major_code = codes[0] if codes else ""
        # 尝试从行内截取专业名（代码前后中文）
        major_name = ""
        if major_code:
            m = re.search(rf"{major_code}\s*([\u4e00-\u9fffA-Za-z（）()·\-\s]{{2,30}})", line)
            if m:
                major_name = m.group(1).strip()[:40]

        college = ""
        for kw in ("学院", "系", "研究院", "中心"):
            m = re.search(rf"([\u4e00-\u9fff]{{2,20}}{kw})", line)
            if m:
                college = m.group(1)
                break

        rows.append({
            "school": school,
            "college": college,
            "major": major_name,
            "major_code": major_code,
            "year": year,
            "initial_score": initial,
            "admission_status": "拟录取",
        })

    # 去重：同专业代码+分数
    dedup: dict[tuple, dict] = {}
    for r in rows:
        key = (r.get("major_code"), r.get("initial_score"))
        dedup[key] = r
    return list(dedup.values())
