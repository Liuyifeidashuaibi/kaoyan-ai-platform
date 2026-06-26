"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ChevronRight } from "lucide-react";
import { EmptyState } from "@/components/schools/empty-state";
import { SkeletonList } from "@/components/schools/skeleton-list";
import { LevelTags } from "@/components/schools/level-tags";
import { MajorCard } from "@/components/schools/major-card";
import {
  searchUnified,
  getUniversityInitial,
  type SchoolSearchHit,
  type AggregatedMajor,
} from "@/lib/api/schools";
import { useSchoolsSync } from "../_context/schools-sync-context";
import { cn } from "@/lib/utils";

interface SearchResultsViewProps {
  keyword: string;
  onLoadingChange?: (loading: boolean) => void;
  onBrowseAllMajors?: (keyword: string) => void;
}

const MATCH_ORDER: Record<SchoolSearchHit["matchReason"], number> = {
  both: 0,
  major: 1,
  school: 2,
};

const MATCH_LABELS: Record<SchoolSearchHit["matchReason"], string> = {
  both: "校名+专业",
  major: "专业匹配",
  school: "校名匹配",
};

export function SearchResultsView({
  keyword,
  onLoadingChange,
  onBrowseAllMajors,
}: SearchResultsViewProps) {
  const { version } = useSchoolsSync();
  const [schools, setSchools] = useState<SchoolSearchHit[]>([]);
  const [majors, setMajors] = useState<AggregatedMajor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    onLoadingChange?.(true);
    searchUnified(keyword)
      .then((data) => {
        if (!cancelled) {
          setSchools(data.schools);
          setMajors(data.majors);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSchools([]);
          setMajors([]);
          setError(true);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
          onLoadingChange?.(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [keyword, version, retryKey, onLoadingChange]);

  const sortedSchools = useMemo(
    () =>
      [...schools].sort((a, b) => {
        const reasonDiff = MATCH_ORDER[a.matchReason] - MATCH_ORDER[b.matchReason];
        if (reasonDiff !== 0) return reasonDiff;
        if (b.matchedMajors.length !== a.matchedMajors.length) {
          return b.matchedMajors.length - a.matchedMajors.length;
        }
        return a.name.localeCompare(b.name, "zh-CN");
      }),
    [schools]
  );

  if (loading) {
    return <SkeletonList count={5} />;
  }

  if (error) {
    return (
      <EmptyState
        title="搜索失败"
        description="网络异常，请稍后重试"
        icon="school"
        action={
          <button
            type="button"
            onClick={() => setRetryKey((k) => k + 1)}
            className="rounded-lg border border-border bg-white px-4 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
          >
            重试
          </button>
        }
      />
    );
  }

  if (schools.length === 0 && majors.length === 0) {
    return (
      <EmptyState
        title="未找到相关结果"
        description={`没有与「${keyword}」匹配的院校或专业，可尝试更短的关键词`}
        icon="search"
      />
    );
  }

  return (
    <div className="space-y-6">
      {majors.length > 0 && (
        <section>
          <p className="mb-3 text-sm text-muted-foreground">
            相关专业{" "}
            <span className="font-semibold text-[#111827]">{majors.length}</span> 个
          </p>
          <div className="flex flex-col gap-3">
            {majors.slice(0, 20).map((major) => (
              <MajorCard key={`${major.code}-${major.degree_type}`} major={major} />
            ))}
            {majors.length > 20 && (
              <button
                type="button"
                onClick={() => onBrowseAllMajors?.(keyword)}
                className="rounded-xl border border-dashed border-black/10 bg-black/5 py-3 text-center text-xs text-[#111827] hover:bg-black/10"
              >
                还有 {majors.length - 20} 个专业 · 切换到「按专业」浏览全部
              </button>
            )}
          </div>
        </section>
      )}

      {sortedSchools.length > 0 && (
        <section>
          <p className="mb-3 text-sm text-muted-foreground">
            相关院校{" "}
            <span className="font-semibold text-[#111827]">{sortedSchools.length}</span> 所
          </p>
          <div className="flex flex-col gap-3">
            {sortedSchools.map((hit) => (
              <SearchHitRow key={hit.id} hit={hit} keyword={keyword} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function SearchHitRow({ hit, keyword }: { hit: SchoolSearchHit; keyword: string }) {
  const initial = getUniversityInitial(hit.name);
  const majorsPreview = hit.matchedMajors.slice(0, 3);
  const moreCount = hit.matchedMajors.length - majorsPreview.length;
  const detailUrl =
    hit.matchReason === "school"
      ? `/schools/${hit.id}?tab=overview`
      : `/schools/${hit.id}?tab=majors`;

  return (
    <Link
      href={detailUrl}
      className="flex items-center gap-3 rounded-2xl bg-white p-4 shadow-sm transition-shadow hover:shadow-md"
    >
      {hit.logo_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={hit.logo_url}
          alt={hit.name}
          className="size-12 shrink-0 rounded-full object-cover ring-2 ring-black/10"
        />
      ) : (
        <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-black/5 ring-2 ring-black/10">
          <span className="text-sm font-bold text-[#111827]">{initial}</span>
        </div>
      )}

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="truncate text-base font-bold">{hit.name}</h3>
          <span
            className={cn(
              "shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium",
              hit.matchReason === "both"
                ? "bg-black/10 text-[#111827]"
                : hit.matchReason === "major"
                  ? "bg-black/5 text-[#111827]"
                  : "bg-muted text-muted-foreground"
            )}
          >
            {MATCH_LABELS[hit.matchReason]}
          </span>
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {hit.province} · {hit.city} · {hit.major_count} 个招生专业
        </p>
        {majorsPreview.length > 0 && (
          <p className="mt-1 truncate text-xs text-[#111827]/90">
            匹配专业：{majorsPreview.join("、")}
            {moreCount > 0 ? ` 等${hit.matchedMajors.length}个` : ""}
          </p>
        )}
        {hit.matchReason === "school" && keyword && (
          <p className="mt-0.5 text-xs text-muted-foreground">
            校名或所在地含「{keyword}」
          </p>
        )}
        <LevelTags university={hit} className="mt-2" />
      </div>

      <ChevronRight className="size-5 shrink-0 text-muted-foreground" />
    </Link>
  );
}
