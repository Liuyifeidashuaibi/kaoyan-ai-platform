"""失败任务队列（JSON 文件）。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("crawler.schedulers")

FAILED_QUEUE = Path(__file__).resolve().parents[1] / "logs" / "failed_tasks.json"


def push_failed_task(task: dict) -> None:
    FAILED_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    tasks: list[dict] = []
    if FAILED_QUEUE.exists():
        try:
            tasks = json.loads(FAILED_QUEUE.read_text(encoding="utf-8"))
        except Exception:
            tasks = []
    task["failed_at"] = datetime.now(timezone.utc).isoformat()
    tasks.append(task)
    FAILED_QUEUE.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
    log.warning("任务入失败队列: %s", task.get("school") or task.get("url"))

    try:
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from storage import get_client, upsert_crawl_task

        sb = get_client()
        upsert_crawl_task(
            sb,
            university_id=task.get("university_id"),
            school_name=task.get("school"),
            task_type=task.get("mode") or "fetch",
            target_url=task.get("url"),
            status="failed",
            error_message=task.get("error"),
            payload=task,
        )
    except Exception as exc:
        log.debug("crawl_tasks 写入跳过: %s", exc)


def list_failed_tasks() -> list[dict]:
    if not FAILED_QUEUE.exists():
        return []
    try:
        return json.loads(FAILED_QUEUE.read_text(encoding="utf-8"))
    except Exception:
        return []
