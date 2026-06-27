"""
Agent 任务日志服务 — 持久化全链路审计日志。

记录每次 Agent 任务的：
  - 任务 ID、会话 ID、用户输入
  - 每轮 ReAct 循环的思考内容、工具调用、执行结果
  - 最终输出、生成文件
  - 执行时长、错误信息

存储方式：PostgreSQL 主存储 + 内存热查询缓存（商用正式环境）。
替代旧的内存字典方案，任务日志重启不丢失，满足企业商用交付要求。

对外接口签名与旧版完全兼容——调用方（agent_mode_service.py）零改动。
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import orm

from app.database import AgentGeneratedFile, AgentTask, AgentTaskStep, SessionLocal

logger = logging.getLogger(__name__)


class TaskLogger:
    """
    任务日志管理器 — Postgres 持久化 + 内存缓存加速。

    写路径：同步写 Postgres（create_task / log_step / finish_task）
    读路径：优先查内存缓存，miss 时查 Postgres 回填

    保持全局单例模式，与旧版兼容。
    """

    def __init__(self, max_cache: int = 500) -> None:
        self._cache: dict[str, dict[str, Any]] = {}
        self._max_cache = max_cache

    # ── 内部辅助 ────────────────────────────────────────────

    def _db_session(self):
        """获取数据库 Session（每次调用新 Session，用完由调用方确保 close）。"""
        return SessionLocal()

    def _cache_put(self, task_id: str, data: dict[str, Any]) -> None:
        """更新内存缓存。"""
        self._cache[task_id] = data
        if len(self._cache) > self._max_cache:
            # LRU-like: 按时间戳删除最旧的
            oldest = sorted(self._cache.items(), key=lambda x: str(x[1].get("started_at", "")))
            for tid, _ in oldest[: len(self._cache) - self._max_cache]:
                self._cache.pop(tid, None)

    def _cache_get(self, task_id: str) -> dict[str, Any] | None:
        return self._cache.get(task_id)

    @staticmethod
    def _now() -> datetime:
        """当前 UTC 时间（返回 datetime 对象，供 ORM 写入）。"""
        return datetime.utcnow()

    @staticmethod
    def _now_iso(dt: datetime | None = None) -> str:
        """当前 UTC 时间（返回 ISO 字符串，供缓存/返回值用）。"""
        return (dt or datetime.utcnow()).isoformat()

    # ── 任务创建 ────────────────────────────────────────────

    def create_task(self, session_id: str, user_input: str) -> dict[str, Any]:
        """
        创建新任务日志 — 写入 Postgres + 内存缓存。

        返回与旧版兼容的 task_log 字典（含 task_id）。
        """
        task_id = uuid.uuid4().hex[:12]
        now = datetime.utcnow().isoformat()

        # 写 Postgres（用 datetime 对象，兼容 SQLite DateTime 列）
        now_dt = self._now()
        try:
            db = self._db_session()
            try:
                db_task = AgentTask(
                    task_id=task_id,
                    session_id=session_id,
                    user_input=user_input[:5000],
                    status="running",
                    started_at=now_dt,
                )
                db.add(db_task)
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.warning("任务日志写 Postgres 失败，降级为内存: %s", exc)

        # 内存缓存（用 ISO 字符串）
        now_str = self._now_iso(now_dt)
        cache_entry = {
            "task_id": task_id,
            "session_id": session_id,
            "user_input": user_input,
            "status": "running",
            "steps": [],
            "final_output": "",
            "files_generated": [],
            "started_at": now_str,
            "finished_at": "",
            "total_duration_ms": 0.0,
            "error": "",
            "success": False,
        }
        self._cache_put(task_id, cache_entry)

        return cache_entry

    # ── 步骤记录 ────────────────────────────────────────────

    def log_step(
        self,
        task_id: str,
        step_id: int,
        round_idx: int,
        tool_name: str,
        args: dict,
        result: dict,
        status: str = "done",
        error: str = "",
        duration_ms: float = 0.0,
    ) -> None:
        """记录一个工具执行步骤 — 写 Postgres + 更新内存缓存。"""
        now_dt = self._now()
        now_str = self._now_iso(now_dt)
        args_json = json.dumps(args, ensure_ascii=False, default=str) if isinstance(args, dict) else str(args)
        result_json = json.dumps(result, ensure_ascii=False, default=str) if isinstance(result, dict) else str(result)

        # 写 Postgres
        try:
            db = self._db_session()
            try:
                db_step = AgentTaskStep(
                    task_id=task_id,
                    step_id=step_id,
                    round_idx=round_idx,
                    tool_name=tool_name,
                    args=args_json,
                    result=result_json,
                    status=status,
                    error=error,
                    duration_ms=duration_ms,
                    timestamp=now_dt,
                )
                db.add(db_step)
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.warning("步骤日志写 Postgres 失败: %s", exc)

        # 更新内存缓存
        cached = self._cache_get(task_id)
        if cached is not None:
            cached["steps"].append({
                "step_id": step_id,
                "round_idx": round_idx,
                "tool_name": tool_name,
                "args": args,
                "result": result,
                "status": status,
                "error": error,
                "duration_ms": duration_ms,
                "timestamp": now_str,
            })

    # ── 任务完成 ────────────────────────────────────────────

    def finish_task(
        self,
        task_id: str,
        final_output: str = "",
        files: list[dict] | None = None,
        success: bool = True,
        error: str = "",
    ) -> None:
        """标记任务完成 — 更新 Postgres 记录 + 内存缓存。"""
        now_dt = self._now()              # datetime 对象，供 ORM 写入（SQLite DateTime 列严格要求）
        now = now_dt.isoformat()          # ISO 字符串，供内存缓存

        # 更新 Postgres
        try:
            db = self._db_session()
            try:
                db_task = db.query(AgentTask).filter_by(task_id=task_id).first()
                if db_task:
                    db_task.final_output = final_output[:20000] if final_output else ""
                    db_task.finished_at = now_dt
                    start = db_task.started_at or now_dt
                    if isinstance(start, str):
                        start = datetime.fromisoformat(start)
                    db_task.total_duration_ms = (now_dt - start).total_seconds() * 1000
                    db_task.success = success
                    db_task.error = error[:5000] if error else ""
                    db_task.status = "completed" if success else "failed"

                    # 写文件资产记录
                    if files:
                        for f in files:
                            db_file = AgentGeneratedFile(
                                task_id=task_id,
                                object_name=f.get("object_name", f.get("file_path", "")),
                                filename=f.get("filename", ""),
                                format=f.get("format", ""),
                                title=f.get("title", ""),
                                size=f.get("file_size", 0),
                                storage=f.get("storage", "local"),
                                file_url=f.get("file_url", ""),
                            )
                            db.add(db_file)

                    db.commit()
                else:
                    logger.warning("finish_task: 任务不存在 %s", task_id)
            finally:
                db.close()
        except Exception as exc:
            logger.warning("finish_task 写 Postgres 失败: %s", exc)

        # 更新内存缓存
        cached = self._cache_get(task_id)
        if cached is not None:
            cached["final_output"] = final_output
            cached["files_generated"] = files or []
            cached["finished_at"] = now
            if cached["started_at"]:
                try:
                    start = datetime.fromisoformat(cached["started_at"])
                    end = datetime.fromisoformat(now)
                    cached["total_duration_ms"] = (end - start).total_seconds() * 1000
                except Exception:
                    pass
            cached["success"] = success
            cached["status"] = "completed" if success else "failed"
            cached["error"] = error

    # ── 查询接口（兼容旧版） ────────────────────────────────

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """获取任务详情（内存优先，miss 查 Postgres）。"""
        cached = self._cache_get(task_id)
        if cached is not None and cached.get("steps"):
            return cached

        # 查 Postgres
        try:
            db = self._db_session()
            try:
                db_task = db.query(AgentTask).filter_by(task_id=task_id).first()
                if db_task is None:
                    return None

                db_steps = (
                    db.query(AgentTaskStep)
                    .filter_by(task_id=task_id)
                    .order_by(AgentTaskStep.step_id)
                    .all()
                )
                db_files = db.query(AgentGeneratedFile).filter_by(task_id=task_id).all()

                result = {
                    "task_id": db_task.task_id,
                    "session_id": db_task.session_id or "",
                    "user_input": db_task.user_input or "",
                    "status": db_task.status or "running",
                    "steps": [
                        {
                            "step_id": s.step_id,
                            "round_idx": s.round_idx,
                            "tool_name": s.tool_name or "",
                            "args": json.loads(s.args) if s.args else {},
                            "result": json.loads(s.result) if s.result else {},
                            "status": s.status,
                            "error": s.error or "",
                            "duration_ms": s.duration_ms or 0.0,
                            "timestamp": s.timestamp.isoformat() if s.timestamp else "",
                        }
                        for s in db_steps
                    ],
                    "final_output": db_task.final_output or "",
                    "files_generated": [
                        {
                            "filename": f.filename,
                            "file_url": f.file_url,
                            "file_path": f.object_name,
                            "file_size": f.size or 0,
                            "format": f.format,
                            "title": f.title,
                        }
                        for f in db_files
                    ],
                    "started_at": db_task.started_at.isoformat() if db_task.started_at else "",
                    "finished_at": db_task.finished_at.isoformat() if db_task.finished_at else "",
                    "total_duration_ms": db_task.total_duration_ms or 0.0,
                    "success": db_task.success,
                    "error": db_task.error or "",
                }

                # 回填内存缓存
                self._cache_put(task_id, result)
                return result
            finally:
                db.close()
        except Exception as exc:
            logger.warning("get_task 查 Postgres 失败: %s", exc)
            return self._cache_get(task_id)

    def get_recent_tasks(self, limit: int = 20) -> list[dict]:
        """获取最近的任务列表。"""
        # 优先从缓存取（够的话）
        if len(self._cache) >= limit:
            sorted_cache = sorted(
                self._cache.values(),
                key=lambda x: x.get("started_at", ""),
                reverse=True,
            )
            return [
                {
                    "task_id": t["task_id"],
                    "session_id": t.get("session_id", ""),
                    "user_input": (t.get("user_input") or "")[:100],
                    "status": t.get("status", "running"),
                    "steps_count": len(t.get("steps", [])),
                    "started_at": t.get("started_at", ""),
                    "success": t.get("success", False),
                }
                for t in sorted_cache[:limit]
            ]

        # 查 Postgres
        try:
            db = self._db_session()
            try:
                db_tasks = (
                    db.query(AgentTask)
                    .order_by(AgentTask.started_at.desc())
                    .limit(limit)
                    .all()
                )
                return [
                    {
                        "task_id": t.task_id,
                        "session_id": t.session_id or "",
                        "user_input": (t.user_input or "")[:100],
                        "status": t.status or "running",
                        "steps_count": len(t.steps) if t.steps else 0,
                        "started_at": t.started_at.isoformat() if t.started_at else "",
                        "success": t.success,
                    }
                    for t in db_tasks
                ]
            finally:
                db.close()
        except Exception as exc:
            logger.warning("get_recent_tasks 查 Postgres 失败，降级缓存: %s", exc)
            sorted_cache = sorted(
                self._cache.values(),
                key=lambda x: x.get("started_at", ""),
                reverse=True,
            )
            return [
                {
                    "task_id": t["task_id"],
                    "session_id": t.get("session_id", ""),
                    "user_input": (t.get("user_input") or "")[:100],
                    "status": t.get("status", "running"),
                    "steps_count": len(t.get("steps", [])),
                    "started_at": t.get("started_at", ""),
                    "success": t.get("success", False),
                }
                for t in sorted_cache[:limit]
            ]

    def get_task_detail(self, task_id: str) -> dict | None:
        """获取任务详情（含每步工具调用记录）— 兼容旧接口。"""
        return self.get_task(task_id)


# ── 全局单例 ────────────────────────────────────────────

_task_logger = TaskLogger()


def get_task_logger() -> TaskLogger:
    return _task_logger
