"""择校数据中心 REST API。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.schools import (
    AdmissionRecordItem,
    MajorDetail,
    MajorStatisticsItem,
    PaginatedMajors,
    PaginatedSchools,
    SchoolDetail,
    ScoreLineItem,
)
from app.services.schools_service import get_schools_service
from app.utils.response import error_response, success_response

router = APIRouter(prefix="/api", tags=["择校数据中心"])


@router.get("/schools")
async def list_schools(
    page: int = Query(1, ge=1),
    keyword: str | None = Query(None),
    tag: str | None = Query(None, description="985 | 211 | 双一流"),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取学校列表。"""
    try:
        data: PaginatedSchools = get_schools_service().list_schools(
            page=page, keyword=keyword, tag=tag, page_size=page_size
        )
        return success_response(data.model_dump())
    except RuntimeError as exc:
        return error_response(str(exc))


@router.get("/schools/{school_id}")
async def get_school_detail(school_id: str):
    """获取学校详情（学院、专业、分数线）。"""
    try:
        detail: SchoolDetail | None = get_schools_service().get_school_detail(school_id)
    except RuntimeError as exc:
        return error_response(str(exc))
    if not detail:
        raise HTTPException(status_code=404, detail="学校不存在")
    return success_response(detail.model_dump())


@router.get("/majors/{major_id}")
async def get_major_detail(major_id: str):
    """获取专业详情及历年分数线。"""
    try:
        detail: MajorDetail | None = get_schools_service().get_major_detail(major_id)
    except RuntimeError as exc:
        return error_response(str(exc))
    if not detail:
        raise HTTPException(status_code=404, detail="专业不存在")
    return success_response(detail.model_dump())


@router.get("/majors")
async def list_majors(
    page: int = Query(1, ge=1),
    keyword: str | None = Query(None),
    school: str | None = Query(None, description="学校 UUID"),
    college: str | None = Query(None, description="学院 UUID"),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取专业列表，支持学校/学院/关键词筛选。"""
    try:
        data: PaginatedMajors = get_schools_service().list_majors(
            page=page,
            keyword=keyword,
            school_id=school,
            college_id=college,
            page_size=page_size,
        )
        return success_response(data.model_dump())
    except RuntimeError as exc:
        return error_response(str(exc))


@router.get("/statistics")
async def list_statistics(
    school: str | None = Query(None, description="学校 UUID"),
    college: str | None = Query(None, description="学院 UUID"),
    major: str | None = Query(None, description="专业 UUID"),
    year: int | None = Query(None, ge=2020, le=2030),
    limit: int = Query(200, ge=1, le=500),
):
    """获取专业录取统计（最低/平均/最高录取分）。"""
    try:
        items: list[MajorStatisticsItem] = get_schools_service().list_statistics(
            school_id=school,
            college_id=college,
            major_id=major,
            year=year,
            limit=limit,
        )
        return success_response([i.model_dump() for i in items])
    except RuntimeError as exc:
        return error_response(str(exc))


@router.get("/admissions")
async def list_admissions(
    school: str | None = Query(None, description="学校 UUID"),
    college: str | None = Query(None, description="学院 UUID"),
    major: str | None = Query(None, description="专业 UUID"),
    year: int | None = Query(None, ge=2020, le=2030),
    limit: int = Query(200, ge=1, le=500),
):
    """获取拟录取名单逐考生记录。"""
    try:
        items: list[AdmissionRecordItem] = get_schools_service().list_admissions(
            school_id=school,
            college_id=college,
            major_id=major,
            year=year,
            limit=limit,
        )
        return success_response([i.model_dump() for i in items])
    except RuntimeError as exc:
        return error_response(str(exc))


@router.get("/score-lines")
async def list_score_lines(
    school: str | None = Query(None, description="学校 UUID"),
    college: str | None = Query(None, description="学院 UUID"),
    major: str | None = Query(None, description="专业 UUID"),
    year: int | None = Query(None, ge=2020, le=2030),
    limit: int = Query(200, ge=1, le=500),
):
    """获取复试分数线，支持多维度筛选。"""
    try:
        items: list[ScoreLineItem] = get_schools_service().list_score_lines(
            school_id=school,
            college_id=college,
            major_id=major,
            year=year,
            limit=limit,
        )
        return success_response([i.model_dump() for i in items])
    except RuntimeError as exc:
        return error_response(str(exc))
