"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { UniversityCard } from "@/components/schools/university-card";
import { SkeletonList } from "@/components/schools/skeleton-list";
import { EmptyState } from "@/components/schools/empty-state";
import { TabNav } from "@/components/schools/tab-nav";
import {
  getUniversities,
  REGION_MAP,
  type UniversityFilters,
  type UniversityWithMajorCount,
} from "@/lib/api/schools";
import { useSchoolsFilter } from "../_context/schools-filter-context";

interface SchoolListViewProps {
  search: string;
}

const REGIONS = Object.keys(REGION_MAP);

export function SchoolListView({ search }: SchoolListViewProps) {
  const { filter } = useSchoolsFilter();
  const [region, setRegion] = useState("全国");
  const [universities, setUniversities] = useState<UniversityWithMajorCount[]>([]);
  const [loading, setLoading] = useState(true);
  const abortRef = useRef<AbortController | null>(null);

  const fetchData = useCallback(async () => {
    // 取消上一次请求
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setLoading(true);
    try {
      const filters: UniversityFilters = {
        level985: filter.level985,
        level211: filter.level211,
        doubleFirstClass: filter.doubleFirstClass,
        region,
        search,
      };
      const data = await getUniversities(filters);
      setUniversities(data);
    } catch (err) {
      if ((err as Error)?.name !== "AbortError") {
        console.error("加载院校列表失败:", err);
      }
    } finally {
      setLoading(false);
    }
  }, [filter, region, search]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const regionTabs = useMemo(
    () => REGIONS.map((r) => ({ value: r, label: r })),
    []
  );

  return (
    <div className="flex flex-col h-full">
      {/* 大区快捷筛选 */}
      <div className="bg-background border-b border-border">
        <TabNav
          tabs={regionTabs}
          active={region}
          onChange={setRegion}
          activeColor="orange"
        />
      </div>

      {/* 列表区域 */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <SkeletonList count={8} className="rounded-none" />
        ) : universities.length === 0 ? (
          <EmptyState
            title="未找到相关院校"
            description={
              search
                ? `没有与"${search}"匹配的院校`
                : "当前筛选条件下无院校数据"
            }
            icon="school"
          />
        ) : (
          <div className="bg-card">
            {/* 结果计数 */}
            <div className="px-4 py-2 text-xs text-muted-foreground border-b border-border">
              共 {universities.length} 所院校
            </div>
            {universities.map((uni) => (
              <UniversityCard key={uni.id} university={uni} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
