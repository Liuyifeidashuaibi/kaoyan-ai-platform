#!/usr/bin/env python3
"""社区 API 冒烟测试（需 Supabase + 后端已启动）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import jwt

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

for name in (".env", ".env.local", "crawler/.env"):
    p = ROOT / name
    if p.exists():
        load_dotenv(p)

from app.config import get_settings
from supabase import create_client


def main() -> int:
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001").rstrip("/")
    proxy = (sys.argv[2] if len(sys.argv) > 2 else "").rstrip("/")

    settings = get_settings()
    sb = create_client(settings.effective_supabase_url, settings.effective_supabase_service_key)
    uid = sb.table("users").select("id").limit(1).execute().data[0]["id"]
    token = jwt.encode({"sub": uid, "aud": "authenticated"}, "test", algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}

    failures: list[str] = []

    def check(label: str, url: str, method: str = "GET", **kwargs) -> dict | None:
        try:
            r = httpx.request(method, url, timeout=20, headers=headers, **kwargs)
            if r.headers.get("content-type", "").startswith("application/json"):
                body = r.json()
            else:
                body = {"raw": r.text}
            ok = r.status_code == 200 and body.get("success") is not False
            if not ok and r.status_code == 200 and body.get("success") is False:
                ok = False
            status = "OK" if ok else "FAIL"
            print(f"  [{status}] {label} -> {r.status_code}")
            if not ok:
                failures.append(f"{label}: {r.status_code} {json.dumps(body, ensure_ascii=False)[:200]}")
            return body if isinstance(body, dict) else None
        except Exception as exc:
            print(f"  [FAIL] {label} -> {exc}")
            failures.append(f"{label}: {exc}")
            return None

    print(f"Backend: {base}")
    check("health", f"{base}/api/health")
    check("list posts", f"{base}/api/community/posts?sort=latest")

    created = check(
        "create post",
        f"{base}/api/community/posts",
        method="POST",
        json={
            "post_type": "experience",
            "subject_category": "工学",
            "title": "冒烟测试帖",
            "content": "自动化测试内容",
            "attachments": [],
        },
    )
    post_id = (created or {}).get("data", {}).get("id") if created else None

    if post_id:
        check("get post", f"{base}/api/community/posts/{post_id}")
        check(
            "create comment",
            f"{base}/api/community/posts/{post_id}/comments",
            method="POST",
            json={"content": "测试评论", "parent_id": None},
        )
        check("list comments", f"{base}/api/community/posts/{post_id}/comments")
        check(
            "toggle favorite",
            f"{base}/api/community/posts/{post_id}/favorite",
            method="POST",
        )
        check("delete post", f"{base}/api/community/posts/{post_id}", method="DELETE")

    if proxy:
        print(f"Proxy: {proxy}")
        check("proxy list", f"{proxy}/api/community/posts?sort=latest")
        check(
            "proxy create",
            f"{proxy}/api/community/posts",
            method="POST",
            json={
                "post_type": "material",
                "subject_category": "理学",
                "title": "代理测试帖",
                "content": "via next rewrite",
                "attachments": [],
            },
        )

    if failures:
        print("\n失败项:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("\n全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
