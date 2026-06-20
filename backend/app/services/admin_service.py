"""
管理后台数据服务 — 通过 Supabase Service Role 读取统计与列表。
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

# Agent 任务队列（文件持久化，不新增数据库表）
_agent_tasks: dict[str, dict[str, Any]] = {}
_error_logs: list[dict[str, Any]] = []
_agent_tasks_lock = threading.Lock()


def _agent_tasks_path() -> Path:
    path = get_settings().root / "data" / "admin"
    path.mkdir(parents=True, exist_ok=True)
    return path / "agent_tasks.json"


def _load_agent_tasks() -> None:
    global _agent_tasks
    file_path = _agent_tasks_path()
    if not file_path.exists():
        return
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            _agent_tasks = raw
    except Exception:
        logger.exception("load agent tasks failed")


def _save_agent_tasks() -> None:
    file_path = _agent_tasks_path()
    try:
        with _agent_tasks_lock:
            file_path.write_text(
                json.dumps(_agent_tasks, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except Exception:
        logger.exception("save agent tasks failed")
        _log_error("agent", "任务持久化失败")


_load_agent_tasks()


def _supabase():
    settings = get_settings()
    url = settings.effective_supabase_url
    key = settings.effective_supabase_service_key
    if not url or not key:
        return None
    from supabase import create_client

    return create_client(url, key)


def _today_start_iso() -> str:
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.isoformat()


async def get_dashboard_metrics() -> dict[str, Any]:
    client = _supabase()
    if not client:
        return {"degraded": True, "degradedReason": "未配置 Supabase", **_mock_dashboard_metrics()}

    today = _today_start_iso()
    try:
        users_total = _count(client, "users")
        posts_total = _count(client, "community_posts", {"deleted_at": "is.null"})
        schools_total = _count(client, "universities")
        majors_total = _count(client, "majors")
        users_today = _count(client, "users", {"created_at": f"gte.{today}"})
        posts_today = _count(
            client,
            "community_posts",
            {"created_at": f"gte.{today}", "deleted_at": "is.null"},
        )
        return {
            "usersTotal": users_total,
            "postsTotal": posts_total,
            "schoolsTotal": schools_total,
            "majorsTotal": majors_total,
            "usersToday": users_today,
            "postsToday": posts_today,
            "degraded": False,
        }
    except Exception:
        logger.exception("dashboard metrics failed")
        _log_error("dashboard", "metrics query failed")
        raise RuntimeError("指标查询失败")


def _mock_dashboard_metrics() -> dict[str, Any]:
    return {
        "usersTotal": 12480,
        "postsTotal": 3291,
        "schoolsTotal": 486,
        "majorsTotal": 8102,
        "usersToday": 42,
        "postsToday": 18,
    }


def _count(client, table: str, extra: dict[str, str] | None = None) -> int:
    q = client.table(table).select("id", count="exact", head=True)
    if extra:
        for key, val in extra.items():
            if val.startswith("gte."):
                q = q.gte(key, val[4:])
            elif val == "is.null":
                q = q.is_(key, "null")
    res = q.execute()
    return res.count or 0


async def get_dashboard_activity(limit: int = 10) -> list[dict[str, Any]]:
    client = _supabase()
    if not client:
        return []

    items: list[dict[str, Any]] = []
    try:
        users = (
            client.table("users")
            .select("id, nickname, email, created_at")
            .order("created_at", desc=True)
            .limit(3)
            .execute()
        )
        for row in users.data or []:
            name = row.get("nickname") or row.get("email") or "新用户"
            items.append(
                {
                    "id": f"user-{row['id']}",
                    "type": "user",
                    "message": f"新用户注册：{name}",
                    "time": row.get("created_at", ""),
                    "href": f"/admin/users",
                }
            )

        posts = (
            client.table("community_posts")
            .select("id, title, created_at, is_hidden")
            .is_("deleted_at", "null")
            .order("created_at", desc=True)
            .limit(3)
            .execute()
        )
        for row in posts.data or []:
            title = (row.get("title") or "无标题")[:40]
            hidden = bool(row.get("is_hidden"))
            items.append(
                {
                    "id": f"post-{row['id']}",
                    "type": "report" if hidden else "post",
                    "message": f"{'隐藏帖' if hidden else '社区新帖'}：{title}",
                    "time": row.get("created_at", ""),
                    "href": "/admin/community/moderation" if hidden else f"/admin/community/posts/{row['id']}",
                }
            )
    except Exception:
        logger.exception("activity feed failed")
        return []

    items.sort(key=lambda x: x.get("time", ""), reverse=True)
    return items[:limit]


def _mock_activity() -> list[dict[str, Any]]:
    return [
        {
            "id": "1",
            "type": "user",
            "message": "新用户注册：张同学",
            "time": datetime.now(timezone.utc).isoformat(),
            "href": "/admin/users",
        },
        {
            "id": "2",
            "type": "post",
            "message": "社区新帖待审核：《浙大计算机复试经验》",
            "time": datetime.now(timezone.utc).isoformat(),
            "href": "/admin/community/moderation",
        },
    ]


async def list_users(page: int = 1, page_size: int = 20, q: str = "") -> dict[str, Any]:
    client = _supabase()
    if not client:
        return {"items": [], "total": 0, "page": page, "pageSize": page_size}

    offset = (page - 1) * page_size
    query = client.table("users").select(
        "id, email, nickname, avatar_url, created_at, display_id",
        count="exact",
    )
    if q.strip():
        query = query.or_(f"nickname.ilike.%{q}%,email.ilike.%{q}%")
    res = query.order("created_at", desc=True).range(offset, offset + page_size - 1).execute()
    return {
        "items": res.data or [],
        "total": res.count or 0,
        "page": page,
        "pageSize": page_size,
    }


async def moderate_post(post_id: str, action: str) -> dict[str, Any]:
    """hide / show / delete（软删除）"""
    if action not in ("hide", "show", "delete"):
        raise ValueError("无效操作")

    client = _supabase()
    if not client:
        raise RuntimeError("未配置 Supabase")

    now = datetime.now(timezone.utc).isoformat()
    if action == "hide":
        payload = {"is_hidden": True, "updated_at": now}
    elif action == "show":
        payload = {"is_hidden": False, "updated_at": now}
    else:
        payload = {"deleted_at": now, "updated_at": now}

    res = (
        client.table("community_posts")
        .update(payload)
        .eq("id", post_id)
        .is_("deleted_at", "null")
        .execute()
    )
    if not res.data:
        raise ValueError("帖子不存在或已删除")
    return res.data[0]


async def delete_comment(comment_id: str) -> dict[str, Any]:
    client = _supabase()
    if not client:
        raise RuntimeError("未配置 Supabase")

    res = (
        client.table("community_comments")
        .delete()
        .eq("id", comment_id)
        .execute()
    )
    if not res.data:
        raise ValueError("评论不存在")
    return {"id": comment_id, "deleted": True}


async def list_posts(page: int = 1, page_size: int = 20, q: str = "") -> dict[str, Any]:
    client = _supabase()
    if not client:
        return {"items": [], "total": 0, "page": page, "pageSize": page_size}

    offset = (page - 1) * page_size
    query = (
        client.table("community_posts")
        .select(
            "id, title, post_type, subject_category, view_count, favorite_count, comment_count, is_hidden, created_at, author_id",
            count="exact",
        )
        .is_("deleted_at", "null")
    )
    if q.strip():
        query = query.ilike("title", f"%{q}%")
    res = query.order("created_at", desc=True).range(offset, offset + page_size - 1).execute()
    return {
        "items": res.data or [],
        "total": res.count or 0,
        "page": page,
        "pageSize": page_size,
    }


async def list_colleges(page: int = 1, page_size: int = 20, q: str = "") -> dict[str, Any]:
    client = _supabase()
    if not client:
        return {"items": [], "total": 0, "page": page, "pageSize": page_size}

    offset = (page - 1) * page_size
    query = client.table("colleges").select(
        "id, name, official_site, university_id, updated_at",
        count="exact",
    )
    if q.strip():
        query = query.ilike("name", f"%{q}%")
    res = query.order("name").range(offset, offset + page_size - 1).execute()
    return {
        "items": res.data or [],
        "total": res.count or 0,
        "page": page,
        "pageSize": page_size,
    }


def _format_university(row: dict[str, Any]) -> dict[str, Any]:
    tags: list[str] = []
    if row.get("level_985"):
        tags.append("985")
    if row.get("level_211"):
        tags.append("211")
    if row.get("double_first_class"):
        tags.append("双一流")
    return {
        "id": row["id"],
        "name": row["name"],
        "province": row.get("province"),
        "city": row.get("city"),
        "school_type": row.get("school_type"),
        "level_985": bool(row.get("level_985")),
        "level_211": bool(row.get("level_211")),
        "double_first_class": row.get("double_first_class"),
        "level": "/".join(tags) if tags else None,
        "website": row.get("website"),
        "intro": row.get("intro"),
        "updated_at": row.get("updated_at"),
    }


def _format_major(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "code": row.get("code"),
        "college": row.get("college"),
        "subject_category": row.get("subject_category"),
        "degree_type": row.get("degree_type"),
        "study_mode": row.get("study_mode"),
        "university_id": row.get("university_id"),
        "updated_at": row.get("updated_at"),
    }


async def list_schools(page: int = 1, page_size: int = 20, q: str = "") -> dict[str, Any]:
    client = _supabase()
    if not client:
        return {"items": [], "total": 0, "page": page, "pageSize": page_size}

    offset = (page - 1) * page_size
    query = client.table("universities").select(
        "id, name, province, city, level_985, level_211, double_first_class, school_type, website, intro, updated_at",
        count="exact",
    )
    if q.strip():
        query = query.ilike("name", f"%{q}%")
    res = query.order("name").range(offset, offset + page_size - 1).execute()
    return {
        "items": [_format_university(row) for row in (res.data or [])],
        "total": res.count or 0,
        "page": page,
        "pageSize": page_size,
    }


async def list_majors(page: int = 1, page_size: int = 20, q: str = "") -> dict[str, Any]:
    client = _supabase()
    if not client:
        return {"items": [], "total": 0, "page": page, "pageSize": page_size}

    offset = (page - 1) * page_size
    query = client.table("majors").select(
        "id, name, code, college, subject_category, degree_type, study_mode, university_id, updated_at",
        count="exact",
    )
    if q.strip():
        query = query.ilike("name", f"%{q}%")
    res = query.order("updated_at", desc=True).range(offset, offset + page_size - 1).execute()
    return {
        "items": [_format_major(row) for row in (res.data or [])],
        "total": res.count or 0,
        "page": page,
        "pageSize": page_size,
    }


async def create_school(payload: dict[str, Any]) -> dict[str, Any]:
    client = _supabase()
    if not client:
        raise RuntimeError("未配置 Supabase")
    row = {
        "name": payload["name"].strip(),
        "province": (payload.get("province") or "未知").strip(),
        "city": (payload.get("city") or "未知").strip(),
        "school_type": (payload.get("school_type") or "综合").strip(),
        "level_985": bool(payload.get("level_985")),
        "level_211": bool(payload.get("level_211")),
        "double_first_class": payload.get("double_first_class") or None,
        "website": payload.get("website") or None,
        "intro": payload.get("intro") or None,
    }
    res = client.table("universities").insert(row).execute()
    if not res.data:
        raise RuntimeError("创建失败")
    return _format_university(res.data[0])


async def update_school(school_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    client = _supabase()
    if not client:
        raise RuntimeError("未配置 Supabase")
    allowed = (
        "name",
        "province",
        "city",
        "school_type",
        "level_985",
        "level_211",
        "double_first_class",
        "website",
        "intro",
    )
    updates = {k: payload[k] for k in allowed if k in payload}
    if "name" in updates:
        updates["name"] = str(updates["name"]).strip()
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = (
        client.table("universities")
        .update(updates)
        .eq("id", school_id)
        .execute()
    )
    if not res.data:
        raise ValueError("学校不存在")
    return _format_university(res.data[0])


async def create_major(payload: dict[str, Any]) -> dict[str, Any]:
    client = _supabase()
    if not client:
        raise RuntimeError("未配置 Supabase")
    row = {
        "university_id": payload["university_id"],
        "name": payload["name"].strip(),
        "code": (payload.get("code") or "000000").strip(),
        "college": (payload.get("college") or "未分类").strip(),
        "degree_type": (payload.get("degree_type") or "学硕").strip(),
        "study_mode": (payload.get("study_mode") or "全日制").strip(),
        "subject_category": payload.get("subject_category") or None,
    }
    res = client.table("majors").insert(row).execute()
    if not res.data:
        raise RuntimeError("创建失败")
    return _format_major(res.data[0])


async def update_major(major_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    client = _supabase()
    if not client:
        raise RuntimeError("未配置 Supabase")
    allowed = ("name", "code", "college", "subject_category", "degree_type", "study_mode")
    updates = {k: payload[k] for k in allowed if k in payload}
    if "name" in updates:
        updates["name"] = str(updates["name"]).strip()
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = (
        client.table("majors")
        .update(updates)
        .eq("id", major_id)
        .execute()
    )
    if not res.data:
        raise ValueError("专业不存在")
    return _format_major(res.data[0])


async def create_college(payload: dict[str, Any]) -> dict[str, Any]:
    client = _supabase()
    if not client:
        raise RuntimeError("未配置 Supabase")
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "university_id": payload["university_id"],
        "name": payload["name"].strip(),
        "official_site": payload.get("official_site") or None,
        "updated_at": now,
    }
    res = client.table("colleges").insert(row).execute()
    if not res.data:
        raise RuntimeError("创建失败")
    return res.data[0]


async def update_college(college_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    client = _supabase()
    if not client:
        raise RuntimeError("未配置 Supabase")
    allowed = ("name", "official_site")
    updates = {k: payload[k] for k in allowed if k in payload}
    if "name" in updates:
        updates["name"] = updates["name"].strip()
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = (
        client.table("colleges")
        .update(updates)
        .eq("id", college_id)
        .execute()
    )
    if not res.data:
        raise ValueError("学院不存在")
    return res.data[0]


def _log_error(source: str, message: str) -> None:
    _error_logs.insert(
        0,
        {
            "id": str(uuid.uuid4()),
            "source": source,
            "message": message[:500],
            "time": datetime.now(timezone.utc).isoformat(),
        },
    )
    del _error_logs[50:]


async def list_comments(page: int = 1, page_size: int = 20, q: str = "") -> dict[str, Any]:
    client = _supabase()
    if not client:
        return {"items": [], "total": 0, "page": page, "pageSize": page_size}

    offset = (page - 1) * page_size
    query = client.table("community_comments").select(
        "id, post_id, author_id, content, parent_id, created_at",
        count="exact",
    )
    if q.strip():
        query = query.ilike("content", f"%{q}%")
    res = query.order("created_at", desc=True).range(offset, offset + page_size - 1).execute()
    return {
        "items": res.data or [],
        "total": res.count or 0,
        "page": page,
        "pageSize": page_size,
    }


async def list_moderation_queue(page: int = 1, page_size: int = 20) -> dict[str, Any]:
    client = _supabase()
    if not client:
        return {"items": [], "total": 0, "page": page, "pageSize": page_size}

    offset = (page - 1) * page_size
    res = (
        client.table("community_posts")
        .select(
            "id, title, author_id, is_hidden, created_at, comment_count, favorite_count",
            count="exact",
        )
        .is_("deleted_at", "null")
        .eq("is_hidden", True)
        .order("created_at", desc=True)
        .range(offset, offset + page_size - 1)
        .execute()
    )
    return {
        "items": res.data or [],
        "total": res.count or 0,
        "page": page,
        "pageSize": page_size,
    }


async def list_reports(page: int = 1, page_size: int = 20) -> dict[str, Any]:
    """举报队列：当前以被隐藏帖子代替（无独立举报表）。"""
    data = await list_moderation_queue(page=page, page_size=page_size)
    for item in data["items"]:
        item["reason"] = "内容被隐藏，待复核"
        item["status"] = "pending"
    return data


async def list_user_follows(page: int = 1, page_size: int = 20) -> dict[str, Any]:
    client = _supabase()
    if not client:
        return {"items": [], "total": 0, "page": page, "pageSize": page_size}

    offset = (page - 1) * page_size
    res = (
        client.table("user_follows")
        .select("follower_id, following_id, created_at", count="exact")
        .order("created_at", desc=True)
        .range(offset, offset + page_size - 1)
        .execute()
    )
    return {
        "items": res.data or [],
        "total": res.count or 0,
        "page": page,
        "pageSize": page_size,
    }


async def list_favorite_stats(page: int = 1, page_size: int = 20) -> dict[str, Any]:
    client = _supabase()
    if not client:
        return {"items": [], "total": 0, "page": page, "pageSize": page_size}

    offset = (page - 1) * page_size
    res = (
        client.table("post_favorites")
        .select("user_id, post_id, created_at", count="exact")
        .order("created_at", desc=True)
        .range(offset, offset + page_size - 1)
        .execute()
    )
    return {
        "items": res.data or [],
        "total": res.count or 0,
        "page": page,
        "pageSize": page_size,
    }


async def list_post_stats(page: int = 1, page_size: int = 20) -> dict[str, Any]:
    client = _supabase()
    if not client:
        return {"items": [], "total": 0, "page": page, "pageSize": page_size}

    offset = (page - 1) * page_size
    try:
        res = client.rpc(
            "admin_author_post_stats",
            {"p_limit": page_size, "p_offset": offset},
        ).execute()
        payload = res.data
        if isinstance(payload, str):
            payload = json.loads(payload)
        if isinstance(payload, dict):
            items = payload.get("items") or []
            total = int(payload.get("total") or 0)
            return {
                "items": items if isinstance(items, list) else [],
                "total": total,
                "page": page,
                "pageSize": page_size,
            }
    except Exception as exc:
        logger.debug("RPC admin_author_post_stats unavailable, fallback: %s", exc)

    try:
        res = (
            client.table("community_posts")
            .select("author_id", count="exact")
            .is_("deleted_at", "null")
            .not_.is_("author_id", "null")
            .limit(10000)
            .execute()
        )
        counts: dict[str, int] = {}
        for row in res.data or []:
            aid = row.get("author_id")
            if aid:
                counts[aid] = counts.get(aid, 0) + 1
        ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        total = len(ranked)
        page_items = ranked[offset : offset + page_size]
        items = [{"author_id": aid, "post_count": cnt} for aid, cnt in page_items]
        return {"items": items, "total": total, "page": page, "pageSize": page_size}
    except Exception as exc:
        _log_error("post_stats", str(exc))
        return {"items": [], "total": 0, "page": page, "pageSize": page_size}


async def create_announcement(payload: dict[str, Any]) -> dict[str, Any]:
    client = _supabase()
    if not client:
        raise RuntimeError("未配置 Supabase")
    row = {
        "university_id": payload["university_id"],
        "title": payload["title"].strip(),
        "publish_time": payload["publish_time"],
        "url": payload["url"].strip(),
        "type": (payload.get("type") or "招生公告").strip(),
        "content": payload.get("content") or None,
    }
    res = client.table("announcements").insert(row).execute()
    if not res.data:
        raise RuntimeError("创建失败")
    return res.data[0]


async def update_announcement(announcement_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    client = _supabase()
    if not client:
        raise RuntimeError("未配置 Supabase")
    allowed = ("title", "publish_time", "url", "type", "content")
    updates = {k: payload[k] for k in allowed if k in payload}
    if "title" in updates:
        updates["title"] = str(updates["title"]).strip()
    if "url" in updates:
        updates["url"] = str(updates["url"]).strip()
    updates["last_updated"] = datetime.now(timezone.utc).isoformat()
    res = (
        client.table("announcements")
        .update(updates)
        .eq("id", announcement_id)
        .execute()
    )
    if not res.data:
        raise ValueError("公告不存在")
    return res.data[0]


async def delete_announcement(announcement_id: str) -> dict[str, Any]:
    client = _supabase()
    if not client:
        raise RuntimeError("未配置 Supabase")
    res = client.table("announcements").delete().eq("id", announcement_id).execute()
    if not res.data:
        raise ValueError("公告不存在")
    return {"id": announcement_id}


async def create_pdf_record(payload: dict[str, Any]) -> dict[str, Any]:
    client = _supabase()
    if not client:
        raise RuntimeError("未配置 Supabase")
    row = {
        "school_id": payload.get("school_id") or None,
        "file_name": payload["file_name"].strip(),
        "file_type": (payload.get("file_type") or "application/pdf").strip(),
        "file_path": payload["file_path"].strip(),
        "file_size": payload.get("file_size"),
        "source_url": payload.get("source_url") or None,
        "batch_id": payload.get("batch_id") or None,
    }
    res = client.table("raw_files").insert(row).execute()
    if not res.data:
        raise RuntimeError("创建失败")
    return res.data[0]


async def update_pdf_record(pdf_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    client = _supabase()
    if not client:
        raise RuntimeError("未配置 Supabase")
    allowed = ("file_name", "file_path", "file_size", "source_url", "school_id")
    updates = {k: payload[k] for k in allowed if k in payload}
    if "file_name" in updates:
        updates["file_name"] = str(updates["file_name"]).strip()
    if "file_path" in updates:
        updates["file_path"] = str(updates["file_path"]).strip()
    res = client.table("raw_files").update(updates).eq("id", pdf_id).execute()
    if not res.data:
        raise ValueError("PDF 记录不存在")
    return res.data[0]


async def delete_pdf_record(pdf_id: str) -> dict[str, Any]:
    client = _supabase()
    if not client:
        raise RuntimeError("未配置 Supabase")
    res = client.table("raw_files").delete().eq("id", pdf_id).execute()
    if not res.data:
        raise ValueError("PDF 记录不存在")
    return {"id": pdf_id}


async def list_announcements(page: int = 1, page_size: int = 20, q: str = "") -> dict[str, Any]:
    client = _supabase()
    if not client:
        return {"items": [], "total": 0, "page": page, "pageSize": page_size}

    offset = (page - 1) * page_size
    query = client.table("announcements").select(
        "id, university_id, title, publish_time, url, type, created_at",
        count="exact",
    )
    if q.strip():
        query = query.ilike("title", f"%{q}%")
    res = query.order("publish_time", desc=True).range(offset, offset + page_size - 1).execute()
    return {
        "items": res.data or [],
        "total": res.count or 0,
        "page": page,
        "pageSize": page_size,
    }


async def list_pdfs(page: int = 1, page_size: int = 20, q: str = "") -> dict[str, Any]:
    client = _supabase()
    if not client:
        return {"items": [], "total": 0, "page": page, "pageSize": page_size}

    offset = (page - 1) * page_size
    query = client.table("raw_files").select(
        "id, file_name, file_type, file_path, file_size, source_url, school_id, created_at",
        count="exact",
    ).ilike("file_type", "%pdf%")
    if q.strip():
        query = query.ilike("file_name", f"%{q}%")
    res = query.order("created_at", desc=True).range(offset, offset + page_size - 1).execute()
    return {
        "items": res.data or [],
        "total": res.count or 0,
        "page": page,
        "pageSize": page_size,
    }


async def get_sync_logs(page: int = 1, page_size: int = 20) -> dict[str, Any]:
    client = _supabase()
    if not client:
        return {"meta": None, "items": [], "total": 0, "page": page, "pageSize": page_size}

    meta_res = (
        client.table("schools_sync_meta")
        .select("revision, updated_at, note")
        .eq("id", 1)
        .maybe_single()
        .execute()
    )
    offset = (page - 1) * page_size
    pages_res = (
        client.table("source_pages")
        .select(
            "id, university_id, url, title, page_type, status, last_fetch_time, updated_at",
            count="exact",
        )
        .order("updated_at", desc=True)
        .range(offset, offset + page_size - 1)
        .execute()
    )
    return {
        "meta": meta_res.data,
        "items": pages_res.data or [],
        "total": pages_res.count or 0,
        "page": page,
        "pageSize": page_size,
    }


async def get_monitoring_detail(section: str) -> dict[str, Any]:
    health = await get_monitoring_health()
    if section == "api":
        return {"section": "api", **health["api"], "llmConfigured": health["llmConfigured"]}
    if section == "database":
        client = _supabase()
        tables: dict[str, int | str] = {}
        if client:
            for table in ("users", "community_posts", "universities", "majors", "announcements"):
                try:
                    r = client.table(table).select("id", count="exact", head=True).execute()
                    tables[table] = r.count or 0
                except Exception as exc:
                    tables[table] = str(exc)
        return {"section": "database", **health["database"], "tables": tables}
    if section == "agents":
        return {
            "section": "agents",
            **health["agent"],
            "agents": get_agent_status(),
        }
    if section == "errors":
        from app.utils.admin_audit import list_audit_logs

        return {
            "section": "errors",
            "items": _error_logs[:50],
            "auditLogs": list_audit_logs(limit=30),
        }
    if section == "queue":
        return {
            "section": "queue",
            **health["queue"],
            "tasks": list_agent_tasks()[:20],
        }
    return health


async def get_user_detail(user_id: str) -> dict[str, Any] | None:
    client = _supabase()
    if not client:
        return None
    res = (
        client.table("users")
        .select("id, email, nickname, avatar_url, bio, display_id, created_at, target_year")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    if not res.data:
        return None
    user = res.data
    posts = (
        client.table("community_posts")
        .select("id", count="exact", head=True)
        .eq("author_id", user_id)
        .is_("deleted_at", "null")
        .execute()
        .count
        or 0
    )
    followers = (
        client.table("user_follows")
        .select("follower_id", count="exact", head=True)
        .eq("following_id", user_id)
        .execute()
        .count
        or 0
    )
    following = (
        client.table("user_follows")
        .select("following_id", count="exact", head=True)
        .eq("follower_id", user_id)
        .execute()
        .count
        or 0
    )
    favorites = (
        client.table("post_favorites")
        .select("post_id", count="exact", head=True)
        .eq("user_id", user_id)
        .execute()
        .count
        or 0
    )
    user["stats"] = {
        "posts": posts,
        "followers": followers,
        "following": following,
        "favorites": favorites,
    }
    return user


async def get_post_detail(post_id: str) -> dict[str, Any] | None:
    client = _supabase()
    if not client:
        return None
    res = (
        client.table("community_posts")
        .select("*")
        .eq("id", post_id)
        .maybe_single()
        .execute()
    )
    if not res.data:
        return None
    post = res.data
    author = (
        client.table("users")
        .select("id, nickname, email, display_id")
        .eq("id", post.get("author_id"))
        .maybe_single()
        .execute()
    )
    post["author"] = author.data
    comments = (
        client.table("community_comments")
        .select("id, content, author_id, created_at")
        .eq("post_id", post_id)
        .order("created_at", desc=False)
        .limit(20)
        .execute()
    )
    post["recent_comments"] = comments.data or []
    return post


async def batch_moderate_posts(post_ids: list[str], action: str) -> dict[str, Any]:
    if action not in ("hide", "show", "delete"):
        raise ValueError("无效操作")
    ok: list[str] = []
    failed: list[str] = []
    for pid in post_ids:
        try:
            await moderate_post(pid, action)
            ok.append(pid)
        except Exception as exc:
            failed.append(pid)
            _log_error("batch_moderate", f"{pid}: {exc}")
    return {"success": ok, "failed": failed, "action": action}


async def get_user_posts(user_id: str, page: int = 1, page_size: int = 10) -> dict[str, Any]:
    client = _supabase()
    if not client:
        return {"items": [], "total": 0, "page": page, "pageSize": page_size}
    offset = (page - 1) * page_size
    res = (
        client.table("community_posts")
        .select("id, title, post_type, is_hidden, created_at, comment_count, favorite_count", count="exact")
        .eq("author_id", user_id)
        .is_("deleted_at", "null")
        .order("created_at", desc=True)
        .range(offset, offset + page_size - 1)
        .execute()
    )
    return {"items": res.data or [], "total": res.count or 0, "page": page, "pageSize": page_size}


async def get_user_follows_for(user_id: str, page: int = 1, page_size: int = 10) -> dict[str, Any]:
    client = _supabase()
    if not client:
        return {"items": [], "total": 0, "page": page, "pageSize": page_size}
    offset = (page - 1) * page_size
    res = (
        client.table("user_follows")
        .select("following_id, created_at", count="exact")
        .eq("follower_id", user_id)
        .order("created_at", desc=True)
        .range(offset, offset + page_size - 1)
        .execute()
    )
    return {"items": res.data or [], "total": res.count or 0, "page": page, "pageSize": page_size}


async def get_user_favorites_for(user_id: str, page: int = 1, page_size: int = 10) -> dict[str, Any]:
    client = _supabase()
    if not client:
        return {"items": [], "total": 0, "page": page, "pageSize": page_size}
    offset = (page - 1) * page_size
    res = (
        client.table("post_favorites")
        .select("post_id, created_at", count="exact")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .range(offset, offset + page_size - 1)
        .execute()
    )
    return {"items": res.data or [], "total": res.count or 0, "page": page, "pageSize": page_size}


async def get_monitoring_health() -> dict[str, Any]:
    settings = get_settings()
    client = _supabase()
    db_ok = False
    if client:
        try:
            client.table("users").select("id").limit(1).execute()
            db_ok = True
        except Exception:
            db_ok = False

    return {
        "api": {"status": "ok", "latencyMs": _probe_api_latency_ms()},
        "database": {"status": "ok" if db_ok else "degraded", "connected": db_ok},
        "agent": {
            "status": "running"
            if any(t.get("status") == "running" for t in _agent_tasks.values())
            else "idle",
            "activeTasks": sum(1 for t in _agent_tasks.values() if t.get("status") == "running"),
        },
        "queue": {"pending": sum(1 for t in _agent_tasks.values() if t.get("status") == "pending")},
        "llmConfigured": bool(settings.dashscope_api_key.strip()),
    }


def _assess_risk(intent: str) -> str:
    high_keywords = ["全部985", "全部 985", "bulk", "删除", "清空"]
    medium_keywords = ["同步", "导入", "写入", "upsert"]
    if any(k in intent for k in high_keywords):
        return "high"
    if any(k in intent for k in medium_keywords):
        return "medium"
    return "low"


def _simulate_task_run(task_id: str) -> None:
    import time

    checkpoints = [25, 50, 75, 100]
    for progress in checkpoints:
        time.sleep(1.5)
        with _agent_tasks_lock:
            task = _agent_tasks.get(task_id)
            if not task or task.get("status") != "running":
                return
            task["progress"] = progress
            if progress >= 100:
                task["status"] = "done"
                task["statusLabel"] = "已完成"
                task["finishedAt"] = datetime.now(timezone.utc).isoformat()
        _save_agent_tasks()


def _append_task_log(task_id: str, message: str) -> None:
    with _agent_tasks_lock:
        task = _agent_tasks.get(task_id)
        if task:
            task.setdefault("logs", []).append(
                {"time": datetime.now(timezone.utc).isoformat(), "message": message}
            )


def _set_task_progress(task_id: str, progress: int) -> None:
    with _agent_tasks_lock:
        task = _agent_tasks.get(task_id)
        if task and task.get("status") == "running":
            task["progress"] = min(100, max(0, progress))
    _save_agent_tasks()


def _finish_task(task_id: str, ok: bool, message: str) -> None:
    with _agent_tasks_lock:
        task = _agent_tasks.get(task_id)
        if not task:
            return
        task["progress"] = 100
        task["status"] = "done" if ok else "failed"
        task["statusLabel"] = "已完成" if ok else "失败"
        task["finishedAt"] = datetime.now(timezone.utc).isoformat()
        task.setdefault("logs", []).append(
            {"time": datetime.now(timezone.utc).isoformat(), "message": message}
        )
    _save_agent_tasks()


def _start_task_run(task_id: str, intent: str) -> None:
    from app.services.agent_runner import resolve_command, run_task_subprocess

    resolved = resolve_command(intent)
    if not resolved:
        threading.Thread(target=_simulate_task_run, args=(task_id,), daemon=True).start()
        return

    argv, desc = resolved
    _append_task_log(task_id, f"执行类型: {desc}")
    _save_agent_tasks()
    run_task_subprocess(
        task_id,
        argv,
        lambda msg: (_append_task_log(task_id, msg), _save_agent_tasks()),
        _set_task_progress,
        _finish_task,
    )


def create_agent_plan(intent: str) -> dict[str, Any]:
    from app.services.agent_runner import resolve_command

    plan_id = str(uuid.uuid4())
    risk = _assess_risk(intent)
    resolved = resolve_command(intent)
    if resolved:
        _argv, desc = resolved
        steps = [
            {"order": 1, "title": f"准备执行: {desc}", "duration": "~5s"},
            {"order": 2, "title": "运行脚本并采集日志", "duration": "~60s"},
            {"order": 3, "title": "校验结果并更新任务状态", "duration": "~10s"},
        ]
    else:
        steps = [
            {"order": 1, "title": "解析任务参数与目标范围", "duration": "~5s"},
            {"order": 2, "title": "拉取外部数据源（模拟）", "duration": "~30s"},
            {"order": 3, "title": "比对并写入数据库（模拟）", "duration": "~60s"},
        ]
    impact = "~120 条专业记录" if "专业" in intent else "~50 条记录"
    if risk == "high":
        impact = "~2000+ 条记录"

    plan = {
        "planId": plan_id,
        "intent": intent,
        "steps": steps,
        "impact": impact,
        "risk": risk,
        "riskReason": "批量写入生产数据" if risk != "low" else "只读或低风险操作",
    }
    with _agent_tasks_lock:
        _agent_tasks[plan_id] = {
            "id": plan_id,
            "title": intent,
            "status": "pending",
            "statusLabel": "待确认",
            "agent": "SyncAgent",
            "progress": 0,
            "plan": plan,
            "logs": [],
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
    _save_agent_tasks()
    return plan


def execute_agent_plan(plan_id: str) -> dict[str, Any]:
    with _agent_tasks_lock:
        task = _agent_tasks.get(plan_id)
        if not task:
            raise ValueError("计划不存在或已过期")
        task["status"] = "running"
        task["statusLabel"] = "运行中"
        task["progress"] = 10
        task["startedAt"] = datetime.now(timezone.utc).isoformat()
        task.setdefault("logs", []).append(
            {"time": datetime.now(timezone.utc).isoformat(), "message": "任务已开始执行"}
        )
        snapshot = dict(task)
        intent = task.get("title", "")
    _save_agent_tasks()
    _start_task_run(plan_id, intent)
    return snapshot


def retry_agent_task(task_id: str) -> dict[str, Any]:
    with _agent_tasks_lock:
        task = _agent_tasks.get(task_id)
        if not task:
            raise ValueError("任务不存在")
        task["status"] = "running"
        task["statusLabel"] = "运行中"
        task["progress"] = 5
        task.setdefault("logs", []).append(
            {"time": datetime.now(timezone.utc).isoformat(), "message": "任务重试中"}
        )
        snapshot = dict(task)
        intent = task.get("title", "")
    _save_agent_tasks()
    _start_task_run(task_id, intent)
    return snapshot


def get_agent_task(task_id: str) -> dict[str, Any] | None:
    task = _agent_tasks.get(task_id)
    return dict(task) if task else None


def cancel_agent_task(task_id: str) -> dict[str, Any]:
    with _agent_tasks_lock:
        task = _agent_tasks.get(task_id)
        if not task:
            raise ValueError("任务不存在")
        if task.get("status") not in ("pending", "running"):
            raise ValueError("任务无法取消")
        task["status"] = "failed"
        task["statusLabel"] = "已取消"
        task.setdefault("logs", []).append(
            {"time": datetime.now(timezone.utc).isoformat(), "message": "任务已取消"}
        )
        snapshot = dict(task)
    _save_agent_tasks()
    return snapshot


def list_agent_tasks() -> list[dict[str, Any]]:
    tasks = list(_agent_tasks.values())
    tasks.sort(key=lambda t: t.get("createdAt", ""), reverse=True)
    return tasks


def get_agent_status() -> list[dict[str, Any]]:
    running = sum(1 for t in _agent_tasks.values() if t.get("status") == "running")
    done = sum(1 for t in _agent_tasks.values() if t.get("status") == "done")
    failed = sum(1 for t in _agent_tasks.values() if t.get("status") == "failed")
    total = len(_agent_tasks) or 1
    success_rate = f"{(done / total) * 100:.1f}%"
    return [
        {
            "id": "sync",
            "name": "SyncAgent",
            "status": "running" if running else "idle",
            "lastRun": "刚刚" if running else "—",
            "successRate": success_rate,
            "taskCount": len(_agent_tasks),
        },
        {
            "id": "rag",
            "name": "RAGAgent",
            "status": "warning" if failed else "idle",
            "lastRun": "—",
            "successRate": success_rate,
            "taskCount": failed,
        },
        {
            "id": "report",
            "name": "ReportAgent",
            "status": "idle",
            "lastRun": "—",
            "successRate": "—",
            "taskCount": done,
        },
    ]


def _probe_api_latency_ms() -> int:
    import time

    client = _supabase()
    if not client:
        return 0
    start = time.perf_counter()
    try:
        client.table("users").select("id").limit(1).execute()
        return int((time.perf_counter() - start) * 1000)
    except Exception:
        return -1
