"""掌上考研本地数据路径（clawer 输出目录 E:\\Kaoyan\\re）。"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DATA_DIR = Path(r"E:\Kaoyan\re")


def kaoyan_data_dir() -> Path:
    raw = (os.environ.get("KAOYAN_DATA_DIR") or "").strip()
    return Path(raw) if raw else DEFAULT_DATA_DIR


def kaoyan_full_json() -> Path:
    base = kaoyan_data_dir()
    latest = base / "latest" / "syl-schools-full.json"
    if latest.exists():
        return latest
    root = base / "syl-schools-full.json"
    if root.exists():
        return root
    return latest


def kaoyan_schools_json() -> Path:
    base = kaoyan_data_dir()
    latest = base / "latest" / "schools.json"
    if latest.exists():
        return latest
    return base / "schools.json"
