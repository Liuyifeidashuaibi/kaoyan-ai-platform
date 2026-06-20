#!/usr/bin/env python3
"""
写入常用考研词汇样本到 word_lib（ECDICT 全量导入前的快速测试数据）。

用法:
  python scripts/seed_word_lib_sample.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.modules.word_dict.database import get_word_lib_engine, init_word_lib_db
from app.modules.word_dict.models import WordLibEntry
from app.modules.word_dict.database import get_word_lib_session_factory

SAMPLES = [
    {
        "word": "protocol",
        "phonetic": "/ˈprəʊtəkɒl/",
        "pos": "n.",
        "translation": "协议；礼仪；草案",
        "tag": "cet6 ky",
        "kaoyan_gloss": "协议；规程",
        "detail": "identification protocol\n识别方案",
    },
    {
        "word": "macro",
        "phonetic": "/ˈmækrəʊ/",
        "pos": "n.",
        "translation": "宏观；宏",
        "tag": "ky",
        "kaoyan_gloss": "宏观（经济）",
        "detail": "macro announcement\n宏观公告",
    },
    {
        "word": "volatility",
        "phonetic": "/ˌvɒləˈtɪləti/",
        "pos": "n.",
        "translation": "波动性；易变",
        "tag": "ky",
        "kaoyan_gloss": "波动性",
        "detail": "implied volatility\n隐含波动率",
    },
    {
        "word": "identification",
        "phonetic": "/aɪˌdentɪfɪˈkeɪʃn/",
        "pos": "n.",
        "translation": "识别；鉴定；身份证明",
        "tag": "cet6 ky",
        "kaoyan_gloss": "识别；鉴定",
        "detail": "non-spanning identification\n非跨越识别",
    },
    {
        "word": "surface",
        "phonetic": "/ˈsɜːfɪs/",
        "pos": "n.",
        "translation": "表面；曲面",
        "tag": "gk ky",
        "kaoyan_gloss": "表面；曲面",
        "detail": "volatility surface\n波动率曲面",
    },
]


def main() -> None:
    init_word_lib_db()
    factory = get_word_lib_session_factory()
    db = factory()
    added = 0
    try:
        for item in SAMPLES:
            exists = (
                db.query(WordLibEntry)
                .filter(WordLibEntry.word == item["word"])
                .first()
            )
            if exists:
                continue
            db.add(WordLibEntry(**item, ai_generated=0))
            added += 1
        db.commit()
    finally:
        db.close()
    print(f"Sample words seeded: {added} new, db={get_word_lib_engine().url}")


if __name__ == "__main__":
    main()
