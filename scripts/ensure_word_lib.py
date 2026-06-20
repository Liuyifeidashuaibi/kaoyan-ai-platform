#!/usr/bin/env python3
"""Ensure word_lib.db is populated from ECDICT data if available."""

from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.modules.word_dict.database import init_word_lib_db  # noqa: E402

ECDICT_DIR = ROOT / "data" / "ecdict"
STARDICT = ECDICT_DIR / "stardict.db"
CSV = ECDICT_DIR / "ecdict.csv"
MIN_IMPORTED = 100_000
PY = sys.executable


def _run(script: str, *args: str) -> None:
    subprocess.run([PY, str(ROOT / "scripts" / script), *args], check=True)


def _word_count(db_path: Path) -> int:
    if not db_path.is_file():
        return 0
    init_word_lib_db()
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM word_lib").fetchone()[0]
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-import even if word_lib looks populated")
    args = parser.parse_args()

    db_path = get_settings().word_lib_db_path
    count = _word_count(db_path)

    if count >= MIN_IMPORTED and not args.force:
        print(f"word_lib OK ({count} entries)")
        return

    if STARDICT.is_file():
        print(f"Found {STARDICT.name}, importing stardict.db ...")
        _run("import_ecdict_stardict.py")
        return

    if CSV.is_file():
        print(f"Found {CSV.name}, importing ecdict.csv ...")
        _run("import_ecdict.py", "--csv", str(CSV))
        return

    if count == 0:
        print("No ECDICT file found; seeding core vocabulary ...")
        data = ROOT / "scripts" / "data" / "core_en_words.json"
        if not data.is_file():
            _run("generate_core_words.py")
        _run("seed_word_lib_core.py")
        return

    print(f"word_lib has {count} entries; no ECDICT file in {ECDICT_DIR}")


if __name__ == "__main__":
    main()
