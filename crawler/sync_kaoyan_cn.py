#!/usr/bin/env python3
"""
掌上考研数据发布：读取 E:\\Kaoyan\\re JSON → 入库 Supabase → 通知前端

爬虫在 E:\\Kaoyan\\clawer 独立运行；本脚本只负责发布到网站。

用法：
  python sync_kaoyan_cn.py              # 从 re 入库（默认）
  python sync_kaoyan_cn.py --import-only  # 同上
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_here = Path(__file__).parent


def main() -> None:
    parser = argparse.ArgumentParser(description="掌上考研 JSON 发布到 Supabase")
    parser.add_argument("--import-only", action="store_true", help="仅入库（默认行为）")
    parser.add_argument("--years", default="2025-2026")
    args = parser.parse_args()

    py = sys.executable
    import_script = _here / "import_kaoyan_full.py"
    cmd = [py, str(import_script), "--years", args.years]

    print("\n═══ 发布择校数据（re → Supabase）═══", flush=True)
    print(" ".join(cmd), flush=True)
    rc = subprocess.call(cmd, cwd=str(_here.parent))
    if rc != 0:
        sys.exit(rc)

    print("\n择校数据已发布到网站。", flush=True)


if __name__ == "__main__":
    main()
