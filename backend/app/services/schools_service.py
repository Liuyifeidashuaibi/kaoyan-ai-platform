"""
择校数据中心 — Supabase 查询服务。

映射规范表名：
  schools      → universities（视图 schools）
  score_lines  → scores（视图 score_lines）
"""

from __future__ import annotations

import logging
from typing import Any

from supabase import Client, create_client

from app.config import get_settings
from app.schemas.schools import (
    AdmissionRecordItem,
    CollegeItem,
    MajorDetail,
    MajorItem,
    MajorStatisticsItem,
    PaginatedMajors,
    PaginatedSchools,
    SchoolDetail,
    SchoolListItem,
    ScoreLineItem,
)

logger = logging.getLogger(__name__)

SCORE_YEARS = (2025, 2026)
PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 100


class SchoolsService:
    def __init__(self) -> None:
        self._client: Client | None = None

    def _sb(self) -> Client:
        if self._client is None:
            s = get_settings()
            if not s.supabase_url or not s.supabase_service_key:
                raise RuntimeError("未配置 SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY")
            self._client = create_client(s.supabase_url, s.supabase_service_key)
        return self._client

    def _uni_to_school(self, row: dict[str, Any], major_count: int = 0) -> SchoolListItem:
        return SchoolListItem(
            id=row["id"],
            name=row["name"],
            is_985=bool(row.get("level_985")),
            is_211=bool(row.get("level_211")),
            is_double_first_class=bool(row.get("double_first_class")),
            province=row.get("province"),
            city=row.get("city"),
            school_type=row.get("school_type"),
            official_site=row.get("website"),
            graduate_site=row.get("graduate_url"),
            major_count=major_count,
        )

    def list_schools(
        self,
        *,
        page: int = 1,
        keyword: str | None = None,
        tag: str | None = None,
        page_size: int = PAGE_SIZE_DEFAULT,
    ) -> PaginatedSchools:
        sb = self._sb()
        page = max(1, page)
        page_size = min(max(1, page_size), PAGE_SIZE_MAX)
        offset = (page - 1) * page_size

        q = sb.table("universities").select(
            "id,name,province,city,level_985,level_211,double_first_class,school_type,website,graduate_url,majors(count)",
            count="exact",
        )

        if keyword:
            kw = keyword.strip()
            q = q.or_(f"name.ilike.%{kw}%,province.ilike.%{kw}%,city.ilike.%{kw}%")

        tag = (tag or "").strip().lower()
        if tag == "985":
            q = q.eq("level_985", True)
        elif tag == "211":
            q = q.eq("level_211", True)
        elif tag in ("双一流", "double_first_class", "syl"):
            q = q.not_.is_("double_first_class", "null")

        res = q.order("name").range(offset, offset + page_size - 1).execute()
        items: list[SchoolListItem] = []
        for row in res.data or []:
            mc = 0
            majors_rel = row.get("majors")
            if isinstance(majors_rel, list) and majors_rel:
                mc = int(majors_rel[0].get("count") or 0)
            elif isinstance(majors_rel, dict):
                mc = int(majors_rel.get("count") or 0)
            items.append(self._uni_to_school(row, mc))

        total = int(res.count or len(items))
        return PaginatedSchools(items=items, total=total, page=page, page_size=page_size)

    def get_school_detail(self, school_id: str) -> SchoolDetail | None:
        sb = self._sb()
        uni_res = (
            sb.table("universities")
            .select("id,name,province,city,level_985,level_211,double_first_class,school_type,website,graduate_url")
            .eq("id", school_id)
            .maybe_single()
            .execute()
        )
        if not uni_res.data:
            return None
        uni = uni_res.data

        colleges_res = (
            sb.table("colleges")
            .select("id,name,official_site")
            .eq("university_id", school_id)
            .order("name")
            .execute()
        )
        colleges = [
            CollegeItem(id=c["id"], name=c["name"], official_site=c.get("official_site"))
            for c in (colleges_res.data or [])
        ]

        majors_res = (
            sb.table("majors")
            .select("id,name,code,degree_type,study_mode,college,college_id,source_url")
            .eq("university_id", school_id)
            .order("code")
            .execute()
        )
        majors = [
            MajorItem(
                id=m["id"],
                major_name=m["name"],
                major_code=m.get("code"),
                degree_type=m.get("degree_type"),
                study_mode=m.get("study_mode"),
                college=m.get("college"),
                college_id=m.get("college_id"),
                source_url=m.get("source_url"),
            )
            for m in (majors_res.data or [])
        ]

        scores_res = (
            sb.table("scores")
            .select(
                "id,year,score_type,total_score,politics_score,english_score,"
                "professional1_score,professional2_score,remarks,source_url,publish_date,confidence,"
                "major_id,college_id,majors(name,college)"
            )
            .eq("university_id", school_id)
            .in_("year", list(SCORE_YEARS))
            .order("year", desc=True)
            .execute()
        )
        score_lines = self._map_score_rows(scores_res.data or [])

        school = self._uni_to_school(uni, len(majors))
        return SchoolDetail(
            school=school,
            colleges=colleges,
            majors=majors,
            score_lines=score_lines,
        )

    def get_major_detail(self, major_id: str) -> MajorDetail | None:
        sb = self._sb()
        major_res = (
            sb.table("majors")
            .select(
                "id,name,code,degree_type,study_mode,college,college_id,source_url,university_id,"
                "universities(id,name,province,city,level_985,level_211,double_first_class,school_type,website,graduate_url)"
            )
            .eq("id", major_id)
            .maybe_single()
            .execute()
        )
        if not major_res.data:
            return None
        row = major_res.data
        uni = row.get("universities") or {}

        scores_res = (
            sb.table("scores")
            .select(
                "id,year,score_type,total_score,politics_score,english_score,"
                "professional1_score,professional2_score,remarks,source_url,publish_date,confidence,"
                "major_id,college_id,majors(name,college)"
            )
            .eq("major_id", major_id)
            .in_("year", list(SCORE_YEARS))
            .order("year", desc=True)
            .execute()
        )

        major = MajorItem(
            id=row["id"],
            major_name=row["name"],
            major_code=row.get("code"),
            degree_type=row.get("degree_type"),
            study_mode=row.get("study_mode"),
            college=row.get("college"),
            college_id=row.get("college_id"),
            source_url=row.get("source_url"),
        )
        school = self._uni_to_school(uni)
        return MajorDetail(
            major=major,
            school=school,
            score_lines=self._map_score_rows(scores_res.data or []),
        )

    def list_score_lines(
        self,
        *,
        school_id: str | None = None,
        college_id: str | None = None,
        major_id: str | None = None,
        year: int | None = None,
        limit: int = 200,
    ) -> list[ScoreLineItem]:
        sb = self._sb()
        q = (
            sb.table("scores")
            .select(
                "id,year,score_type,total_score,politics_score,english_score,"
                "professional1_score,professional2_score,remarks,source_url,publish_date,confidence,"
                "major_id,college_id,university_id,majors(name,college)"
            )
            .in_("year", list(SCORE_YEARS))
            .order("year", desc=True)
            .limit(min(limit, 500))
        )
        if school_id:
            q = q.eq("university_id", school_id)
        if college_id:
            q = q.eq("college_id", college_id)
        if major_id:
            q = q.eq("major_id", major_id)
        if year:
            q = q.eq("year", year)

        res = q.execute()
        return self._map_score_rows(res.data or [])

    def _map_score_rows(self, rows: list[dict[str, Any]]) -> list[ScoreLineItem]:
        out: list[ScoreLineItem] = []
        for s in rows:
            majors = s.get("majors") or {}
            out.append(
                ScoreLineItem(
                    id=s["id"],
                    year=int(s["year"]),
                    score_type=s.get("score_type") or "复试线",
                    total_score=int(s["total_score"]),
                    politics_score=int(s["politics_score"]),
                    english_score=int(s["english_score"]),
                    major_one_score=s.get("professional1_score"),
                    major_two_score=s.get("professional2_score"),
                    remarks=s.get("remarks"),
                    source_url=s.get("source_url"),
                    publish_date=str(s["publish_date"]) if s.get("publish_date") else None,
                    confidence=s.get("confidence"),
                    major_id=s.get("major_id"),
                    major_name=majors.get("name") if isinstance(majors, dict) else None,
                    college_id=s.get("college_id"),
                    college_name=majors.get("college") if isinstance(majors, dict) else None,
                )
            )
        return out


    def list_majors(
        self,
        *,
        page: int = 1,
        keyword: str | None = None,
        school_id: str | None = None,
        college_id: str | None = None,
        page_size: int = PAGE_SIZE_DEFAULT,
    ) -> PaginatedMajors:
        sb = self._sb()
        page = max(1, page)
        page_size = min(max(1, page_size), PAGE_SIZE_MAX)
        offset = (page - 1) * page_size

        q = sb.table("majors").select(
            "id,name,code,degree_type,study_mode,college,college_id,source_url,university_id",
            count="exact",
        )
        if school_id:
            q = q.eq("university_id", school_id)
        if college_id:
            q = q.eq("college_id", college_id)
        if keyword:
            kw = keyword.strip()
            q = q.or_(f"name.ilike.%{kw}%,code.ilike.%{kw}%,college.ilike.%{kw}%")

        res = q.order("code").range(offset, offset + page_size - 1).execute()
        items = [
            MajorItem(
                id=m["id"],
                major_name=m["name"],
                major_code=m.get("code"),
                degree_type=m.get("degree_type"),
                study_mode=m.get("study_mode"),
                college=m.get("college"),
                college_id=m.get("college_id"),
                source_url=m.get("source_url"),
            )
            for m in (res.data or [])
        ]
        return PaginatedMajors(
            items=items,
            total=int(res.count or len(items)),
            page=page,
            page_size=page_size,
        )

    def list_statistics(
        self,
        *,
        school_id: str | None = None,
        college_id: str | None = None,
        major_id: str | None = None,
        year: int | None = None,
        limit: int = 200,
    ) -> list[MajorStatisticsItem]:
        sb = self._sb()
        q = (
            sb.table("major_statistics")
            .select(
                "id,year,min_score,avg_score,max_score,admitted_count,retest_count,"
                "admission_rate,retest_line,quota,exempt_count,source_url,source_title,"
                "publish_date,raw_file_path,major_id,college_id,university_id,"
                "majors(name,code,college),universities(name)"
            )
            .order("year", desc=True)
            .limit(min(limit, 500))
        )
        if school_id:
            q = q.eq("university_id", school_id)
        if college_id:
            q = q.eq("college_id", college_id)
        if major_id:
            q = q.eq("major_id", major_id)
        if year:
            q = q.eq("year", year)

        res = q.execute()
        return self._map_statistics_rows(res.data or [])

    def list_admissions(
        self,
        *,
        school_id: str | None = None,
        college_id: str | None = None,
        major_id: str | None = None,
        year: int | None = None,
        limit: int = 200,
    ) -> list[AdmissionRecordItem]:
        sb = self._sb()
        q = (
            sb.table("admission_records")
            .select(
                "id,year,candidate_no,candidate_name,initial_score,retest_score,final_score,"
                "admission_status,source_url,source_title,publish_date,raw_file_path,"
                "major_id,college_id,university_id,"
                "majors(name,code,college),universities(name)"
            )
            .order("year", desc=True)
            .limit(min(limit, 500))
        )
        if school_id:
            q = q.eq("university_id", school_id)
        if college_id:
            q = q.eq("college_id", college_id)
        if major_id:
            q = q.eq("major_id", major_id)
        if year:
            q = q.eq("year", year)

        res = q.execute()
        return self._map_admission_rows(res.data or [])

    def _map_statistics_rows(self, rows: list[dict[str, Any]]) -> list[MajorStatisticsItem]:
        out: list[MajorStatisticsItem] = []
        for row in rows:
            majors = row.get("majors") or {}
            uni = row.get("universities") or {}
            avg = row.get("avg_score")
            out.append(
                MajorStatisticsItem(
                    id=row["id"],
                    year=int(row["year"]),
                    min_score=row.get("min_score"),
                    avg_score=float(avg) if avg is not None else None,
                    max_score=row.get("max_score"),
                    admitted_count=int(row.get("admitted_count") or 0),
                    retest_count=row.get("retest_count"),
                    admission_rate=float(row["admission_rate"]) if row.get("admission_rate") is not None else None,
                    retest_line=row.get("retest_line"),
                    quota=row.get("quota"),
                    exempt_count=row.get("exempt_count"),
                    source_url=row.get("source_url"),
                    source_title=row.get("source_title"),
                    publish_date=str(row["publish_date"]) if row.get("publish_date") else None,
                    raw_file_path=row.get("raw_file_path"),
                    major_id=row["major_id"],
                    major_name=majors.get("name") if isinstance(majors, dict) else None,
                    major_code=majors.get("code") if isinstance(majors, dict) else None,
                    college_id=row.get("college_id"),
                    college_name=majors.get("college") if isinstance(majors, dict) else None,
                    school_id=row["university_id"],
                    school_name=uni.get("name") if isinstance(uni, dict) else None,
                )
            )
        return out

    def _map_admission_rows(self, rows: list[dict[str, Any]]) -> list[AdmissionRecordItem]:
        out: list[AdmissionRecordItem] = []
        for row in rows:
            majors = row.get("majors") or {}
            uni = row.get("universities") or {}
            out.append(
                AdmissionRecordItem(
                    id=row["id"],
                    year=int(row["year"]),
                    candidate_no=row.get("candidate_no"),
                    candidate_name=row.get("candidate_name"),
                    initial_score=row.get("initial_score"),
                    retest_score=row.get("retest_score"),
                    final_score=row.get("final_score"),
                    admission_status=row.get("admission_status") or "拟录取",
                    source_url=row.get("source_url"),
                    source_title=row.get("source_title"),
                    publish_date=str(row["publish_date"]) if row.get("publish_date") else None,
                    raw_file_path=row.get("raw_file_path"),
                    major_id=row.get("major_id"),
                    major_name=majors.get("name") if isinstance(majors, dict) else None,
                    major_code=majors.get("code") if isinstance(majors, dict) else None,
                    college_id=row.get("college_id"),
                    college_name=majors.get("college") if isinstance(majors, dict) else None,
                    school_id=row["university_id"],
                    school_name=uni.get("name") if isinstance(uni, dict) else None,
                )
            )
        return out


_service: SchoolsService | None = None


def get_schools_service() -> SchoolsService:
    global _service
    if _service is None:
        _service = SchoolsService()
    return _service
