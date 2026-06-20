"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { MajorCard } from "@/components/schools/major-card";
import { EmptyState } from "@/components/schools/empty-state";
import { SkeletonList } from "@/components/schools/skeleton-list";
import { TabNav } from "@/components/schools/tab-nav";
import {
  SUBJECT_CATEGORIES,
  SUBJECT_CATEGORY_CODES,
  aggregateMajorsClient,
  buildDisciplineTreeClient,
  prefetchMajorsCatalog,
} from "@/lib/api/schools";
import { useSchoolsFilter } from "../_context/schools-filter-context";
import { useSchoolsSync } from "../_context/schools-sync-context";
import { useIncrementalList } from "@/hooks/use-incremental-list";

interface MajorListViewProps {
  search: string;
  onLoadingChange?: (loading: boolean) => void;
  onClearInjectedSearch?: () => void;
}

const DEGREE_TABS = [
  { value: "学硕", label: "学术型硕士" },
  { value: "专硕", label: "专业型硕士" },
];

export function MajorListView({
  search,
  onLoadingChange,
  onClearInjectedSearch,
}: MajorListViewProps) {
  const { filter } = useSchoolsFilter();
  const [degreeType, setDegreeType] = useState<"学硕" | "专硕">("学硕");
  const [subjectCategory, setSubjectCategory] = useState("全部");
  const { version } = useSchoolsSync();
  const [catalog, setCatalog] = useState<Awaited<ReturnType<typeof prefetchMajorsCatalog>>>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const onLoadingChangeRef = useRef(onLoadingChange);
  onLoadingChangeRef.current = onLoadingChange;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(false);
    onLoadingChangeRef.current?.(true);
    prefetchMajorsCatalog()
      .then((rows) => {
        if (!cancelled) setCatalog(rows);
      })
      .catch(() => {
        if (!cancelled) {
          setCatalog([]);
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

  const disciplineTree = useMemo(
    () => (catalog.length > 0 ? buildDisciplineTreeClient(catalog) : {}),
    [catalog]
  );

  const majors = useMemo(
    () =>
      aggregateMajorsClient(catalog, {
        level985: filter.level985,
        level211: filter.level211,
        doubleFirstClass: filter.doubleFirstClass,
        degreeType,
        subjectCategory: subjectCategory !== "全部" ? subjectCategory : undefined,
        search,
      }),
    [catalog, filter, degreeType, subjectCategory, search]
  );

  const { visibleItems, hasMore, loadMore, total } = useIncrementalList(majors, 30);

  const categoryTabs = useMemo(
    () => [
      { value: "全部", label: "全部" },
      ...SUBJECT_CATEGORIES.map((cat) => ({
        value: cat,
        label: `${SUBJECT_CATEGORY_CODES[cat] ?? ""} ${cat}`.trim(),
      })),
    ],
    []
  );

  const disciplineCount =
    subjectCategory !== "全部"
      ? (disciplineTree[subjectCategory] ?? []).length
      : 0;

  const hasActiveFilters =
    subjectCategory !== "全部" ||
    !!search ||
    !filter.level985 ||
    !filter.level211 ||
    !filter.doubleFirstClass;

  const resetFilters = () => {
    setSubjectCategory("全部");
    onClearInjectedSearch?.();
  };

  return (
    <div>
      <div className="mb-3 overflow-hidden rounded-2xl bg-white shadow-sm">
        <TabNav
          tabs={DEGREE_TABS}
          active={degreeType}
          onChange={(v) => setDegreeType(v as "学硕" | "专硕")}
          activeColor="brand"
          className="border-none"
        />
      </div>

      <div className="mb-4 overflow-hidden rounded-2xl bg-white shadow-sm">
        <TabNav
          tabs={categoryTabs}
          active={subjectCategory}
          onChange={setSubjectCategory}
          activeColor="brand"
          className="border-none"
        />
        {subjectCategory !== "全部" && disciplineCount > 0 && (
          <p className="border-t border-border/60 px-4 py-2 text-xs text-muted-foreground">
            {subjectCategory} 下设 {disciplineCount} 个一级学科
          </p>
        )}
      </div>

      {!loading && search && (
        <p className="mb-3 text-xs text-[#007AFF]">
          关键词筛选：「{search}」
          <button
            type="button"
            onClick={resetFilters}
            className="ml-2 font-medium hover:underline"
          >
            清除
          </button>
        </p>
      )}

      {!loading && (
        <p className="mb-3 text-sm text-muted-foreground">
          共找到{" "}
          <span className="font-semibold text-[#007AFF]">{total}</span>{" "}
          个{degreeType === "学硕" ? "学术型" : "专业型"}招生专业
          {hasMore ? `，已显示 ${visibleItems.length} 个` : null}
        </p>
      )}

      {loading ? (
        <>
          <p className="mb-3 text-xs text-muted-foreground">
            专业目录数据量较大，首次加载可能需要一些时间…
          </p>
          <SkeletonList count={6} />
        </>
      ) : loadError ? (
        <EmptyState
          title="专业数据加载失败"
          description="网络异常或数据库连接超时，请点击右上角刷新重试"
          icon="school"
        />
      ) : majors.length === 0 ? (
        <EmptyState
          title={catalog.length === 0 ? "暂无专业数据" : "未找到相关专业"}
          description={
            catalog.length === 0
              ? "数据同步中或网络异常，请稍后刷新"
              : hasActiveFilters
                ? "当前筛选条件下无匹配专业，可尝试放宽筛选"
                : "暂无符合条件的专业"
          }
          action={
            hasActiveFilters && catalog.length > 0 ? (
              <button
                type="button"
                onClick={resetFilters}
                className="rounded-lg border border-border bg-white px-4 py-2 text-sm font-medium hover:bg-muted/50"
              >
                清除筛选
              </button>
            ) : undefined
          }
        />
      ) : (
        <>
          <div className="flex flex-col gap-3">
            {visibleItems.map((major) => (
              <MajorCard
                key={`${major.code}-${major.degree_type}`}
                major={major}
              />
            ))}
          </div>
          {hasMore && (
            <div className="mt-6 flex justify-center">
              <button
                type="button"
                onClick={loadMore}
                className="rounded-xl border border-border bg-white px-6 py-2.5 text-sm font-medium hover:bg-muted/50"
              >
                加载更多（还剩 {total - visibleItems.length} 个）
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
