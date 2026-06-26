"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, Search, X } from "lucide-react";
import { FilterDropdown } from "@/components/schools/filter-dropdown";
import { EmptyState } from "@/components/schools/empty-state";
import { MajorCodeTag } from "@/components/schools/major-code-tag";
import { cn } from "@/lib/utils";
import {
  isValidMajorRecord,
  resolveCollegeGroupLabel,
  type Major,
} from "@/lib/api/schools";

interface MajorsTabProps {
  majors: Major[];
  scoredMajorCodes?: Set<string>;
  highlightMajorCode?: string;
  onViewScores?: (majorCode: string) => void;
  onSelectMajor?: (majorCode: string) => void;
  onClearHighlight?: () => void;
}

export function MajorsTab({
  majors,
  scoredMajorCodes,
  highlightMajorCode,
  onViewScores,
  onSelectMajor,
  onClearHighlight,
}: MajorsTabProps) {
  const [studyMode, setStudyMode] = useState("");
  const [degreeType, setDegreeType] = useState("");
  const [search, setSearch] = useState("");

  const filtered = majors.filter((m) => {
    if (!isValidMajorRecord(m)) return false;
    if (studyMode && m.study_mode !== studyMode) return false;
    if (degreeType && m.degree_type !== degreeType) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      return (
        m.name.toLowerCase().includes(q) ||
        (m.code ?? "").toLowerCase().includes(q) ||
        (m.college ?? "").toLowerCase().includes(q)
      );
    }
    return true;
  });

  const byCollege = useMemo(() => {
    const groups: Record<string, Major[]> = {};
    for (const m of filtered) {
      const col = resolveCollegeGroupLabel(m);
      (groups[col] ??= []).push(m);
    }
    const sortedKeys = Object.keys(groups).sort((a, b) => {
      if (a === "未标注学院") return 1;
      if (b === "未标注学院") return -1;
      return a.localeCompare(b, "zh-CN");
    });
    return sortedKeys.map((key) => [key, groups[key]!] as const);
  }, [filtered]);

  const highlightDigits = highlightMajorCode?.replace(/\D/g, "").slice(0, 6);
  const highlightRef = useRef<HTMLDivElement>(null);
  const highlightedName = highlightDigits
    ? majors.find(
        (m) => m.code?.replace(/\D/g, "").slice(0, 6) === highlightDigits
      )?.name
    : undefined;

  useEffect(() => {
    if (highlightDigits && highlightRef.current) {
      highlightRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [highlightDigits]);

  return (
    <div className="flex flex-col h-full">
      {highlightDigits && onClearHighlight && (
        <div className="flex items-center justify-between gap-2 border-b border-black/10 bg-black/5 px-4 py-2 text-xs">
          <span className="text-[#111827]">
            已定位专业
            {highlightedName ? `：${highlightedName}` : ` ${highlightDigits}`}
          </span>
          <button
            type="button"
            onClick={onClearHighlight}
            className="shrink-0 font-medium text-[#111827] hover:underline"
          >
            查看全部
          </button>
        </div>
      )}
      <div className="bg-background border-b border-border px-4 py-2.5 flex flex-wrap items-center gap-1">
        <FilterDropdown
          label="学习方式"
          value={studyMode}
          options={[
            { value: "", label: "全部" },
            { value: "全日制", label: "全日制" },
            { value: "非全日制", label: "非全日制" },
          ]}
          onChange={setStudyMode}
        />
        <FilterDropdown
          label="学位类别"
          value={degreeType}
          options={[
            { value: "", label: "全部" },
            { value: "学硕", label: "学硕" },
            { value: "专硕", label: "专硕" },
          ]}
          onChange={setDegreeType}
        />
        <div className="ml-auto flex items-center gap-1.5 rounded-lg border border-border bg-background px-2 py-1.5">
          <Search className="size-3.5 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索专业"
            className="w-24 bg-transparent text-xs outline-none placeholder:text-muted-foreground"
          />
          {search && (
            <button type="button" onClick={() => setSearch("")}>
              <X className="size-3 text-muted-foreground" />
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {majors.length === 0 ? (
          <EmptyState
            title="暂无专业数据"
            description="专业目录正在同步中，请稍后刷新页面"
          />
        ) : filtered.length === 0 ? (
          <EmptyState title="没有匹配专业" description="调整筛选条件或清除搜索" />
        ) : (
          <div className="pb-8 bg-card">
            {byCollege.map(([college, items]) => (
              <CollegeGroup key={college} college={college} majors={items}>
                {items.map((m) => {
                  const rowCode = m.code?.replace(/\D/g, "").slice(0, 6);
                  return (
                  <MajorRow
                    key={m.id}
                    major={m}
                    highlighted={
                      !!highlightDigits &&
                      rowCode === highlightDigits
                    }
                    highlightRef={
                      !!highlightDigits &&
                      rowCode === highlightDigits
                        ? highlightRef
                        : undefined
                    }
                    onViewScores={onViewScores}
                    onSelectMajor={onSelectMajor}
                    hasScore={!!rowCode && !!scoredMajorCodes?.has(rowCode)}
                  />
                  );
                })}
              </CollegeGroup>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function CollegeGroup({
  college,
  majors,
  children,
}: {
  college: string;
  majors: Major[];
  children: React.ReactNode;
}) {
  const [expanded, setExpanded] = useState(true);
  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between border-b border-border/60 bg-muted/30 px-4 py-2.5"
      >
        <span className="text-xs font-semibold text-foreground">{college}</span>
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <span>
            {majors.length}个专业
            {college === "未标注学院" && "（学院信息待补全）"}
          </span>
          <ChevronDown className={cn("size-3.5 transition-transform", expanded && "rotate-180")} />
        </div>
      </button>
      {expanded && <div>{children}</div>}
    </div>
  );
}

function MajorRow({
  major,
  highlighted,
  highlightRef,
  onViewScores,
  onSelectMajor,
  hasScore,
}: {
  major: Major;
  highlighted?: boolean;
  highlightRef?: React.RefObject<HTMLDivElement | null>;
  onViewScores?: (majorCode: string) => void;
  onSelectMajor?: (majorCode: string) => void;
  hasScore?: boolean;
}) {
  const code = major.code?.replace(/\D/g, "").slice(0, 6);
  const query = major.degree_type ? `?degree=${encodeURIComponent(major.degree_type)}` : "";

  return (
    <div
      ref={highlightRef}
      className={cn(
        "flex items-center gap-3 border-b border-border/60 px-4 py-3 last:border-0",
        highlighted && "bg-black/5"
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          {code ? (
            <Link
              href={`/schools/majors/${code}${query}`}
              onClick={() => onSelectMajor?.(code)}
              className="truncate text-sm font-semibold hover:text-[#111827]"
            >
              {major.name}
            </Link>
          ) : (
            <p className="truncate text-sm font-semibold">{major.name}</p>
          )}
          {code && onViewScores && hasScore && (
            <button
              type="button"
              onClick={() => onViewScores(code)}
              className="shrink-0 text-xs text-[#111827] hover:underline"
            >
              本校分数
            </button>
          )}
          {hasScore && (
            <span className="shrink-0 rounded bg-black/5 px-1.5 py-0.5 text-[10px] font-medium text-[#111827]">
              有分数
            </span>
          )}
          {code && (
            <Link
              href={`/schools/majors/${code}${query}`}
              className="shrink-0 text-xs text-muted-foreground hover:text-[#111827] hover:underline"
            >
              跨校开设
            </Link>
          )}
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {[
            major.college &&
            major.college !== "未知学院" &&
            !major.name.includes(major.college)
              ? major.college
              : null,
            major.exam_type,
            major.study_mode,
          ]
            .filter(Boolean)
            .join(" · ")}
          {major.enrollment_count ? ` · 招${major.enrollment_count}人` : ""}
        </p>
      </div>
      {code ? (
        <Link href={`/schools/majors/${code}${query}`}>
          <MajorCodeTag code={code} />
        </Link>
      ) : (
        <span className="shrink-0 rounded bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
          {major.degree_type ?? "学硕"}
        </span>
      )}
    </div>
  );
}
