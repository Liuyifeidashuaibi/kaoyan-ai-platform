"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight } from "lucide-react";
import { EmptyState } from "@/components/schools/empty-state";
import { SkeletonList } from "@/components/schools/skeleton-list";
import {
  getMajorsByCategory,
  SUBJECT_CATEGORIES,
  type MajorWithSchool,
} from "@/lib/api/schools";
import { useSchoolsFilter } from "../_context/schools-filter-context";
import { cn } from "@/lib/utils";

type MajorWithUniversity = MajorWithSchool;

interface MajorListViewProps {
  search: string;
}

export function MajorListView({ search }: MajorListViewProps) {
  const { filter } = useSchoolsFilter();
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [majors, setMajors] = useState<MajorWithSchool[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchMajors = useCallback(
    async (category: string) => {
      setLoading(true);
      try {
        const data = await getMajorsByCategory(category, {
          level985: filter.level985,
          level211: filter.level211,
          doubleFirstClass: filter.doubleFirstClass,
        });
        setMajors(data);
      } catch (err) {
        console.error("加载专业列表失败:", err);
        setMajors([]);
      } finally {
        setLoading(false);
      }
    },
    [filter]
  );

  const handleCategoryClick = (cat: string) => {
    if (activeCategory === cat) {
      setActiveCategory(null);
      setMajors([]);
    } else {
      setActiveCategory(cat);
      fetchMajors(cat);
    }
  };

  // filter 变化时重新获取
  useEffect(() => {
    if (activeCategory) {
      fetchMajors(activeCategory);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  const filteredMajors = search.trim()
    ? majors.filter(
        (m) =>
          m.name.toLowerCase().includes(search.toLowerCase()) ||
          (m.code ?? "").toLowerCase().includes(search.toLowerCase()) ||
          (m.university?.name ?? "").toLowerCase().includes(search.toLowerCase())
      )
    : majors;

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="bg-card">
        {SUBJECT_CATEGORIES.map((cat) => (
          <div key={cat} className="border-b border-border last:border-0">
            {/* 学科门类行 */}
            <button
              onClick={() => handleCategoryClick(cat)}
              className="flex w-full items-center justify-between px-4 py-3.5 active:bg-muted/50 transition-colors"
            >
              <span className="text-sm font-medium">{cat}</span>
              {activeCategory === cat ? (
                <ChevronDown className="size-4 text-muted-foreground" />
              ) : (
                <ChevronRight className="size-4 text-muted-foreground" />
              )}
            </button>

            {/* 专业列表（展开态） */}
            {activeCategory === cat && (
              <div className="bg-muted/30 border-t border-border">
                {loading ? (
                  <SkeletonList count={4} className="rounded-none" />
                ) : filteredMajors.length === 0 ? (
                  <EmptyState
                    title="暂无数据"
                    description={
                      search
                        ? `无"${search}"相关专业`
                        : "该学科门类暂无招生专业"
                    }
                    className="py-8"
                  />
                ) : (
                  filteredMajors.map((major) => (
                    <Link
                      key={major.id}
                      href={`/schools/${major.university_id}`}
                      className="flex items-start gap-3 px-4 py-3 border-b border-border/50 last:border-0 active:bg-muted/50 transition-colors"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-mono text-muted-foreground">
                            {major.code}
                          </span>
                          <span className="text-sm font-medium truncate">
                            {major.name}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <span>{major.university?.name ?? "—"}</span>
                          <span>·</span>
                          <span>{major.university?.province}</span>
                        </div>
                      </div>
                      <div className="flex flex-col gap-1 shrink-0">
                        <DegreeTag type={major.degree_type ?? "学硕"} />
                        <ModeTag mode={major.study_mode ?? "全日制"} />
                      </div>
                    </Link>
                  ))
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function DegreeTag({ type }: { type: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-1.5 py-px text-[10px] font-medium border",
        type === "学硕"
          ? "bg-blue-50 text-blue-600 border-blue-200"
          : "bg-orange-50 text-orange-600 border-orange-200"
      )}
    >
      {type}
    </span>
  );
}

function ModeTag({ mode }: { mode: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-1.5 py-px text-[10px] font-medium border",
        mode === "全日制"
          ? "bg-green-50 text-green-600 border-green-200"
          : "bg-gray-50 text-gray-500 border-gray-200"
      )}
    >
      {mode}
    </span>
  );
}
