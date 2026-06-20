"""管理后台写操作审计（文件持久化，不新增数据库表）。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import get_settings


def _audit_path() -> Path:
    path = get_settings().root / "data" / "admin"
    path.mkdir(parents=True, exist_ok=True)
    return path / "audit.jsonl"


def log_admin_action(
    actor: str,
    action: str,
    resource: str = "",
    detail: dict[str, Any] | None = None,
) -> None:
    entry = {
        "time": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "action": action,
        "resource": resource,
        "detail": detail or {},
    }
    try:
        with _audit_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def list_audit_logs(limit: int = 50) -> list[dict[str, Any]]:
    path = _audit_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    items: list[dict[str, Any]] = []
    for line in reversed(lines[-limit:]):
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items
