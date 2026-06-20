#!/usr/bin/env python3
"""测试 /api/word-query 双层查询（需登录 token 或本地直连 backend）。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.modules.word_dict.database import get_word_lib_db, init_word_lib_db
from app.modules.word_dict.service import get_word_dict_service


async def main() -> None:
    init_word_lib_db()
    db = next(get_word_lib_db())
    svc = get_word_dict_service()
    for word in ("protocol", "macro", "nonexistentwordxyz"):
        hover = await svc.query(db, word, mode="hover")
        print(word, "=>", hover.model_dump() if hover else None)


if __name__ == "__main__":
    asyncio.run(main())
