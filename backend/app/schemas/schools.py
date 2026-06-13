"""择校数据中心 API 数据模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SchoolListItem(BaseModel):
    id: str
    name: str
    is_985: bool = False
    is_211: bool = False
    is_double_first_class: bool = False
    province: str | None = None
    city: str | None = None
    school_type: str | None = None
    official_site: str | None = None
    graduate_site: str | None = None
    major_count: int = 0


class CollegeItem(BaseModel):
    id: str
    name: str
    official_site: str | None = None


class MajorItem(BaseModel):
    id: str
    major_name: str
    major_code: str | None = None
    degree_type: str | None = None
    study_mode: str | None = None
    college: str | None = None
    college_id: str | None = None
    source_url: str | None = None


class ScoreLineItem(BaseModel):
    id: str
    year: int
    score_type: str = "复试线"
    total_score: int
    politics_score: int
    english_score: int
    major_one_score: int | None = None
    major_two_score: int | None = None
    remarks: str | None = None
    source_url: str | None = None
    publish_date: str | None = None
    confidence: float | None = None
    major_id: str | None = None
    major_name: str | None = None
    college_id: str | None = None
    college_name: str | None = None


class SchoolDetail(BaseModel):
    school: SchoolListItem
    colleges: list[CollegeItem] = Field(default_factory=list)
    majors: list[MajorItem] = Field(default_factory=list)
    score_lines: list[ScoreLineItem] = Field(default_factory=list)


class MajorDetail(BaseModel):
    major: MajorItem
    school: SchoolListItem
    score_lines: list[ScoreLineItem] = Field(default_factory=list)


class PaginatedSchools(BaseModel):
    items: list[SchoolListItem]
    total: int
    page: int
    page_size: int


class MajorStatisticsItem(BaseModel):
    id: str
    year: int
    min_score: int | None = None
    avg_score: float | None = None
    max_score: int | None = None
    admitted_count: int = 0
    retest_count: int | None = None
    admission_rate: float | None = None
    retest_line: int | None = None
    quota: int | None = None
    exempt_count: int | None = None
    source_url: str | None = None
    source_title: str | None = None
    publish_date: str | None = None
    raw_file_path: str | None = None
    major_id: str
    major_name: str | None = None
    major_code: str | None = None
    college_id: str | None = None
    college_name: str | None = None
    school_id: str
    school_name: str | None = None


class AdmissionRecordItem(BaseModel):
    id: str
    year: int
    candidate_no: str | None = None
    candidate_name: str | None = None
    initial_score: int | None = None
    retest_score: int | None = None
    final_score: int | None = None
    admission_status: str = "拟录取"
    source_url: str | None = None
    source_title: str | None = None
    publish_date: str | None = None
    raw_file_path: str | None = None
    major_id: str | None = None
    major_name: str | None = None
    major_code: str | None = None
    college_id: str | None = None
    college_name: str | None = None
    school_id: str
    school_name: str | None = None


class PaginatedMajors(BaseModel):
    items: list[MajorItem]
    total: int
    page: int
    page_size: int
