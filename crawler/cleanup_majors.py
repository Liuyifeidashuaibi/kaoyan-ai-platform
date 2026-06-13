"""清理 majors 表中的噪声数据，并修正错误的 college 字段"""
import argparse
from dotenv import load_dotenv

load_dotenv()

import os
from supabase import create_client

from crawl_basic_once import is_valid_major_name, is_likely_major_code, _is_likely_college_name

SUBJECT_CATEGORIES = {
    "哲学", "经济学", "法学", "教育学", "文学", "历史学", "理学", "工学",
    "农学", "医学", "军事学", "管理学", "艺术学",
}

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def load_all_majors():
    offset = 0
    all_rows = []
    while True:
        r = (
            sb.table("majors")
            .select("id,name,code,college,first_discipline,subject_category")
            .range(offset, offset + 999)
            .execute()
        )
        rows = r.data or []
        all_rows.extend(rows)
        if len(rows) < 1000:
            break
        offset += 1000
    return all_rows


def batch_delete(ids: list[str], chunk_size: int = 80) -> int:
    deleted = 0
    for i in range(0, len(ids), chunk_size):
        chunk = ids[i : i + chunk_size]
        sb.table("majors").delete().in_("id", chunk).execute()
        deleted += len(chunk)
        print(f"  已删除 {deleted}/{len(ids)} ...")
    return deleted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--delete-only",
        action="store_true",
        help="仅删除噪声专业，不批量修正 college",
    )
    args = parser.parse_args()

    all_rows = load_all_majors()
    to_delete: list[str] = []
    to_fix: list[dict] = []

    for row in all_rows:
        mid = row["id"]
        name = row.get("name") or ""
        code = (row.get("code") or "").replace(" ", "")
        college = (row.get("college") or "").strip()
        first_d = (row.get("first_discipline") or "").strip()
        subject = (row.get("subject_category") or "").strip()

        digits = "".join(c for c in code if c.isdigit())
        if not is_valid_major_name(name) or not is_likely_major_code(digits):
            to_delete.append(mid)
            continue

        if args.delete_only:
            continue

        should_clear_college = (
            not college
            or college == "未知学院"
            or college == first_d
            or college == subject
            or college in SUBJECT_CATEGORIES
            or not _is_likely_college_name(college)
        )
        if should_clear_college and college:
            to_fix.append({"id": mid, "college": ""})

    print(f"总记录: {len(all_rows)}")
    print(f"待删除噪声: {len(to_delete)}")
    if not args.delete_only:
        print(f"待修正 college: {len(to_fix)}")

    deleted = batch_delete(to_delete) if to_delete else 0

    fixed_college = 0
    if not args.delete_only and to_fix:
        for i in range(0, len(to_fix), 50):
            chunk = to_fix[i : i + 50]
            for patch in chunk:
                sb.table("majors").update({"college": ""}).eq("id", patch["id"]).execute()
            fixed_college += len(chunk)
            if fixed_college % 500 == 0 or fixed_college == len(to_fix):
                print(f"  已修正 {fixed_college}/{len(to_fix)} ...")

    print(f"已删除 {deleted} 条，已修正 college {fixed_college} 条")


if __name__ == "__main__":
    main()
