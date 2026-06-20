"""Smoke-test translator export attachments (txt / docx / pdf)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app.services.export_attachment_service import build_attachment

SAMPLE = "Hello world\nThis is a bilingual export test.\n你好，世界。"


def main() -> int:
    failed = 0
    for fmt in ("txt", "docx", "pdf"):
        try:
            data, filename, mime = build_attachment(SAMPLE, fmt, "Translation Test")
            assert data, "empty payload"
            print(f"[OK] {fmt:4} {filename:30} {len(data):6} bytes  {mime}")
        except Exception as exc:
            failed += 1
            print(f"[FAIL] {fmt}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
