"""
择校数据 Redis 缓存 Facade — 包装 SchoolsService，不修改其内部 Supabase 查询逻辑。
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings
from app.infrastructure.cache import keys
from app.infrastructure.cache.redis_client import cache_get_json, cache_set_json
from app.schemas.schools import (
    AdmissionRecordItem,
    MajorDetail,
    MajorStatisticsItem,
    PaginatedMajors,
    PaginatedSchools,
    SchoolDetail,
    ScoreLineItem,
)
from app.services.schools_service import SchoolsService, get_schools_service

logger = logging.getLogger(__name__)


class CachedSchoolsFacade:
    """在 SchoolsService 外包一层 Redis 读穿透缓存。"""

    def __init__(self, inner: SchoolsService | None = None) -> None:
        self._inner = inner or get_schools_service()
        settings = get_settings()
        self._ttl_list = settings.cache_ttl_schools_list
        self._ttl_detail = settings.cache_ttl_schools_detail
        self._ttl_scores = settings.cache_ttl_score_lines

    def list_schools(
        self,
        *,
        page: int = 1,
        keyword: str | None = None,
        tag: str | None = None,
        page_size: int = 20,
    ) -> PaginatedSchools:
        cache_key = keys.schools_list_key(page, keyword, tag, page_size)
        cached = cache_get_json(cache_key)
        if cached is not None:
            return PaginatedSchools.model_validate(cached)

        result = self._inner.list_schools(
            page=page, keyword=keyword, tag=tag, page_size=page_size
        )
        cache_set_json(cache_key, result.model_dump(), self._ttl_list)
        return result

    def get_school_detail(self, school_id: str) -> SchoolDetail | None:
        cache_key = keys.school_detail_key(school_id)
        cached = cache_get_json(cache_key)
        if cached is not None:
            return SchoolDetail.model_validate(cached)

        result = self._inner.get_school_detail(school_id)
        if result:
            cache_set_json(cache_key, result.model_dump(), self._ttl_detail)
        return result

    def get_major_detail(self, major_id: str) -> MajorDetail | None:
        cache_key = f"{keys.PREFIX_SCHOOLS}major:{major_id}"
        cached = cache_get_json(cache_key)
        if cached is not None:
            return MajorDetail.model_validate(cached)

        result = self._inner.get_major_detail(major_id)
        if result:
            cache_set_json(cache_key, result.model_dump(), self._ttl_detail)
        return result

    def list_majors(self, **kwargs: Any) -> PaginatedMajors:
        cache_key = keys.PREFIX_SCHOOLS + "majors:" + keys.score_lines_key(**kwargs).split(":")[-1]
        cached = cache_get_json(cache_key)
        if cached is not None:
            return PaginatedMajors.model_validate(cached)

        result = self._inner.list_majors(**kwargs)
        cache_set_json(cache_key, result.model_dump(), self._ttl_list)
        return result

    def list_score_lines(self, **kwargs: Any) -> list[ScoreLineItem]:
        cache_key = keys.score_lines_key(**kwargs)
        cached = cache_get_json(cache_key)
        if cached is not None:
            return [ScoreLineItem.model_validate(i) for i in cached]

        items = self._inner.list_score_lines(**kwargs)
        cache_set_json(cache_key, [i.model_dump() for i in items], self._ttl_scores)
        return items

    def list_statistics(self, **kwargs: Any) -> list[MajorStatisticsItem]:
        cache_key = keys.PREFIX_SCHOOLS + "stats:" + keys.score_lines_key(**kwargs).split(":")[-1]
        cached = cache_get_json(cache_key)
        if cached is not None:
            return [MajorStatisticsItem.model_validate(i) for i in cached]

        items = self._inner.list_statistics(**kwargs)
        cache_set_json(cache_key, [i.model_dump() for i in items], self._ttl_scores)
        return items

    def list_admissions(self, **kwargs: Any) -> list[AdmissionRecordItem]:
        # 拟录取名单变更较频繁，短 TTL
        cache_key = keys.PREFIX_SCHOOLS + "adm:" + keys.score_lines_key(**kwargs).split(":")[-1]
        cached = cache_get_json(cache_key)
        if cached is not None:
            return [AdmissionRecordItem.model_validate(i) for i in cached]

        items = self._inner.list_admissions(**kwargs)
        cache_set_json(cache_key, [i.model_dump() for i in items], self._ttl_scores)
        return items


_facade: CachedSchoolsFacade | None = None


def get_cached_schools_facade() -> CachedSchoolsFacade:
    global _facade
    if _facade is None:
        _facade = CachedSchoolsFacade()
    return _facade
