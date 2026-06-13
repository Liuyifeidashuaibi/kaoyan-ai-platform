"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, SlidersHorizontal } from "lucide-react";
import { UniversityCard } from "@/components/schools/university-card";
import { SkeletonList } from "@/components/schools/skeleton-list";
import { EmptyState } from "@/components/schools/empty-state";
import { BottomFilterSheet } from "@/components/schools/bottom-filter-sheet";
import {
  filterUniversitiesClient,
  prefetchUniversitiesList,
  SCHOOL_TYPES,
  type UniversityWithMajorCount,
} from "@/lib/api/schools";
import { useSchoolsFilter } from "../_context/schools-filter-context";
import { useSchoolsSync } from "../_context/schools-sync-context";
import { GlobalFilterDrawer } from "./global-filter-drawer";
import { cn } from "@/lib/utils";

interface SchoolListViewProps {
  search: string;
  onLoadingChange?: (loading: boolean) => void;
}

const REGION_OPTIONS = [
  { value: "华北", label: "华北" },
  { value: "华东", label: "华东" },
  { value: "华南", label: "华南" },
  { value: "华中", label: "华中" },
  { value: "西南", label: "西南" },
  { value: "西北", label: "西北" },
  { value: "东北", label: "东北" },
];

const SCHOOL_TYPE_OPTIONS = SCHOOL_TYPES.map((t) => ({ value: t, label: t }));

type FilterKey = "type" | "level" | "region" | null;

export function SchoolListView({ search, onLoadingChange }: SchoolListViewProps) {
  const { filter } = useSchoolsFilter();
  const [schoolType, setSchoolType] = useState("");
  const [region, setRegion] = useState("");
  const [activeSheet, setActiveSheet] = useState<FilterKey>(null);
  const [levelDrawerOpen, setLevelDrawerOpen] = useState(false);
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

  const levelActiveCount = [
    filter.level985,
    filter.level211,
    filter.doubleFirstClass,
  ].filter(Boolean).length;

  const levelLabel =
    levelActiveCount === 3
      ? "全部层次"
      : [
          filter.level985 && "985",
          filter.level211 && "211",
          filter.doubleFirstClass && "双一流",
        ]
          .filter(Boolean)
          .join("、");

  const hasActiveFilters =
    !!schoolType ||
    !!region ||
    levelActiveCount < 3 ||
    !!search;

  return (
    <div>
      <div className="mb-4 rounded-2xl bg-white px-3 py-2 shadow-sm">
        <div className="flex flex-wrap items-center gap-2">
          <FilterChip
            label="院校类型"
            value={schoolType || "全部"}
            active={!!schoolType}
            onClick={() => setActiveSheet("type")}
          />
          <FilterChip
            label="院校层次"
            value={levelLabel}
            active={levelActiveCount < 3}
            onClick={() => setLevelDrawerOpen(true)}
            icon={<SlidersHorizontal className="size-3.5" />}
          />
          <FilterChip
            label="所在地区"
            value={region || "全国"}
            active={!!region}
            onClick={() => setActiveSheet("region")}
          />
        </div>
      </div>

      <BottomFilterSheet
        open={activeSheet === "type"}
        onClose={() => setActiveSheet(null)}
        title="院校类型"
        options={SCHOOL_TYPE_OPTIONS}
        selected={schoolType}
        onSelect={setSchoolType}
        allLabel="全部类型"
      />
      <BottomFilterSheet
        open={activeSheet === "region"}
        onClose={() => setActiveSheet(null)}
        title="所在地区"
        options={REGION_OPTIONS}
        selected={region}
        onSelect={setRegion}
        allLabel="全国"
      />
      <GlobalFilterDrawer
        open={levelDrawerOpen}
        onClose={() => setLevelDrawerOpen(false)}
      />

      {!loading && (
        <p className="mb-3 text-sm text-muted-foreground">
          共 <span className="font-semibold text-orange-500">{filtered.length}</span> 所院校
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
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((uni) => (
            <UniversityCard key={uni.id} university={uni} />
          ))}
        </div>
      )}
    </div>
  );
}

function FilterChip({
  label,
  value,
  active,
  onClick,
  icon,
}: {
  label: string;
  value: string;
  active: boolean;
  onClick: () => void;
  icon?: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-sm transition-colors",
        active
          ? "border-orange-200 bg-orange-50 font-medium text-orange-700"
          : "border-border bg-background text-foreground hover:bg-muted/40"
      )}
    >
      <span className="text-muted-foreground">{label}</span>
      <span className="max-w-[8rem] truncate">{value}</span>
      {icon ?? <ChevronDown className="size-3.5 text-muted-foreground" />}
    </button>
  );
}
