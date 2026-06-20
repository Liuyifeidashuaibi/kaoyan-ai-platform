#!/usr/bin/env python3
"""
从 ECDICT 官方 stardict.db 导入到 word_lib.db

用法:
  python scripts/import_ecdict_stardict.py
  python scripts/import_ecdict_stardict.py --db-path data/ecdict/stardict.db
  python scripts/import_ecdict_stardict.py --limit 10000
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.modules.word_dict.database import init_word_lib_db  # noqa: E402

DEFAULT_STARDICT = ROOT / "data" / "ecdict" / "stardict.db"
BATCH = 50_000

INSERT_SQL = """
INSERT OR REPLACE INTO word_lib
(word, phonetic, definition, translation, pos, collins, oxford, tag, bnc, frq, exchange, detail, audio, ai_generated)
SELECT word, phonetic, definition, translation, pos,
       COALESCE(collins, 0), COALESCE(oxford, 0), tag,
       COALESCE(bnc, 0), COALESCE(frq, 0), exchange, detail, audio, 0
FROM src.stardict
WHERE id > ? AND id <= ?
"""


def import_stardict(
    src_path: Path,
    dst_path: Path,
    batch_size: int = BATCH,
    limit: int | None = None,
) -> int:
    if not src_path.is_file():
        raise SystemExit(f"stardict.db not found: {src_path}")

    init_word_lib_db()
    src = sqlite3.connect(src_path)
    try:
        min_id, max_id = src.execute("SELECT MIN(id), MAX(id) FROM stardict").fetchone()
        if min_id is None:
            raise SystemExit("stardict table is empty")
        if limit is not None:
            max_id = min(max_id, min_id + limit - 1)
        total_src = src.execute(
            "SELECT COUNT(*) FROM stardict WHERE id BETWEEN ? AND ?",
            (min_id, max_id),
        ).fetchone()[0]
    finally:
        src.close()

    dst = sqlite3.connect(dst_path)
    dst.execute("PRAGMA journal_mode=WAL")
    dst.execute("PRAGMA synchronous=OFF")
    dst.execute("PRAGMA temp_store=MEMORY")
    dst.execute("ATTACH DATABASE ? AS src", (str(src_path.resolve()),))

    imported = 0
    started = time.time()
    cursor = min_id
    while cursor <= max_id:
        end = min(cursor + batch_size - 1, max_id)
        dst.execute(INSERT_SQL, (cursor - 1, end))
        dst.commit()
        imported += end - cursor + 1
        elapsed = time.time() - started
        rate = imported / elapsed if elapsed > 0 else 0
        print(
            f"imported {imported}/{total_src} rows ({rate:.0f}/s) ...",
            flush=True,
        )
        cursor = end + 1

    count = dst.execute("SELECT COUNT(*) FROM word_lib").fetchone()[0]
    dst.execute("DETACH DATABASE src")
    dst.close()
    print(f"Done. word_lib rows: {count}")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Import ECDICT stardict.db into word_lib.db")
    parser.add_argument("--db-path", default=str(DEFAULT_STARDICT), help="Path to stardict.db")
    parser.add_argument("--out", default="", help="Override word_lib.db path")
    parser.add_argument("--batch-size", type=int, default=BATCH)
    parser.add_argument("--limit", type=int, default=None, help="Max source rows for testing")
    args = parser.parse_args()

    src_path = Path(args.db_path)
    dst_path = Path(args.out) if args.out else get_settings().word_lib_db_path
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Source: {src_path}")
    print(f"Target: {dst_path}")
    import_stardict(src_path, dst_path, batch_size=args.batch_size, limit=args.limit)


if __name__ == "__main__":
    main()
