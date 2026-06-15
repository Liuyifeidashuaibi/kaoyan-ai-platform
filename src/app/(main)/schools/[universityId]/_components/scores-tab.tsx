"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import { FilterDropdown } from "@/components/schools/filter-dropdown";
import { EmptyState } from "@/components/schools/empty-state";
import { SkeletonList } from "@/components/schools/skeleton-list";
import { MajorCodeTag } from "@/components/schools/major-code-tag";
import {
  getScores,
  getScoreYears,
  SCORE_DISPLAY_YEARS,
  type ScoreWithMajor,
} from "@/lib/api/schools";
import { cn } from "@/lib/utils";

interface ScoresTabProps {
  universityId: string;
  dataVersion?: number;
  highlightMajorCode?: string;
  onClearHighlight?: () => void;
}

function formatCollege(college: string | null | undefined): string {
  if (!college || college === "未知学院" || college === "未标注学院") {
    return "—";
  }
  return college;
}

function formatMajorCode(code: string | null | undefined): string {
  return code?.replace(/\D/g, "").slice(0, 6) ?? "";
}

export function ScoresTab({
  universityId,
  dataVersion = 0,
  highlightMajorCode,
  onClearHighlight,
}: ScoresTabProps) {
  const [scores, setScores] = useState<ScoreWithMajor[]>([]);
  const [years, setYears] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);

  const [year, setYear] = useState("");
  const [degreeType, setDegreeType] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [s, ys] = await Promise.all([
          getScores(universityId),
          getScoreYears(universityId),
        ]);
        setScores(s);
        setYears(ys);
      } catch (err) {
        console.error("加载分数失败:", err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [universityId, dataVersion]);

  const filtered = useMemo(() => {
    return scores.filter((s) => {
      if (year && String(s.year) !== year) return false;
      if (degreeType && s.majors?.degree_type !== degreeType) return false;
      if (search.trim()) {
        const q = search.toLowerCase();
        return (
          (s.majors?.name ?? "").toLowerCase().includes(q) ||
          (s.majors?.code ?? "").toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [scores, year, degreeType, search]);

  const sortedRows = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const collegeA = a.majors?.college ?? "";
      const collegeB = b.majors?.college ?? "";
      const byCollege = collegeA.localeCompare(collegeB, "zh-CN");
      if (byCollege !== 0) return byCollege;

      const nameA = a.majors?.name ?? "";
      const nameB = b.majors?.name ?? "";
      const byName = nameA.localeCompare(nameB, "zh-CN");
      if (byName !== 0) return byName;

      return b.year - a.year;
    });
  }, [filtered]);

  const highlightDigits = highlightMajorCode?.replace(/\D/g, "").slice(0, 6);
  const highlightRef = useRef<HTMLTableRowElement>(null);

  useEffect(() => {
    if (highlightDigits && highlightRef.current) {
      highlightRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [highlightDigits, sortedRows.length]);

  const yearOptions = [
    { value: "", label: "全部年份" },
    ...years
      .filter((y) => (SCORE_DISPLAY_YEARS as readonly number[]).includes(y))
      .map((y) => ({ value: String(y), label: `${y}年` })),
  ];

  const highlightedName = highlightDigits
    ? sortedRows.find(
        (s) => formatMajorCode(s.majors?.code) === highlightDigits
      )?.majors?.name
    : undefined;

  return (
    <div className="flex h-full flex-col">
      {highlightDigits && onClearHighlight && (
        <div className="flex items-center justify-between gap-2 border-b border-[#007AFF]/15 bg-[#007AFF]/10 px-4 py-2 text-xs">
          <span className="text-[#007AFF]">
            已定位专业
            {highlightedName ? `：${highlightedName}` : ` ${highlightDigits}`}
          </span>
          <button
            type="button"
            onClick={onClearHighlight}
            className="shrink-0 font-medium text-[#007AFF] hover:underline"
          >
            查看全部
          </button>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-1 border-b border-border bg-background px-4 py-2.5">
        <FilterDropdown
          label="年份"
          value={year}
          options={yearOptions}
          onChange={setYear}
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

      <div className="flex-1 overflow-x-auto overflow-y-auto">
        {loading ? (
          <SkeletonList count={6} className="rounded-none" />
        ) : sortedRows.length === 0 ? (
          <EmptyState
            title="暂无分数"
            description={
              scores.length === 0
                ? "该院校 2025/2026 分数尚未收录，请稍后刷新"
                : "调整筛选条件或清除搜索"
            }
          />
        ) : (
          <div className="overflow-x-auto pb-8">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-xs text-muted-foreground">
                  <th className="py-2.5 pl-4 text-left font-medium">专业名称/代码</th>
                  <th className="py-2.5 text-left font-medium">招生院系</th>
                  <th className="py-2.5 text-center font-medium">总分</th>
                  <th className="py-2.5 text-center font-medium">政治</th>
                  <th className="py-2.5 text-center font-medium">外语</th>
                  <th className="py-2.5 text-center font-medium">业务课一</th>
                  <th className="py-2.5 pr-4 text-center font-medium">业务课二</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {sortedRows.map((score) => {
                  const code = formatMajorCode(score.majors?.code);
                  const highlighted =
                    !!highlightDigits && code === highlightDigits;

                  return (
                    <tr
                      key={score.id}
                      ref={highlighted ? highlightRef : undefined}
                      className={cn(
                        "hover:bg-muted/20",
                        highlighted && "bg-[#007AFF]/10"
                      )}
                    >
                      <td className="py-3 pl-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">
                            {score.majors?.name ?? "—"}
                          </span>
                          {code ? <MajorCodeTag code={code} /> : null}
                        </div>
                      </td>
                      <td className="py-3 text-muted-foreground">
                        {formatCollege(score.majors?.college)}
                      </td>
                      <td className="py-3 text-center font-semibold">
                        {score.total_score}
                      </td>
                      <td className="py-3 text-center">{score.politics_score}</td>
                      <td className="py-3 text-center">{score.english_score}</td>
                      <td className="py-3 text-center">
                        {score.professional1_score ?? "—"}
                      </td>
                      <td className="py-3 pr-4 text-center">
                        {score.professional2_score ?? "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
