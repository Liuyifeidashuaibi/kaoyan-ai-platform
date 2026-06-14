#!/usr/bin/env python3
"""
掌上考研爬虫一键同步：Node 抓取 → JSON 入库 → 通知前端

用法：
  python sync_kaoyan_cn.py              # 增量同步 + 入库
  python sync_kaoyan_cn.py --full       # 全量抓取 + 入库
  python sync_kaoyan_cn.py --import-only  # 仅导入已有 JSON
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_here = Path(__file__).parent
KAOYAN_CN = _here / "kaoyan-cn"


def run(cmd: list[str], label: str) -> int:
    print(f"\n═══ {label} ═══", flush=True)
    print(" ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=str(_here))


def main() -> None:
    parser = argparse.ArgumentParser(description="掌上考研数据同步")
    parser.add_argument("--full", action="store_true", help="全量抓取（默认增量）")
    parser.add_argument("--import-only", action="store_true", help="跳过抓取，仅入库")
    parser.add_argument("--years", default="2025-2026")
    args = parser.parse_args()

    py = sys.executable
    node = "node"

    if not args.import_only:
        npm_install = subprocess.call(
            ["npm", "install", "--prefix", str(KAOYAN_CN)],
            cwd=str(_here),
        )
        if npm_install != 0:
            sys.exit(npm_install)

        if args.full:
            crawl_rc = subprocess.call(
                [node, str(KAOYAN_CN / "scripts" / "run-once.js"), "--fresh"],
                cwd=str(KAOYAN_CN),
            )
        else:
            crawl_rc = subprocess.call(
                [node, str(KAOYAN_CN / "scripts" / "sync-once.js")],
                cwd=str(KAOYAN_CN),
            )
        if crawl_rc != 0:
            print(f"爬虫退出码 {crawl_rc}", file=sys.stderr)
            sys.exit(crawl_rc)

    import_rc = run(
        [
            py,
            str(_here / "import_kaoyan_full.py"),
            "--years",
            args.years,
        ],
        "JSON 入库",
    )
    if import_rc != 0:
        sys.exit(import_rc)

    print("\n掌上考研同步完成。", flush=True)


if __name__ == "__main__":
    main()
