#!/usr/bin/env python3
"""
导入常用英语核心词（约 400 个）到 word_lib.db。
覆盖 have / very / the / is 等基础词，不依赖 ECDICT 全量包。

用法:
  python scripts/seed_word_lib_core.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.modules.word_dict.database import (  # noqa: E402
    get_word_lib_engine,
    get_word_lib_session_factory,
    init_word_lib_db,
)
from app.modules.word_dict.models import WordLibEntry  # noqa: E402

DATA_FILE = ROOT / "scripts" / "data" / "core_en_words.json"


def _load_words() -> list[dict]:
    if DATA_FILE.is_file():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return []


def main() -> None:
    words = _load_words()
    if not words:
        print("No core words data found:", DATA_FILE)
        sys.exit(1)

    init_word_lib_db()
    factory = get_word_lib_session_factory()
    db = factory()
    added = 0
    updated = 0
    try:
        for item in words:
            w = item["word"].strip().lower()
            if not w:
                continue
            row = db.query(WordLibEntry).filter(WordLibEntry.word == w).first()
            if row:
                if not row.translation and item.get("translation"):
                    row.translation = item["translation"]
                    row.phonetic = item.get("phonetic") or row.phonetic
                    row.pos = item.get("pos") or row.pos
                    row.kaoyan_gloss = item.get("kaoyan_gloss") or item.get("translation", "").split("；")[0]
                    updated += 1
                continue
            gloss = item.get("kaoyan_gloss") or (item.get("translation") or "").split("；")[0]
            db.add(
                WordLibEntry(
                    word=w,
                    phonetic=item.get("phonetic"),
                    pos=item.get("pos"),
                    translation=item.get("translation"),
                    kaoyan_gloss=gloss,
                    tag=item.get("tag", "core"),
                    ai_generated=0,
                )
            )
            added += 1
        db.commit()
    finally:
        db.close()
    print(
        f"Core words: {added} added, {updated} updated, total file={len(words)}, db={get_word_lib_engine().url}"
    )


if __name__ == "__main__":
    main()
