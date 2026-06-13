"""择校 AI 补全流水线共享常量"""

from __future__ import annotations

import os
import re
from datetime import date as _date

TARGET_YEAR = int(os.environ.get("SCHOOL_CONTENT_YEAR", "2025"))
SCORE_YEARS = [2025, 2026]

# 2025 考研国家线（一区总分，用于推算 line_diff）
NATIONAL_LINE_TOTAL: dict[str, int] = {
    "哲学": 323,
    "经济学": 323,
    "法学": 323,
    "教育学": 331,
    "文学": 351,
    "历史学": 336,
    "理学": 274,
    "工学": 273,
    "农学": 251,
    "医学": 296,
    "军事学": 260,
    "管理学": 323,
    "艺术学": 362,
}

# 6 位专业代码前 2 位 → 学科门类（专硕常见）
CODE_PREFIX_CATEGORY: dict[str, str] = {
    "01": "哲学",
    "02": "经济学",
    "03": "法学",
    "04": "教育学",
    "05": "文学",
    "06": "历史学",
    "07": "理学",
    "08": "工学",
    "09": "农学",
    "10": "医学",
    "11": "军事学",
    "12": "管理学",
    "13": "艺术学",
    "14": "艺术学",
}


def national_line_for_major(
    code: str | None,
    subject_category: str | None,
    degree_type: str | None = None,
) -> int | None:
    """根据专业代码/学科门类估算国家线总分（一区）。"""
    if subject_category and subject_category in NATIONAL_LINE_TOTAL:
        return NATIONAL_LINE_TOTAL[subject_category]
    digits = "".join(c for c in str(code or "") if c.isdigit())
    if len(digits) >= 2:
        cat = CODE_PREFIX_CATEGORY.get(digits[:2])
        if cat:
            return NATIONAL_LINE_TOTAL.get(cat)
    if degree_type == "专硕":
        return NATIONAL_LINE_TOTAL.get("工学", 273)
    return None


def infer_rec_type(title: str) -> str:
    if "夏令营" in title:
        return "夏令营"
    if "预推免" in title:
        return "预推免"
    return "正式推免"


def infer_rec_status(start: str | None, end: str | None) -> str:
    today = _date.today().isoformat()
    if start and today < start[:10]:
        return "未开始"
    if end and today > end[:10]:
        return "已结束"
    if start or end:
        return "报名中"
    return "未开始"


_DATE_RE = re.compile(r"(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})")


def extract_dates_from_text(text: str) -> tuple[str | None, str | None]:
    found: list[str] = []
    for y, m, d in _DATE_RE.findall(text or ""):
        found.append(f"{y}-{int(m):02d}-{int(d):02d}")
    if not found:
        return None, None
    found.sort()
    if len(found) == 1:
        return found[0], None
    return found[0], found[-1]
