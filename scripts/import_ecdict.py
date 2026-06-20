#!/usr/bin/env python3
"""
批量导入 ECDICT ecdict.csv 到 word_lib.db

用法:
  python scripts/import_ecdict.py --csv data/ecdict/ecdict.csv
  python scripts/import_ecdict.py --csv data/ecdict/ecdict.csv --limit 10000  # 测试

CSV 字段: word,phonetic,definition,translation,pos,collins,oxford,tag,bnc,frq,exchange,detail,audio
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.modules.word_dict.database import init_word_lib_db  # noqa: E402


def _int(val: str | None) -> int:
    try:
        return int(val or 0)
    except ValueError:
        return 0


def import_csv(csv_path: Path, db_path: Path, batch_size: int = 5000, limit: int | None = None) -> None:
    init_word_lib_db()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")

    insert_sql = """
        INSERT OR IGNORE INTO word_lib
        (word, phonetic, definition, translation, pos, collins, oxford, tag, bnc, frq, exchange, detail, audio, ai_generated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
    """

    total = 0
    batch: list[tuple] = []

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if limit is not None and total >= limit:
                break
            if not row or not row[0].strip():
                continue
            while len(row) < 13:
                row.append("")
            word, phonetic, definition, translation, pos, collins, oxford, tag, bnc, frq, exchange, detail, audio = row[:13]
            batch.append(
                (
                    word.strip(),
                    phonetic or None,
                    definition or None,
                    translation or None,
                    pos or None,
                    _int(collins),
                    _int(oxford),
                    tag or None,
                    _int(bnc),
                    _int(frq),
                    exchange or None,
                    detail or None,
                    audio or None,
                )
            )
            if len(batch) >= batch_size:
                conn.executemany(insert_sql, batch)
                conn.commit()
                total += len(batch)
                print(f"imported {total} ...", flush=True)
                batch.clear()

    if batch:
        conn.executemany(insert_sql, batch)
        conn.commit()
        total += len(batch)

    conn.close()
    print(f"Done. Total rows attempted: {total}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import ECDICT CSV into word_lib.db")
    parser.add_argument("--csv", required=True, help="Path to ecdict.csv")
    parser.add_argument("--db", default="", help="Override word_lib.db path")
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--limit", type=int, default=None, help="Max rows for testing")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.is_file():
        raise SystemExit(f"CSV not found: {csv_path}")

    db_path = Path(args.db) if args.db else get_settings().word_lib_db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Target DB: {db_path}")
    import_csv(csv_path, db_path, batch_size=args.batch_size, limit=args.limit)


if __name__ == "__main__":
    main()
