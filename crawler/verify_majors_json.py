#!/usr/bin/env python3
"""校验 JSON 源数据中的专业重复与分数异常（发布前对照）。"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

_here = Path(__file__).parent
sys.path.insert(0, str(_here))

from enrich_constants import SCORE_YEARS  # noqa: E402
from import_kaoyan_full import (  # noqa: E402
    build_major_rows,
    build_score_rows,
    map_degree,
    resolve_input,
)
from paths import kaoyan_full_json  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(kaoyan_full_json()))
    args = parser.parse_args()

    path = resolve_input(args.input)
    with path.open(encoding="utf-8") as f:
        payload = json.load(f)

    schools = payload.get("schools") or []
    dup_keys: list[str] = []
    score_issues: list[str] = []
    allowed_years = set(SCORE_YEARS)

    for school in schools:
        name = (school.get("name") or "").strip()
        uid = f"dry-{name}"
        majors = build_major_rows(uid, school)
        seen: dict[tuple, list[str]] = defaultdict(list)
        for m in majors:
            key = (m["code"], m["degree_type"], m["study_mode"])
            seen[key].append(m.get("college") or "")

        for key, colleges in seen.items():
            if len(colleges) > 1:
                dup_keys.append(
                    f"{name}: {key[0]} {key[1]} {key[2]} — 学院: {', '.join(colleges)}"
                )

        score_rows, skipped = build_score_rows(uid, school, majors, allowed_years)
        expected = len(majors) * len(allowed_years)
        coverage = len(score_rows) / max(expected, 1) * 100
        if coverage < 30 and len(majors) > 5:
            score_issues.append(f"{name}: 分数覆盖率 {coverage:.0f}% (跳过 {skipped})")

        # 源数据 plans 内重复行（导入前会被 dedup）
        plans = (school.get("plans") or {}).get("items") or []
        raw_seen: set[tuple] = set()
        raw_dup = 0
        for item in plans:
            code = re.sub(r"\D", "", str(item.get("special_code") or ""))[:6]
            degree = map_degree(item.get("degree_type_name", ""), item.get("degree_type"))
            study = (item.get("recruit_type_name") or "全日制").strip() or "全日制"
            k = (code, degree, study)
            if k in raw_seen:
                raw_dup += 1
            raw_seen.add(k)
        if raw_dup > 3:
            score_issues.append(f"{name}: 源 plans 重复键 {raw_dup} 条（导入时会合并）")

    print(f"院校数: {len(schools)}")
    print(f"JSON 内可导入专业唯一键冲突（多学院同码）: {len(dup_keys)}")
    for line in dup_keys[:20]:
        print(f"  - {line}")
    if len(dup_keys) > 20:
        print(f"  ... 还有 {len(dup_keys) - 20} 条")

    print(f"分数/覆盖率告警: {len(score_issues)}")
    for line in score_issues[:15]:
        print(f"  - {line}")
    if len(score_issues) > 15:
        print(f"  ... 还有 {len(score_issues) - 15} 条")

    if dup_keys or score_issues:
        sys.exit(1)


if __name__ == "__main__":
    main()
