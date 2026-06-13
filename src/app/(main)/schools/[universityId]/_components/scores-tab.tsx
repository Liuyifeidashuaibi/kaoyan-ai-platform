"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ExternalLink, Search, X } from "lucide-react";
import { FilterDropdown } from "@/components/schools/filter-dropdown";
import { EmptyState } from "@/components/schools/empty-state";
import { SkeletonList } from "@/components/schools/skeleton-list";
import { MajorCodeTag } from "@/components/schools/major-code-tag";
import {
  getScores,
  getScoreYears,
  getLineDiffColor,
  groupScoresByMajor,
  groupScoresByCollege,
  SCORE_DISPLAY_YEARS,
  type ScoreWithMajor,
} from "@/lib/api/schools";
import { cn } from "@/lib/utils";

interface ScoresTabProps {
  universityId: string;
  dataVersion?: number;
  highlightMajorCode?: string;
  onViewMajors?: (majorCode: string) => void;
  onClearHighlight?: () => void;
}

export function ScoresTab({
  universityId,
  dataVersion = 0,
  highlightMajorCode,
  onViewMajors,
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
        console.error("加载复试线失败:", err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [universityId, dataVersion]);

  const filtered = scores.filter((s) => {
    if (year && String(s.year) !== year) return false;
    if (degreeType && s.majors?.degree_type !== degreeType) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      return (
        (s.majors?.name ?? "").toLowerCase().includes(q) ||
        (s.majors?.code ?? "").toLowerCase().includes(q) ||
        (s.majors?.college ?? "").toLowerCase().includes(q)
      );
    }
    return true;
  });

  const grouped = useMemo(() => groupScoresByMajor(filtered), [filtered]);
  const byCollege = useMemo(() => groupScoresByCollege(grouped), [grouped]);
  const useCollegeSections = byCollege.length > 1 || byCollege[0]?.college !== "未标注学院";

  const highlightDigits = highlightMajorCode?.replace(/\D/g, "").slice(0, 6);
  const highlightRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (highlightDigits && highlightRef.current) {
      highlightRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [highlightDigits, grouped.length]);

  const yearOptions = [
    { value: "", label: "全部年份" },
    ...years
      .filter((y) => (SCORE_DISPLAY_YEARS as readonly number[]).includes(y))
      .map((y) => ({ value: String(y), label: `${y}年` })),
  ];

  const highlightedName = highlightDigits
    ? grouped.find(
        (g) => g.code?.replace(/\D/g, "").slice(0, 6) === highlightDigits
      )?.name
    : undefined;

  return (
    <div className="flex flex-col h-full">
      {highlightDigits && onClearHighlight && (
        <div className="flex items-center justify-between gap-2 border-b border-orange-100 bg-orange-50/60 px-4 py-2 text-xs">
          <span className="text-orange-800">
            已定位专业
            {highlightedName ? `：${highlightedName}` : ` ${highlightDigits}`}
          </span>
          <button
            type="button"
            onClick={onClearHighlight}
            className="shrink-0 font-medium text-orange-600 hover:underline"
          >
            查看全部
          </button>
        </div>
      )}
      <p className="border-b border-border/60 bg-orange-50/80 px-4 py-2 text-xs text-orange-900/90">
        以下为进入复试的最低初试总分（2025/2026），非拟录取最低分。
      </p>
      <div className="bg-background border-b border-border px-4 py-2.5 flex flex-wrap items-center gap-1">
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
            placeholder="搜索专业/学院"
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
        ) : grouped.length === 0 ? (
          <EmptyState
            title="暂无进复试最低分"
            description={
              scores.length === 0
                ? "该院校 2025/2026 进复试分数线尚未收录，请稍后刷新"
                : "调整筛选条件或清除搜索"
            }
          />
        ) : useCollegeSections ? (
          <div className="pb-8">
            {byCollege.map((section) => (
              <div key={section.college} className="border-b border-border/40 last:border-0">
                <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border/60 bg-muted/50 px-4 py-2">
                  <span className="text-xs font-semibold text-foreground">
                    {section.college}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {section.groups.length} 个专业
                  </span>
                </div>
                {section.groups.map((group) => {
                  const code = group.code?.replace(/\D/g, "").slice(0, 6);
                  const highlighted =
                    !!highlightDigits && code === highlightDigits;
                  const query = group.degreeType
                    ? `?degree=${encodeURIComponent(group.degreeType)}`
                    : "";
                  return (
                    <MajorScoreGroup
                      key={group.majorId}
                      group={group}
                      highlighted={highlighted}
                      highlightRef={highlighted ? highlightRef : undefined}
                      crossSchoolHref={
                        code ? `/schools/majors/${code}${query}` : undefined
                      }
                      onViewMajors={
                        code && onViewMajors ? () => onViewMajors(code) : undefined
                      }
                    />
                  );
                })}
              </div>
            ))}
          </div>
        ) : (
          <div className="pb-8">
            {grouped.map((group) => {
              const code = group.code?.replace(/\D/g, "").slice(0, 6);
              const highlighted =
                !!highlightDigits &&
                code === highlightDigits;
              const query = group.degreeType
                ? `?degree=${encodeURIComponent(group.degreeType)}`
                : "";

              return (
                <MajorScoreGroup
                  key={group.majorId}
                  group={group}
                  highlighted={highlighted}
                  highlightRef={highlighted ? highlightRef : undefined}
                  crossSchoolHref={code ? `/schools/majors/${code}${query}` : undefined}
                  onViewMajors={code && onViewMajors ? () => onViewMajors(code) : undefined}
                />
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function MajorScoreGroup({
  group,
  highlighted,
  highlightRef,
  crossSchoolHref,
  onViewMajors,
}: {
  group: ReturnType<typeof groupScoresByMajor>[number];
  highlighted?: boolean;
  highlightRef?: React.RefObject<HTMLDivElement | null>;
  crossSchoolHref?: string;
  onViewMajors?: () => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const code = group.code?.replace(/\D/g, "").slice(0, 6);

  return (
    <div
      ref={highlightRef}
      className={cn(
        "border-b border-border/60",
        highlighted && "bg-orange-50/40"
      )}
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-muted/20"
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold">{group.name}</p>
            {code && <MajorCodeTag code={code} />}
            {onViewMajors && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onViewMajors();
                }}
                className="text-xs text-orange-500 hover:underline"
              >
                本校专业
              </button>
            )}
            {crossSchoolHref && (
              <Link
                href={crossSchoolHref}
                onClick={(e) => e.stopPropagation()}
                className="text-xs text-muted-foreground hover:text-orange-500 hover:underline"
              >
                跨校开设
              </Link>
            )}
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {[
              group.college &&
              group.college !== "未知学院" &&
              group.college !== "未标注学院"
                ? group.college
                : null,
              group.degreeType ?? "学硕",
              `${group.scores.length} 条进复试线`,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <ChevronDown
          className={cn(
            "mt-1 size-4 shrink-0 text-muted-foreground transition-transform",
            expanded && "rotate-180"
          )}
        />
      </button>

      {expanded && (
        <div className="overflow-x-auto px-4 pb-3">
          <table className="w-full min-w-[480px] text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40 text-xs text-muted-foreground">
                <th className="py-2 pl-2 text-left font-medium">年份</th>
                <th className="py-2 text-center font-medium">进复试最低分</th>
                <th className="py-2 text-center font-medium">政治</th>
                <th className="py-2 text-center font-medium">英语</th>
                <th className="py-2 text-center font-medium">专业①</th>
                <th className="py-2 text-center font-medium">专业②</th>
                <th className="py-2 pr-2 text-center font-medium">国家线差</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {group.scores.map((s) => (
                <ScoreRow key={s.id} score={s} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ScoreRow({ score }: { score: ScoreWithMajor }) {
  return (
    <>
      <tr className="hover:bg-muted/20">
        <td className="py-2.5 pl-2 text-sm font-medium">{score.year}</td>
        <td className="py-2.5 text-center font-semibold">{score.total_score}</td>
        <td className="py-2.5 text-center">{score.politics_score}</td>
        <td className="py-2.5 text-center">{score.english_score}</td>
        <td className="py-2.5 text-center">{score.professional1_score ?? "—"}</td>
        <td className="py-2.5 text-center">{score.professional2_score ?? "—"}</td>
        <td className="py-2.5 pr-2 text-center">
          {score.line_diff != null ? (
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-xs font-semibold",
                score.line_diff > 0
                  ? "bg-green-50 text-green-700"
                  : score.line_diff < 0
                    ? "bg-red-50 text-red-600"
                    : "bg-muted text-muted-foreground"
              )}
            >
              {score.line_diff > 0 ? "+" : ""}
              {score.line_diff}
            </span>
          ) : (
            <span className={getLineDiffColor(null)}>—</span>
          )}
        </td>
      </tr>
      {(score.source_url || score.publish_date) && (
        <tr className="bg-muted/10">
          <td colSpan={7} className="px-4 pb-2 pt-0 text-[11px] text-muted-foreground">
            {score.publish_date && (
              <span>发布于 {score.publish_date} · </span>
            )}
            {score.source_url ? (
              <a
                href={score.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-0.5 text-orange-600 hover:underline"
              >
                来源链接
                <ExternalLink className="size-3" />
              </a>
            ) : (
              <span>数据来源：第三方整理复试线</span>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
