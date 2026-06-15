"""Supabase 批量写入与专业匹配（import_kaoyan_full 使用）。"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

log = logging.getLogger("db_import_utils")

BATCH_SIZE = 500


def resolve_major_id(
    majors: list[dict],
    code: str,
    name: str,
    degree_type: str,
) -> Optional[str]:
    code6 = re.sub(r"\D", "", code)[:6]
    if len(code6) != 6:
        code6 = ""

    candidates: list[dict] = []
    for m in majors:
        mcode = re.sub(r"\D", "", str(m.get("code") or ""))[:6]
        if code6 and mcode != code6:
            continue
        if degree_type and m.get("degree_type") and m["degree_type"] != degree_type:
            continue
        candidates.append(m)

    if not candidates and code6:
        candidates = [
            m for m in majors
            if re.sub(r"\D", "", str(m.get("code") or ""))[:6] == code6
        ]

    if not candidates and name:
        for m in majors:
            mname = (m.get("name") or "").strip()
            if mname == name or (name in mname or mname in name):
                candidates.append(m)

    if not candidates:
        return None

    best = max(
        candidates,
        key=lambda m: (
            1 if m.get("study_mode") == "全日制" else 0,
            len(m.get("college") or ""),
        ),
    )
    return best["id"]


def resolve_major_id_relaxed(
    majors: list[dict],
    code: str,
    name: str,
    degree_type: str,
    college: str = "",
) -> Optional[str]:
    mid = resolve_major_id(majors, code, name, degree_type)
    if mid:
        return mid

    code6 = re.sub(r"\D", "", code)[:6]
    college = (college or "").strip()

    if len(code6) == 6:
        by_code = [
            m for m in majors
            if re.sub(r"\D", "", str(m.get("code") or ""))[:6] == code6
        ]
        if college and by_code:
            by_college = [
                m for m in by_code
                if college in (m.get("college") or "")
                or (m.get("college") or "") in college
            ]
            if len(by_college) == 1:
                return by_college[0]["id"]
            if by_college:
                by_code = by_college
        if len(by_code) == 1:
            return by_code[0]["id"]
        if by_code:
            return max(
                by_code,
                key=lambda m: (
                    1 if m.get("study_mode") == "全日制" else 0,
                    len(m.get("college") or ""),
                ),
            )["id"]

    if name:
        name = name.strip()
        by_name = [m for m in majors if (m.get("name") or "").strip() == name]
        if len(by_name) == 1:
            return by_name[0]["id"]
        for m in majors:
            mname = (m.get("name") or "").strip()
            if mname and (name in mname or mname in name):
                return m["id"]
    return None


def batch_upsert(sb: Any, table: str, rows: list[dict], on_conflict: str) -> int:
    written = 0
    for i in range(0, len(rows), BATCH_SIZE):
        chunk = rows[i : i + BATCH_SIZE]
        try:
            sb.table(table).upsert(chunk, on_conflict=on_conflict).execute()
            written += len(chunk)
        except Exception as exc:
            log.error("batch upsert %s [%d:%d]: %s", table, i, i + len(chunk), exc)
    return written
