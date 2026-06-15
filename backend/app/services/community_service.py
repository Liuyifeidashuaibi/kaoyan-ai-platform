"""
社区模块 — Supabase 数据访问。
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from supabase import Client, create_client

from app.config import get_settings
from app.utils.file_utils import ascii_storage_filename
from app.schemas.community import COHORT_GRADES, SUBJECT_CATEGORIES, PostCreate, PostUpdate

logger = logging.getLogger(__name__)

PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 50
USER_PUBLIC_FIELDS = "id,display_id,nickname,avatar_url,subject_category,created_at"
POST_FIELDS = (
    "id,author_id,post_type,subject_category,grade,university_id,university_name,"
    "title,content,attachments,"
    "view_count,favorite_count,comment_count,hot_score,is_hidden,created_at,updated_at"
)


class CommunityService:
    def __init__(self) -> None:
        self._client: Client | None = None

    def _sb(self) -> Client:
        if self._client is None:
            s = get_settings()
            url = s.effective_supabase_url
            key = s.effective_supabase_service_key
            if not url or not key:
                raise RuntimeError(
                    "未配置 Supabase：请设置 SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY"
                )
            self._client = create_client(url, key)
        return self._client

    @staticmethod
    def _first_row(resp: Any) -> dict[str, Any] | None:
        rows = resp.data if resp else None
        if isinstance(rows, list):
            return rows[0] if rows else None
        return rows if isinstance(rows, dict) else None

    @staticmethod
    def _escape_ilike(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    # ---------- helpers ----------

    def _attach_authors(self, posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not posts:
            return []
        author_ids = list({p["author_id"] for p in posts})
        sb = self._sb()
        users_resp = (
            sb.table("users")
            .select(USER_PUBLIC_FIELDS)
            .in_("id", author_ids)
            .execute()
        )
        user_map = {u["id"]: u for u in (users_resp.data or [])}
        result = []
        for post in posts:
            author = user_map.get(post["author_id"], {})
            result.append({**post, "author": author})
        return result

    def _validate_subject(self, category: str) -> None:
        if category not in SUBJECT_CATEGORIES:
            raise ValueError(f"无效的专业大类，请从以下选择：{', '.join(SUBJECT_CATEGORIES)}")

    def _validate_grade(self, grade: str) -> None:
        if grade not in COHORT_GRADES:
            raise ValueError(f"无效的年级，请选择：{', '.join(COHORT_GRADES)}")

    def ensure_user_row(self, user_id: str) -> None:
        """确保 auth 用户在 public.users 中有记录（兼容迁移前注册账号）。"""
        sb = self._sb()
        resp = sb.table("users").select("id").eq("id", user_id).limit(1).execute()
        if self._first_row(resp):
            return
        suffix = user_id.replace("-", "")[:8]
        display_id = f"user_{suffix}"
        sb.table("users").insert(
            {"id": user_id, "display_id": display_id, "nickname": display_id}
        ).execute()

    # ---------- posts ----------

    def list_posts(
        self,
        *,
        sort: str = "latest",
        page: int = 1,
        page_size: int = PAGE_SIZE_DEFAULT,
        post_type: str | None = None,
        subject_category: str | None = None,
        author_id: str | None = None,
        q: str | None = None,
        viewer_id: str | None = None,
    ) -> dict[str, Any]:
        sb = self._sb()
        page = max(1, page)
        page_size = min(max(1, page_size), PAGE_SIZE_MAX)
        offset = (page - 1) * page_size

        query = sb.table("community_posts").select(POST_FIELDS, count="exact")

        if author_id:
            query = query.eq("author_id", author_id).is_("deleted_at", "null")
            if viewer_id != author_id:
                query = query.eq("is_hidden", False)
        else:
            query = query.is_("deleted_at", "null").eq("is_hidden", False)

        if post_type:
            query = query.eq("post_type", post_type)
        if subject_category:
            query = query.eq("subject_category", subject_category)
        if q:
            safe_q = self._escape_ilike(q.strip())
            query = query.or_(f"title.ilike.%{safe_q}%,content.ilike.%{safe_q}%")

        if sort == "hot":
            query = query.order("hot_score", desc=True).order("created_at", desc=True)
        else:
            query = query.order("created_at", desc=True)

        resp = query.range(offset, offset + page_size - 1).execute()
        posts = self._attach_authors(resp.data or [])
        total = resp.count or 0

        if viewer_id and posts:
            post_ids = [p["id"] for p in posts]
            fav_resp = (
                sb.table("post_favorites")
                .select("post_id")
                .eq("user_id", viewer_id)
                .in_("post_id", post_ids)
                .execute()
            )
            fav_set = {r["post_id"] for r in (fav_resp.data or [])}
            for p in posts:
                p["is_favorited"] = p["id"] in fav_set

        return {
            "items": posts,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": offset + len(posts) < total,
        }

    def get_post(self, post_id: str, viewer_id: str | None = None) -> dict[str, Any] | None:
        sb = self._sb()
        resp = (
            sb.table("community_posts")
            .select(POST_FIELDS)
            .eq("id", post_id)
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
        post = self._first_row(resp)
        if not post:
            return None
        if post.get("is_hidden") and post.get("author_id") != viewer_id:
            return None

        sb.table("community_posts").update(
            {"view_count": (post.get("view_count") or 0) + 1}
        ).eq("id", post_id).execute()
        post["view_count"] = (post.get("view_count") or 0) + 1

        enriched = self._attach_authors([post])[0]
        if viewer_id:
            fav_resp = (
                sb.table("post_favorites")
                .select("post_id")
                .eq("user_id", viewer_id)
                .eq("post_id", post_id)
                .limit(1)
                .execute()
            )
            enriched["is_favorited"] = bool(self._first_row(fav_resp))
        return enriched

    def create_post(self, user_id: str, body: PostCreate) -> dict[str, Any]:
        self._validate_subject(body.subject_category)
        self._validate_grade(body.grade)
        self.ensure_user_row(user_id)
        sb = self._sb()

        university_name = (body.university_name or "").strip() or None
        university_id = (body.university_id or "").strip() or None
        if university_id:
            uni_resp = (
                sb.table("universities")
                .select("id,name")
                .eq("id", university_id)
                .limit(1)
                .execute()
            )
            uni = self._first_row(uni_resp)
            if not uni:
                raise ValueError("所选院校不存在")
            university_name = uni.get("name") or university_name

        row = {
            "author_id": user_id,
            "post_type": body.post_type,
            "subject_category": body.subject_category,
            "grade": body.grade,
            "university_id": university_id,
            "university_name": university_name,
            "title": body.title.strip(),
            "content": body.content,
            "attachments": [a.model_dump() for a in body.attachments],
        }
        resp = sb.table("community_posts").insert(row).select(POST_FIELDS).execute()
        created = self._first_row(resp)
        if not created:
            raise RuntimeError("发帖失败，请稍后重试")
        return self._attach_authors([created])[0]

    def update_post(
        self, post_id: str, user_id: str, body: PostUpdate
    ) -> dict[str, Any] | None:
        sb = self._sb()
        existing_resp = (
            sb.table("community_posts")
            .select("id,author_id")
            .eq("id", post_id)
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
        existing = self._first_row(existing_resp)
        if not existing or existing["author_id"] != user_id:
            return None

        patch: dict[str, Any] = {}
        if body.title is not None:
            patch["title"] = body.title.strip()
        if body.content is not None:
            patch["content"] = body.content
        if body.is_hidden is not None:
            patch["is_hidden"] = body.is_hidden
        if not patch:
            return self.get_post(post_id, viewer_id=user_id)

        resp = (
            sb.table("community_posts")
            .update(patch)
            .eq("id", post_id)
            .select(POST_FIELDS)
            .execute()
        )
        updated = self._first_row(resp)
        if not updated:
            return None
        return self._attach_authors([updated])[0]

    def delete_post(self, post_id: str, user_id: str) -> bool:
        sb = self._sb()
        existing_resp = (
            sb.table("community_posts")
            .select("id,author_id")
            .eq("id", post_id)
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
        existing = self._first_row(existing_resp)
        if not existing or existing["author_id"] != user_id:
            return False
        from datetime import datetime, timezone

        sb.table("community_posts").update(
            {"deleted_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", post_id).execute()
        return True

    # ---------- comments ----------

    def list_comments(self, post_id: str) -> list[dict[str, Any]]:
        sb = self._sb()
        resp = (
            sb.table("community_comments")
            .select("id,post_id,author_id,parent_id,content,created_at")
            .eq("post_id", post_id)
            .order("created_at", desc=False)
            .execute()
        )
        comments = resp.data or []
        if not comments:
            return []

        author_ids = list({c["author_id"] for c in comments})
        users_resp = (
            sb.table("users")
            .select(USER_PUBLIC_FIELDS)
            .in_("id", author_ids)
            .execute()
        )
        user_map = {u["id"]: u for u in (users_resp.data or [])}
        return [{**c, "author": user_map.get(c["author_id"], {})} for c in comments]

    def create_comment(
        self, post_id: str, user_id: str, content: str, parent_id: str | None = None
    ) -> dict[str, Any]:
        self.ensure_user_row(user_id)
        sb = self._sb()
        post_resp = (
            sb.table("community_posts")
            .select("id")
            .eq("id", post_id)
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
        if not self._first_row(post_resp):
            raise ValueError("帖子不存在")

        if parent_id:
            parent_resp = (
                sb.table("community_comments")
                .select("id,post_id")
                .eq("id", parent_id)
                .limit(1)
                .execute()
            )
            parent = self._first_row(parent_resp)
            if not parent or parent["post_id"] != post_id:
                raise ValueError("回复目标不存在")

        row = {
            "post_id": post_id,
            "author_id": user_id,
            "content": content.strip(),
            "parent_id": parent_id,
        }
        resp = (
            sb.table("community_comments")
            .insert(row)
            .select("id,post_id,author_id,parent_id,content,created_at")
            .execute()
        )
        comment = self._first_row(resp)
        if not comment:
            raise RuntimeError("评论发表失败")
        user_resp = (
            sb.table("users")
            .select(USER_PUBLIC_FIELDS)
            .eq("id", user_id)
            .execute()
        )
        user = self._first_row(user_resp) or {}
        return {**comment, "author": user}

    # ---------- favorites ----------

    def toggle_favorite(self, post_id: str, user_id: str) -> dict[str, Any]:
        sb = self._sb()
        existing_resp = (
            sb.table("post_favorites")
            .select("post_id")
            .eq("user_id", user_id)
            .eq("post_id", post_id)
            .limit(1)
            .execute()
        )
        if self._first_row(existing_resp):
            sb.table("post_favorites").delete().eq("user_id", user_id).eq(
                "post_id", post_id
            ).execute()
            return {"favorited": False}
        sb.table("post_favorites").insert(
            {"user_id": user_id, "post_id": post_id}
        ).execute()
        return {"favorited": True}

    def list_favorite_post_ids(self, user_id: str) -> list[str]:
        sb = self._sb()
        resp = (
            sb.table("post_favorites")
            .select("post_id")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return [str(row["post_id"]) for row in (resp.data or []) if row.get("post_id")]

    def get_posts_by_ids(
        self, post_ids: list[str], viewer_id: str | None = None
    ) -> list[dict[str, Any]]:
        if not post_ids:
            return []
        sb = self._sb()
        resp = (
            sb.table("community_posts")
            .select(POST_FIELDS)
            .in_("id", post_ids)
            .is_("deleted_at", "null")
            .execute()
        )
        posts = resp.data or []
        enriched = self._attach_authors(posts)
        if viewer_id:
            fav_resp = (
                sb.table("post_favorites")
                .select("post_id")
                .eq("user_id", viewer_id)
                .in_("post_id", post_ids)
                .execute()
            )
            fav_set = {row["post_id"] for row in (fav_resp.data or [])}
            for p in enriched:
                p["is_favorited"] = p["id"] in fav_set
        return enriched

    def list_favorites(self, user_id: str, page: int = 1) -> dict[str, Any]:
        sb = self._sb()
        page_size = PAGE_SIZE_DEFAULT
        offset = (max(1, page) - 1) * page_size
        fav_resp = (
            sb.table("post_favorites")
            .select("post_id,created_at", count="exact")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        favs = fav_resp.data or []
        if not favs:
            return {"items": [], "total": 0, "page": page, "has_more": False}

        post_ids = [f["post_id"] for f in favs]
        posts_resp = (
            sb.table("community_posts")
            .select(POST_FIELDS)
            .in_("id", post_ids)
            .is_("deleted_at", "null")
            .execute()
        )
        post_map = {p["id"]: p for p in (posts_resp.data or [])}
        ordered = [post_map[pid] for pid in post_ids if pid in post_map]
        items = self._attach_authors(ordered)
        for item in items:
            item["is_favorited"] = True
        total = fav_resp.count or len(items)
        return {
            "items": items,
            "total": total,
            "page": page,
            "has_more": offset + len(items) < total,
        }

    # ---------- follows ----------

    def follow_user(self, follower_id: str, following_id: str) -> dict[str, Any]:
        if follower_id == following_id:
            raise ValueError("不能关注自己")
        sb = self._sb()
        target_resp = (
            sb.table("users").select("id").eq("id", following_id).limit(1).execute()
        )
        if not self._first_row(target_resp):
            raise ValueError("用户不存在")
        sb.table("user_follows").upsert(
            {"follower_id": follower_id, "following_id": following_id},
            on_conflict="follower_id,following_id",
        ).execute()
        return {"following": True}

    def unfollow_user(self, follower_id: str, following_id: str) -> dict[str, Any]:
        sb = self._sb()
        sb.table("user_follows").delete().eq("follower_id", follower_id).eq(
            "following_id", following_id
        ).execute()
        return {"following": False}

    def list_following(self, user_id: str) -> list[dict[str, Any]]:
        sb = self._sb()
        resp = (
            sb.table("user_follows")
            .select("following_id,created_at")
            .eq("follower_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        ids = [r["following_id"] for r in (resp.data or [])]
        if not ids:
            return []
        users = sb.table("users").select(USER_PUBLIC_FIELDS).in_("id", ids).execute()
        user_map = {u["id"]: u for u in (users.data or [])}
        return [
            {**user_map[uid], "followed_at": r["created_at"]}
            for r in resp.data or []
            if (uid := r["following_id"]) in user_map
        ]

    def list_followers(self, user_id: str) -> list[dict[str, Any]]:
        sb = self._sb()
        resp = (
            sb.table("user_follows")
            .select("follower_id,created_at")
            .eq("following_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        ids = [r["follower_id"] for r in (resp.data or [])]
        if not ids:
            return []
        users = sb.table("users").select(USER_PUBLIC_FIELDS).in_("id", ids).execute()
        user_map = {u["id"]: u for u in (users.data or [])}
        return [
            {**user_map[uid], "followed_at": r["created_at"]}
            for r in resp.data or []
            if (uid := r["follower_id"]) in user_map
        ]

    def is_following(self, follower_id: str, following_id: str) -> bool:
        sb = self._sb()
        resp = (
            sb.table("user_follows")
            .select("follower_id")
            .eq("follower_id", follower_id)
            .eq("following_id", following_id)
            .limit(1)
            .execute()
        )
        return bool(self._first_row(resp))

    def _count_follows(self, user_id: str) -> tuple[int, int]:
        sb = self._sb()
        following = (
            sb.table("user_follows")
            .select("follower_id", count="exact")
            .eq("follower_id", user_id)
            .execute()
        )
        followers = (
            sb.table("user_follows")
            .select("follower_id", count="exact")
            .eq("following_id", user_id)
            .execute()
        )
        return following.count or 0, followers.count or 0

    # ---------- users ----------

    def get_user_profile(
        self, identifier: str, viewer_id: str | None = None
    ) -> dict[str, Any] | None:
        sb = self._sb()
        resp = (
            sb.table("users")
            .select(USER_PUBLIC_FIELDS)
            .eq("display_id", identifier)
            .limit(1)
            .execute()
        )
        user = self._first_row(resp)
        if not user:
            resp = (
                sb.table("users")
                .select(USER_PUBLIC_FIELDS)
                .eq("id", identifier)
                .limit(1)
                .execute()
            )
            user = self._first_row(resp)
        if not user:
            return None

        following_count, follower_count = self._count_follows(user["id"])
        profile = {
            **user,
            "following_count": following_count,
            "follower_count": follower_count,
        }
        if viewer_id and viewer_id != user["id"]:
            profile["is_following"] = self.is_following(viewer_id, user["id"])
        elif viewer_id == user["id"]:
            profile["is_self"] = True
        return profile

    def update_user_profile(
        self, user_id: str, subject_category: str | None = None, avatar_url: str | None = None
    ) -> dict[str, Any]:
        patch: dict[str, Any] = {}
        if subject_category is not None:
            self._validate_subject(subject_category)
            patch["subject_category"] = subject_category
        if avatar_url is not None:
            patch["avatar_url"] = avatar_url
        if not patch:
            return self.get_user_profile(user_id, viewer_id=user_id)  # type: ignore[return-value]

        sb = self._sb()
        resp = (
            sb.table("users")
            .update(patch)
            .eq("id", user_id)
            .select(USER_PUBLIC_FIELDS)
            .execute()
        )
        updated = self._first_row(resp)
        if not updated:
            raise RuntimeError("更新资料失败")
        following_count, follower_count = self._count_follows(user_id)
        return {
            **updated,
            "following_count": following_count,
            "follower_count": follower_count,
            "is_self": True,
        }

    # ---------- search ----------

    def search(self, q: str) -> dict[str, Any]:
        q = q.strip()
        if not q:
            return {"kind": "posts", "posts": []}

        sb = self._sb()

        # 1. 用户 ID
        user_resp = (
            sb.table("users")
            .select(USER_PUBLIC_FIELDS)
            .eq("display_id", q)
            .limit(1)
            .execute()
        )
        user_row = self._first_row(user_resp)
        if user_row:
            return {
                "kind": "user",
                "user_id": user_row["id"],
                "display_id": user_row["display_id"],
            }

        # 2. 专业大类
        if q in SUBJECT_CATEGORIES:
            return {"kind": "subject", "subject_category": q}

        # 3. 帖子内容
        posts_result = self.list_posts(sort="latest", q=q, page=1, page_size=20)
        return {"kind": "posts", "posts": posts_result["items"]}

    # ---------- upload ----------

    def upload_attachment(
        self, user_id: str, filename: str, content: bytes, content_type: str
    ) -> dict[str, str]:
        sb = self._sb()
        safe_name = ascii_storage_filename(filename)
        path = f"{user_id}/{uuid.uuid4().hex}_{safe_name}"
        sb.storage.from_("community-attachments").upload(
            path,
            content,
            file_options={
                "content-type": content_type or "application/octet-stream",
                "upsert": "false",
            },
        )
        url = sb.storage.from_("community-attachments").get_public_url(path)
        if not isinstance(url, str):
            url = str(url)
        return {"url": url, "name": filename, "mime_type": content_type or ""}


_community_service: CommunityService | None = None


def get_community_service() -> CommunityService:
    global _community_service
    if _community_service is None:
        _community_service = CommunityService()
    return _community_service
