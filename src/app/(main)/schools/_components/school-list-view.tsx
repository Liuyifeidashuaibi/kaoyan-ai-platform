"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { UniversityCard } from "@/components/schools/university-card";
import { SkeletonList } from "@/components/schools/skeleton-list";
import { EmptyState } from "@/components/schools/empty-state";
import {
  filterUniversitiesClient,
  prefetchUniversitiesList,
  SCHOOL_TYPES,
  type UniversityWithMajorCount,
} from "@/lib/api/schools";
import { useSchoolsFilter } from "../_context/schools-filter-context";
import type { SchoolsGlobalFilter } from "../_context/schools-filter-context";
import { useSchoolsSync } from "../_context/schools-sync-context";
import { useIncrementalList } from "@/hooks/use-incremental-list";
import { cn } from "@/lib/utils";

interface SchoolListViewProps {
  search: string;
  onLoadingChange?: (loading: boolean) => void;
}

const REGION_OPTIONS = [
  { value: "", label: "全国" },
  { value: "华北", label: "华北" },
  { value: "华东", label: "华东" },
  { value: "华南", label: "华南" },
  { value: "华中", label: "华中" },
  { value: "西南", label: "西南" },
  { value: "西北", label: "西北" },
  { value: "东北", label: "东北" },
];

const LEVEL_OPTIONS = [
  { key: "level985" as const, label: "985" },
  { key: "level211" as const, label: "211" },
  { key: "doubleFirstClass" as const, label: "双一流" },
];

export function SchoolListView({ search, onLoadingChange }: SchoolListViewProps) {
  const { filter, setFilter } = useSchoolsFilter();
  const [schoolType, setSchoolType] = useState("");
  const [region, setRegion] = useState("");
  const { version } = useSchoolsSync();
  const [allUniversities, setAllUniversities] = useState<UniversityWithMajorCount[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const onLoadingChangeRef = useRef(onLoadingChange);
  onLoadingChangeRef.current = onLoadingChange;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(false);
    onLoadingChangeRef.current?.(true);
    prefetchUniversitiesList()
      .then((data) => {
        if (!cancelled) setAllUniversities(data);
      })
      .catch(() => {
        if (!cancelled) {
          setAllUniversities([]);
          setLoadError(true);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
          onLoadingChangeRef.current?.(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [version]);

  const filtered = useMemo(() => {
    const list = filterUniversitiesClient(allUniversities, {
      level985: filter.level985,
      level211: filter.level211,
      doubleFirstClass: filter.doubleFirstClass,
      schoolType: schoolType || undefined,
      region: region || undefined,
      search,
    });
    return [...list].sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
  }, [allUniversities, filter, schoolType, region, search]);

  const { visibleItems, hasMore, loadMore, total } = useIncrementalList(filtered, 24);

  const levelActiveCount = [
    filter.level985,
    filter.level211,
    filter.doubleFirstClass,
  ].filter(Boolean).length;

  const hasActiveFilters =
    !!schoolType ||
    !!region ||
    levelActiveCount < 3 ||
    !!search;

  const toggleLevel = (key: keyof SchoolsGlobalFilter) => {
    const next = { ...filter, [key]: !filter[key] };
    if (!next.level985 && !next.level211 && !next.doubleFirstClass) return;
    setFilter(next);
  };

  return (
    <div>
      <div className="mb-4 space-y-3 rounded-2xl bg-white px-3 py-3 shadow-sm">
        <FilterRow label="院校类型">
          <InlineChip
            label="全部"
            active={!schoolType}
            onClick={() => setSchoolType("")}
          />
          {SCHOOL_TYPES.map((type) => (
            <InlineChip
              key={type}
              label={type}
              active={schoolType === type}
              onClick={() => setSchoolType(schoolType === type ? "" : type)}
            />
          ))}
        </FilterRow>

        <FilterRow label="院校层次">
          {LEVEL_OPTIONS.map(({ key, label }) => (
            <InlineChip
              key={key}
              label={label}
              active={filter[key]}
              onClick={() => toggleLevel(key)}
            />
          ))}
        </FilterRow>

        <FilterRow label="所在地区">
          {REGION_OPTIONS.map(({ value, label }) => (
            <InlineChip
              key={value || "all"}
              label={label}
              active={region === value}
              onClick={() => setRegion(value)}
            />
          ))}
        </FilterRow>
      </div>

      {!loading && (
        <p className="mb-3 text-sm text-muted-foreground">
          共 <span className="font-semibold text-[#007AFF]">{total}</span> 所院校
          {hasMore ? `，已显示 ${visibleItems.length} 所` : null}
        </p>
      )}

      {loading ? (
        <SkeletonList count={6} />
      ) : loadError ? (
        <EmptyState
          title="院校数据加载失败"
          description="网络异常或数据库连接超时，请点击刷新重试"
          icon="school"
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          title={allUniversities.length === 0 ? "暂无院校数据" : "未找到相关院校"}
          description={
            allUniversities.length === 0
              ? "数据同步中或网络异常，请稍后刷新"
              : hasActiveFilters
                ? "当前筛选条件下无匹配院校，可尝试放宽筛选"
                : "暂无符合条件的院校"
          }
          icon="school"
        />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {visibleItems.map((uni) => (
              <UniversityCard key={uni.id} university={uni} />
            ))}
          </div>
          {hasMore && (
            <div className="mt-6 flex justify-center">
              <button
                type="button"
                onClick={loadMore}
                className="rounded-xl border border-border bg-white px-6 py-2.5 text-sm font-medium hover:bg-muted/50"
              >
                加载更多（还剩 {total - visibleItems.length} 所）
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function FilterRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:gap-3">
      <span className="shrink-0 pt-1.5 text-xs font-medium text-muted-foreground sm:w-16">
        {label}
      </span>
      <div className="flex flex-1 flex-wrap gap-1.5">{children}</div>
    </div>
  );
}

function InlineChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-lg border px-2.5 py-1 text-xs transition-colors",
        active
          ? "border-[#007AFF]/30 bg-[#007AFF]/10 font-medium text-[#007AFF]"
          : "border-border bg-background text-foreground hover:bg-muted/50"
      )}
    >
      {label}
    </button>
  );
}
