#!/usr/bin/env python3
"""删除 Supabase majors 表中违反唯一键的重复行（保留 updated_at 最新的一条）。"""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

_here = Path(__file__).parent
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")
load_dotenv(_here.parent / ".env.local")


def main() -> None:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")

    sb = create_client(url, key)
    offset = 0
    all_rows: list[dict] = []
    while True:
        res = (
            sb.table("majors")
            .select("id, university_id, code, degree_type, study_mode, updated_at")
            .range(offset, offset + 999)
            .execute()
        )
        batch = res.data or []
        all_rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000

    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in all_rows:
        key = (
            row["university_id"],
            row["code"],
            row["degree_type"],
            row["study_mode"],
        )
        groups[key].append(row)

    to_delete: list[str] = []
    for key, rows in groups.items():
        if len(rows) <= 1:
            continue
        rows.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
        for dup in rows[1:]:
            to_delete.append(dup["id"])

    print(f"majors 总数: {len(all_rows)}")
    print(f"重复组: {sum(1 for g in groups.values() if len(g) > 1)}")
    print(f"待删除重复行: {len(to_delete)}")

    if not to_delete:
        print("无重复专业，跳过。")
        return

    for i in range(0, len(to_delete), 50):
        chunk = to_delete[i : i + 50]
        sb.table("majors").delete().in_("id", chunk).execute()

    print(f"已删除 {len(to_delete)} 条重复专业。")


if __name__ == "__main__":
    main()
