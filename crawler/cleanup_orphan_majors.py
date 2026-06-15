#!/usr/bin/env python3
"""删除 Supabase 中不在最新 JSON 专业目录内的孤儿 majors（及级联 scores）。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

_here = Path(__file__).parent
sys.path.insert(0, str(_here))
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")
load_dotenv(_here.parent / ".env.local")

from import_kaoyan_full import build_major_rows, build_university_row  # noqa: E402
from paths import kaoyan_full_json  # noqa: E402


def main() -> None:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")

    path = kaoyan_full_json()
    with path.open(encoding="utf-8") as f:
        payload = json.load(f)
    schools = payload.get("schools") or []

    sb = create_client(url, key)

    expected_by_uni: dict[str, set[tuple[str, str, str]]] = {}
    uni_names: dict[str, str] = {}

    for school in schools:
        name = (school.get("name") or "").strip()
        if not name:
            continue
        res = sb.table("universities").select("id").eq("name", name).limit(1).execute()
        uid = (res.data or [{}])[0].get("id")
        if not uid:
            continue
        uni_names[uid] = name
        rows = build_major_rows(uid, school)
        expected_by_uni[uid] = {
            (r["code"], r["degree_type"], r["study_mode"]) for r in rows
        }

    total_delete = 0
    for uid, expected in expected_by_uni.items():
        res = (
            sb.table("majors")
            .select("id, code, degree_type, study_mode")
            .eq("university_id", uid)
            .execute()
        )
        orphans = [
            r["id"]
            for r in (res.data or [])
            if (r["code"], r["degree_type"], r["study_mode"]) not in expected
        ]
        if not orphans:
            continue
        for i in range(0, len(orphans), 50):
            chunk = orphans[i : i + 50]
            sb.table("majors").delete().in_("id", chunk).execute()
        total_delete += len(orphans)
        print(f"{uni_names.get(uid, uid)}: 删除孤儿专业 {len(orphans)}")

    print(f"合计删除孤儿专业: {total_delete}")


if __name__ == "__main__":
    main()
