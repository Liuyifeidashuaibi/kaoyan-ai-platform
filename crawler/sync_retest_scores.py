#!/usr/bin/env python3
"""
项目院校复试线同步：抓取 → 入库 → 通知择校页刷新
============================================================
范围：仅 Supabase universities 表内院校
绑定：复试线只写入已有 majors（major_id + university_id）
联动：同步更新 majors.college，供专业/复试线页按学院分组

用法：
  python sync_retest_scores.py                    # 全量 148 校
  python sync_retest_scores.py --school 武汉大学
  python sync_retest_scores.py --import-only      # 仅导入已有 CSV
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_here = Path(__file__).parent
CSV_OUT = _here / "data" / "kaoyan_scores_985_211.csv"


def run(cmd: list[str], label: str) -> int:
    print(f"\n═══ {label} ═══", flush=True)
    print(" ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=str(_here))


def main() -> None:
    parser = argparse.ArgumentParser(description="项目院校复试线同步")
    parser.add_argument("--school", default=None, help="仅处理指定院校")
    parser.add_argument("--years", default="2025-2026")
    parser.add_argument("--import-only", action="store_true", help="跳过抓取，仅导入 CSV")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=1, help="并行院校数（默认串行）")
    args = parser.parse_args()

    py = sys.executable

    if not args.import_only:
        crawl_cmd = [
            py,
            str(_here / "crawl_kaoyan_scores_csv.py"),
            "--output",
            str(CSV_OUT),
            "--years",
            args.years,
            "--no-chsi",
            "--concurrency",
            str(args.concurrency),
        ]
        if args.school:
            crawl_cmd.extend(["--school", args.school])
        if args.offset:
            crawl_cmd.extend(["--offset", str(args.offset)])
        rc = run(crawl_cmd, "抓取复试线（项目院校）")
        if rc != 0:
            sys.exit(rc)

    import_rc = run(
        [
            py,
            str(_here / "import_kaoyan_scores_batch.py"),
            "--input",
            str(CSV_OUT),
            "--years",
            args.years,
        ],
        "入库 scores + 补全学院",
    )
    if import_rc != 0:
        sys.exit(import_rc)

    run([py, str(_here / "notify_frontend.py"), "sync_retest_scores"], "通知择校页刷新")
    print("\n复试线同步完成。", flush=True)


if __name__ == "__main__":
    main()
