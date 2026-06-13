#!/usr/bin/env python3
"""
执行 Supabase SQL 迁移文件。

用法：
  python scripts/run_migration.py 007_choose_school_datacenter.sql

需要以下任一凭据（写入 .env.local）：
  SUPABASE_DB_PASSWORD=...        # 数据库密码（Settings → Database）
  SUPABASE_ACCESS_TOKEN=...       # 个人访问令牌（Account → Access Tokens）
  DATABASE_URL=postgresql://...   # 直连连接串
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
PROJECT_REF = "zlgogxuzkmirxinorert"
MIGRATIONS = ROOT / "supabase" / "migrations"


def load_env() -> None:
    for p in (ROOT / ".env.local", ROOT / ".env", ROOT / "crawler" / ".env"):
        if p.exists():
            load_dotenv(p)


def connection_candidates() -> list[str]:
    out: list[str] = []
    db_url = os.getenv("DATABASE_URL", "")
    if db_url.startswith("postgresql"):
        out.append(db_url)

    password = os.getenv("SUPABASE_DB_PASSWORD", "")
    if password:
        enc = requests.utils.quote(password, safe="")
        regions = [
            "aws-0-ap-northeast-1.pooler.supabase.com:6543",
            "aws-0-ap-southeast-1.pooler.supabase.com:6543",
            "aws-0-us-east-1.pooler.supabase.com:6543",
            f"db.{PROJECT_REF}.supabase.co:5432",
        ]
        for host in regions:
            if "pooler" in host:
                out.append(
                    f"postgresql://postgres.{PROJECT_REF}:{enc}@{host}/postgres"
                )
            else:
                out.append(f"postgresql://postgres:{enc}@{host}/postgres")
    return out


def run_via_management_api(sql: str, token: str) -> None:
    resp = requests.post(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"query": sql},
        timeout=120,
    )
    if not resp.ok:
        raise RuntimeError(f"Management API {resp.status_code}: {resp.text}")


def run_via_psycopg2(conn_str: str, sql: str) -> None:
    import psycopg2

    conn = psycopg2.connect(conn_str, sslmode="require")
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql)
    finally:
        conn.close()


def main() -> int:
    load_env()
    if len(sys.argv) < 2:
        print("用法: python scripts/run_migration.py <migration_file.sql>")
        return 1

    sql_path = MIGRATIONS / sys.argv[1]
    if not sql_path.exists():
        sql_path = Path(sys.argv[1])
    if not sql_path.exists():
        print(f"找不到迁移文件: {sys.argv[1]}")
        return 1

    sql = sql_path.read_text(encoding="utf-8")
    print(f"执行迁移: {sql_path.name} ({len(sql)} bytes)")

    token = os.getenv("SUPABASE_ACCESS_TOKEN", "").strip()
    if token:
        print("→ Supabase Management API")
        run_via_management_api(sql, token)
        print("✓ 迁移完成")
        return 0

    last_err: Exception | None = None
    for conn in connection_candidates():
        try:
            print(f"→ Postgres: {conn.split('@')[-1]}")
            run_via_psycopg2(conn, sql)
            print("✓ 迁移完成")
            return 0
        except Exception as exc:
            last_err = exc
            print(f"  连接失败: {exc}")

    print(
        "\n缺少数据库凭据。请在 .env.local 添加其一：\n"
        "  SUPABASE_DB_PASSWORD=你的数据库密码\n"
        "  SUPABASE_ACCESS_TOKEN=你的 Supabase 个人令牌\n"
        "获取方式：Supabase Dashboard → Settings → Database → Database password\n"
        "或 Account → Access Tokens → Generate new token"
    )
    if last_err:
        print(f"\n最后一次错误: {last_err}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
